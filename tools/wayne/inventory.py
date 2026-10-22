#!/usr/bin/env python3
"""Compare vendor enabled symbols with upstream Kconfig definitions, without claiming API compatibility."""
import argparse
import json
import pathlib
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--vendor-config", required=True, type=pathlib.Path)
parser.add_argument("--upstream-git", required=True, type=pathlib.Path)
parser.add_argument("--output", required=True, type=pathlib.Path)
args = parser.parse_args()
git_args = ["git", "-C", str(args.upstream_git)]
sha = subprocess.check_output(git_args + ["rev-parse", "HEAD"], text=True).strip()
if sha != "adc218676eef25575469234709c2d87185ca223a":
    raise SystemExit(f"Expected the pinned v6.12 tree; got {sha}.")
definitions = subprocess.check_output(
    git_args + ["grep", "-h", "-E", r"^(menu)?config [A-Za-z0-9_]+", "HEAD", "--", "**/Kconfig*"],
    text=True,
)
symbols = set(re.findall(r"^(?:menu)?config ([A-Za-z0-9_]+)", definitions, re.M))
enabled = re.findall(r"^CONFIG_([A-Za-z0-9_]+)=([ym])$", args.vendor_config.read_text(), re.M)
missing = sorted(name for name, value in enabled if name not in symbols)
result = {
    "vendor_commit": "3316cb3851478cb1d63cf79b40eea6dc1df8bee4",
    "vendor_config": "arch/arm64/configs/vendor/" + args.vendor_config.name,
    "upstream_commit": sha,
    "enabled_vendor_symbols": len(enabled),
    "symbols_absent_by_name": len(missing),
    "interpretation": "Absent names include renamed or removed options; matching names do not prove driver or Android ABI compatibility.",
    "absent_symbols": ["CONFIG_" + name for name in missing],
}
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(missing)} of {len(enabled)} enabled vendor symbols are absent by name in v6.12.")
print(args.output)
