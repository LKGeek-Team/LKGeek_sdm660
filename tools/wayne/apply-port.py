#!/usr/bin/env python3
"""Apply the experimental Wayne overlay to the pinned upstream v6.12 tree."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess

PINNED_COMMIT = "adc218676eef25575469234709c2d87185ca223a"


def apply(source: pathlib.Path, overlay: pathlib.Path) -> None:
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != PINNED_COMMIT:
        raise SystemExit(f"Expected upstream v6.12 ({PINNED_COMMIT}), found {commit}.")
    makefile = (source / "Makefile").read_text()
    version = tuple(re.search(rf"^{key}\s*=\s*(\d+)$", makefile, re.M)[1]
                    for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL"))
    if version != ("6", "12", "0"):
        raise SystemExit(f"Unexpected kernel version: {version}")
    name = "sdm660-xiaomi-wayne.dts"
    destination = source / "arch/arm64/boot/dts/qcom" / name
    content = (overlay / name).read_bytes()
    manifest_path = source / "wayne-port-manifest.json"
    if destination.exists() and destination.read_bytes() != content:
        previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        current_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
        if previous.get("overlay_sha256") != current_hash:
            raise SystemExit(f"{destination} has local edits; refusing to overwrite them.")
    destination.write_bytes(content)
    target_makefile = destination.parent / "Makefile"
    registration = "dtb-$(CONFIG_ARCH_QCOM) += sdm660-xiaomi-wayne.dtb"
    original = target_makefile.read_text()
    if registration not in original.splitlines():
        with target_makefile.open("a", newline="\n") as stream:
            stream.write("\n" + registration + "\n")
    binding = source / "Documentation/devicetree/bindings/arm/qcom.yaml"
    binding_text = binding.read_text()
    if "- xiaomi,wayne" not in binding_text:
        anchor = "              - xiaomi,lavender\n          - const: qcom,sdm660"
        if binding_text.count(anchor) != 1:
            raise SystemExit("Cannot find the SDM660 board binding; inspect the source tree.")
        binding.write_text(binding_text.replace(
            anchor, "              - xiaomi,lavender\n              - xiaomi,wayne\n          - const: qcom,sdm660"
        ), newline="\n")
    manifest = {
        "upstream_commit": commit,
        "overlay_sha256": hashlib.sha256(content).hexdigest(),
        "state": "experimental; not boot-tested; Android vendor support incomplete",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Applied experimental Wayne overlay to {source} at {commit}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("overlay", type=pathlib.Path)
    arguments = parser.parse_args()
    apply(arguments.source.resolve(), arguments.overlay.resolve())
