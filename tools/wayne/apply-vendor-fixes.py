#!/usr/bin/env python3
"""Apply the reviewed cleanup to the pinned vendor baseline, once."""
import argparse
import pathlib
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=pathlib.Path)
parser.add_argument("patch", type=pathlib.Path)
args = parser.parse_args()
command = ["git", "-C", str(args.source.resolve()), "apply"]
patch = str(args.patch.resolve())
if subprocess.run(command + ["--reverse", "--check", patch], capture_output=True).returncode == 0:
    print("Reviewed legacy KernelSU cleanup is already applied.")
elif subprocess.run(command + ["--check", patch], capture_output=True).returncode == 0:
    subprocess.run(command + [patch], check=True)
    print("Applied reviewed legacy KernelSU cleanup.")
else:
    raise SystemExit("Vendor source differs from the reviewed cleanup; inspect local edits before continuing.")
