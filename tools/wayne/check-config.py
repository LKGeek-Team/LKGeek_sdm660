#!/usr/bin/env python3
"""Fail when Kconfig silently drops a requested Wayne configuration option."""
import pathlib
import re
import sys


def parse(path):
    result = {}
    for line in pathlib.Path(path).read_text().splitlines():
        assignment = re.fullmatch(r"(CONFIG_\w+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_\w+) is not set", line)
        if assignment:
            result[assignment[1]] = assignment[2]
        elif disabled:
            result[disabled[1]] = "n"
    return result


if __name__ == "__main__":
    actual, requested = map(parse, sys.argv[1:3])
    failures = [(key, wanted, actual.get(key, "n"))
                for key, wanted in requested.items() if actual.get(key, "n") != wanted]
    for key, wanted, found in failures:
        print(f"{key}: requested {wanted}, got {found}", file=sys.stderr)
    if failures:
        raise SystemExit(1)
    print(f"All {len(requested)} requested config values survived olddefconfig.")
