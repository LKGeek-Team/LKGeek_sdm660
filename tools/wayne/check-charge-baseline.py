#!/usr/bin/env python3
"""Reject changes to Wayne's charging stack after the pinned pre-import commit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

BASELINE = '1e1c11baf6e4470207eb40f7dde8c449b94b942c'
SCOPE = [
    'drivers/power/supply/qcom', 'drivers/usb/pd',
    'drivers/of/of_batterydata.c', 'include/linux/of_batterydata.h',
    'include/linux/power_supply.h', 'include/linux/qpnp',
    'drivers/iio/adc/qcom-rradc.c', 'drivers/iio/adc/qcom-spmi-adc5.c',
    'drivers/thermal/qcom/adc-tm.c', 'drivers/thermal/qcom/adc-tm-common.c',
    'drivers/thermal/qcom/adc-tm5.c', 'drivers/thermal/qcom/adc-tm7.c',
    'drivers/thermal/qcom/bcl_peripheral.c',
    'drivers/usb/phy/phy-msm-snps-hs.c', 'drivers/usb/phy/phy-msm-qusb.c',
    'drivers/usb/dwc3/dwc3-msm.c',
    'arch/arm64/boot/dts/vendor/qcom/pm660.dtsi',
]
WAYNE = 'arch/arm64/boot/dts/vendor/qcom/xiaomi/longcheer/wayne/'
SCOPE += [WAYNE + f'fg-gen3-batterydata-l8866{kind}-3000mah.dtsi' for kind in ('cos', 'default', 'sun')]
BLOCKS = {
    WAYNE + 'wayne-common-base.dtsi': ['&pm660_charger', '&pm660_fg'],
    'arch/arm64/boot/dts/vendor/qcom/xiaomi/longcheer/common/longcheer-sdm660-mtp.dtsi': ['&mtp_batterydata'],
}


def dt_nodes(path):
    data = path.read_bytes()
    magic, size, offset, strings = struct.unpack_from('>4I', data)
    if magic != 0xd00dfeed or size != len(data):
        raise ValueError('Expected one complete DTB')
    stack, nodes = [], {}
    while True:
        token = struct.unpack_from('>I', data, offset)[0]
        offset += 4
        if token == 1:
            end = data.index(0, offset)
            stack.append(data[offset:end].decode())
            offset = (end + 4) & ~3
            nodes['/'.join(stack)] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name = struct.unpack_from('>II', data, offset)
            offset += 8
            end = data.index(0, strings + name)
            nodes['/'.join(stack)][data[strings + name:end].decode()] = data[offset:offset + length]
            offset = (offset + length + 3) & ~3
        elif token == 9:
            return nodes
        elif token != 4:
            raise ValueError(f'Invalid FDT token: {token}')


def block(text, name):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    start = text.index('{', text.index(name))
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return re.sub(r'\s+', '', text[start:end])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--dtb', type=Path)
    parser.add_argument('--baseline-dtb', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    def git(*params):
        return subprocess.check_output(['git', '-C', str(args.root), *params])
    paths = git('ls-tree', '-r', '--name-only', BASELINE, '--', *SCOPE).decode().splitlines()
    errors, hashes = [], {}
    expected_paths = set(paths)
    for scope in SCOPE:
        p = args.root / scope
        actual = [q for q in p.rglob('*') if q.is_file()] if p.is_dir() else ([p] if p.exists() else [])
        for q in actual:
            rel = str(q.relative_to(args.root))
            if rel not in expected_paths:
                errors.append(f'Unexpected charging file: {rel}')
    for name in paths:
        expected = git('show', BASELINE + ':' + name)
        path = args.root / name
        if not path.is_file() or path.read_bytes() != expected:
            errors.append(f'Charging source differs: {name}')
        hashes[name] = hashlib.sha256(expected).hexdigest()
    for name, labels in BLOCKS.items():
        expected = git('show', BASELINE + ':' + name).decode()
        actual = (args.root / name).read_text()
        for label in labels:
            if block(expected, label) != block(actual, label):
                errors.append(f'Charging DTS block differs: {name} {label}')
    count = None
    if bool(args.dtb) != bool(args.baseline_dtb):
        parser.error('Supply --dtb and --baseline-dtb together')
    if args.dtb:
        old, new = dt_nodes(args.baseline_dtb), dt_nodes(args.dtb)
        pattern = re.compile(r'charg|batt|fuel-gauge|rradc|pdphy|usb-pd|usbpd|typec|qusb|bcl|adc-tm|qpnp,fg|qpnp-smb2', re.I)
        selected = {p for p in old.keys() | new.keys() if pattern.search(p)}
        refs = {'qcom,battery-data', 'qcom,pmic-revid', 'qcom,pmic-misc', 'qcom,pmic-rradc', 'interrupt-parent'}
        def normalize(nodes, properties):
            phandles = {v.get('phandle', v.get('linux,phandle')): p for p, v in nodes.items()}
            def value(k, v):
                if k in refs or k.endswith('-supply'):
                    return phandles.get(v, v.hex())
                providers = {'clocks': '#clock-cells', 'resets': '#reset-cells',
                             'phys': '#phy-cells', 'io-channels': '#io-channel-cells'}
                if k not in providers:
                    return v.hex()
                cells = struct.unpack('>' + 'I' * (len(v) // 4), v)
                result, index = [], 0
                while index < len(cells):
                    target = phandles.get(struct.pack('>I', cells[index]))
                    if target is None:
                        raise ValueError(f'Unresolved {k} phandle')
                    count = struct.unpack('>I', nodes[target][providers[k]])[0]
                    result.append((target, list(cells[index + 1:index + 1 + count])))
                    index += 1 + count
                return result
            return {k: value(k, v) for k, v in properties.items()
                    if k not in ('phandle', 'linux,phandle')}
        for path in sorted(selected):
            if path not in old or path not in new or normalize(old, old[path]) != normalize(new, new[path]):
                errors.append(f'Charging DT node differs: {path}')
        count = len(selected)
    report = {'baseline': BASELINE, 'source_files_checked': len(paths), 'source_sha256': hashes,
              'mixed_dts_blocks_checked': sum(map(len, BLOCKS.values())), 'dt_nodes_checked': count,
              'errors': errors}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'source_sha256'}, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
