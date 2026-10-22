#!/usr/bin/env python3
"""Connect the pinned Android 14 Wayne device tree to Scarlet's OSS kernel config."""
import argparse
import pathlib
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("rom", type=pathlib.Path)
parser.add_argument("overlay", type=pathlib.Path)
args = parser.parse_args()
device = args.rom / "device/xiaomi/wayne"
sha = subprocess.check_output(["git", "-C", str(device), "rev-parse", "HEAD"], text=True).strip()
if sha != "e8f24a6736237fa8afde2986cf08e32717f9f508":
    raise SystemExit(f"Unexpected device tree revision: {sha}")
board = device / "BoardConfig.mk"
board_text = board.read_text()
include = "include device/xiaomi/wayne/ScarletKernel.mk"
overlay = (args.overlay / "ScarletKernel.mk").read_bytes()
destination = device / "ScarletKernel.mk"
if destination.exists() and destination.read_bytes() != overlay:
    raise SystemExit("ScarletKernel.mk has local edits; refusing to overwrite it.")
destination.write_bytes(overlay)
if include not in board_text.splitlines():
    with board.open("a", newline="\n") as stream:
        stream.write("\n" + include + "\n")
print("Selected Scarlet's Wayne OSS config for the Android 14 / 4.19 baseline.")
