#!/usr/bin/env python3
"""Compile a DTS using pcpp + native DTC while WSL is unavailable (not a Kbuild check)."""
import argparse
import pathlib
import posixpath
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", required=True, type=pathlib.Path)
parser.add_argument("--dtc", required=True, type=pathlib.Path)
parser.add_argument("--python-tools", type=pathlib.Path)
parser.add_argument("--output", required=True, type=pathlib.Path)
args = parser.parse_args()
if args.python_tools:
    sys.path.insert(0, str(args.python_tools.resolve()))
from pcpp import Preprocessor

source = args.source.resolve()
git = ["git", "-C", str(source)]
sha = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
if sha != "adc218676eef25575469234709c2d87185ca223a":
    raise SystemExit(f"Expected pinned Linux v6.12, got {sha}")
output = args.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
qcom = source / "arch/arm64/boot/dts/qcom"
entry = qcom / "sdm660-xiaomi-wayne.dts"
with tempfile.TemporaryDirectory(prefix="wayne-dt-includes-") as directory:
    includes = pathlib.Path(directory)
    # Git for Windows represents symlinks as text. Resolve their Git targets in a
    # temporary include path, leaving the upstream checkout untouched.
    tree = subprocess.check_output(git + ["ls-tree", "-r", "-z", "HEAD", "include/dt-bindings"])
    for item in tree.split(b"\0"):
        if not item.startswith(b"120000 "):
            continue
        name = item.split(b"\t", 1)[1].decode()
        target = subprocess.check_output(git + ["show", "HEAD:" + name]).decode().strip()
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        if not resolved.startswith("include/"):
            raise SystemExit(f"Unexpected header symlink target: {resolved}")
        destination = includes / pathlib.PurePosixPath(name).relative_to("include")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(subprocess.check_output(git + ["show", "HEAD:" + resolved]))
    preprocessor = Preprocessor()
    for path in (qcom, includes, source / "include"):
        preprocessor.add_path(str(path))
    preprocessor.define("__DTS__")
    preprocessor.line_directive = None
    preprocessor.parse(entry.read_text(), source=str(entry))
    preprocessed = output.with_suffix(".preprocessed.dts")
    with preprocessed.open("w", encoding="utf-8", newline="\n") as stream:
        preprocessor.write(stream)
    if preprocessor.return_code:
        raise SystemExit(preprocessor.return_code)
    result = subprocess.run([str(args.dtc.resolve()), "-I", "dts", "-O", "dtb",
                             "-o", str(output), str(preprocessed)], capture_output=True)
    output.with_suffix(".warnings.log").write_bytes(result.stderr)
    if result.stderr:
        print(result.stderr.decode(errors="replace"), file=sys.stderr, end="")
    result.check_returncode()
subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("inspect-dtb.py")),
                str(output)], check=True)
