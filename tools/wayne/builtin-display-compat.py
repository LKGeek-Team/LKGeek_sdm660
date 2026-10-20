#!/usr/bin/env python3
"""Apply Wayne's single-mode display configuration to a mounted system image."""

import argparse
import json
import os
from pathlib import Path
import re


def write_preserving_metadata(path, content):
    if path.read_text() != content:
        path.write_text(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system_root", type=Path)
    args = parser.parse_args()
    root = args.system_root.resolve()
    props = root / "my_product/build.prop"
    content = props.read_text()
    for key in ["ro.sf.lcd_density", "ro.oplus.density.fhd_default", "ro.oplus.density.qhd_default"]:
        if re.search(r"^" + re.escape(key) + r"=440$", content, re.M) is None:
            raise ValueError(f"Expected Wayne 440 DPI baseline: {key}")
    for key, value in [("persist.sys.display.density", "440"),
                       ("persist.sys.miui_resolution", "1080,2160,440")]:
        content = re.sub(r"^" + re.escape(key) + r"=.*\n?", "", content, flags=re.M)
        content = content.rstrip() + f"\n{key}={value}\n"
    write_preserving_metadata(props, content)

    feature_paths = [root / folder / "etc/permissions/oplus.product.feature_multimedia_unique.xml"
                     for folder in ["my_product", "system_ext"]]
    for path in feature_paths:
        content = path.read_text()
        content = re.sub(r'^\s*<oplus-feature name="oplus\.software\.display\.resolution_switch_support"\s*/>[^\S\n]*\n',
                         "", content, flags=re.M)
        write_preserving_metadata(path, content)

    config = root / "my_product/etc/sys_resolution_switch_config.xml"
    content = config.read_text()
    content, count = re.subn(r'(<sys_resolution_switch_config\b[^>]*\bscreenwidth=")[0-9]+("[^>]*>)',
                            r'\g<1>1080\2', content)
    if count != 1:
        raise ValueError("Unexpected resolution configuration")
    content, count = re.subn(r'<scaleinfo value="[^"]+"\s*/>',
                            '<scaleinfo value="1.0,1.0,440" />', content)
    if count != 1:
        raise ValueError("Unexpected default resolution scale")
    write_preserving_metadata(config, content)

    source = Path(__file__).resolve().parent
    for name, target, mode in [
        ("lkgeek-display-compat.sh", "system/bin/lkgeek-display-compat.sh", 0o755),
        ("lkgeek_display_compat.rc", "system/etc/init/lkgeek_display_compat.rc", 0o644),
    ]:
        path = root / target
        path.write_bytes((source / name).read_bytes())
        os.chown(path, 0, 0)
        os.chmod(path, mode)
        label = b"u:object_r:system_file:s0\0"
        os.setxattr(path, "security.selinux", label)
    print(json.dumps({"resolution": "1080x2160", "default_dpi": 440,
                      "resolution_switch_feature": False,
                      "boot_sync": "/system/etc/init/lkgeek_display_compat.rc"}, indent=2))


if __name__ == "__main__":
    main()
