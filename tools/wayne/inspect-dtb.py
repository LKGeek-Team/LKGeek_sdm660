#!/usr/bin/env python3
"""Validate DTB structure and the initial Wayne board properties without libfdt."""
import argparse
import hashlib
import json
import pathlib
import struct


def inspect(path):
    data = pathlib.Path(path).read_bytes()
    if len(data) < 40:
        raise ValueError("Truncated DTB header")
    magic, total, off_struct, off_strings, off_reserve, version, last, cpu, strings_len, struct_len = struct.unpack(
        ">10I", data[:40]
    )
    if magic != 0xD00DFEED or total != len(data) or version != 17:
        raise ValueError("Invalid magic, total size or DTB version")
    if not (40 <= off_reserve < off_struct < off_strings <= total):
        raise ValueError("Invalid DTB section offsets")
    if off_struct + struct_len != off_strings or off_strings + strings_len > total:
        raise ValueError("DTB section sizes exceed file bounds")
    position, end = off_struct, off_struct + struct_len
    nodes, stack = {}, []
    while position < end:
        if position + 4 > end:
            raise ValueError("Truncated structure token")
        token = struct.unpack_from(">I", data, position)[0]
        position += 4
        if token == 1:
            terminator = data.index(b"\0", position, end)
            stack.append(data[position:terminator].decode("ascii"))
            position = (terminator + 4) & ~3
            node = "/" + "/".join(stack[1:])
            if node in nodes:
                raise ValueError(f"Duplicate node {node}")
            nodes[node] = {}
        elif token == 2:
            if not stack:
                raise ValueError("Unbalanced end-node")
            stack.pop()
        elif token == 3:
            if not stack or position + 8 > end:
                raise ValueError("Invalid property token")
            length, nameoff = struct.unpack_from(">2I", data, position)
            position += 8
            if nameoff >= strings_len or position + length > end:
                raise ValueError("Property exceeds section bounds")
            start = off_strings + nameoff
            terminator = data.index(b"\0", start, off_strings + strings_len)
            name = data[start:terminator].decode("ascii")
            props = nodes["/" + "/".join(stack[1:])]
            if name in props:
                raise ValueError(f"Duplicate property {name}")
            props[name] = data[position:position + length]
            position = (position + length + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            if stack or position != end:
                raise ValueError("Invalid end-of-tree")
            break
        else:
            raise ValueError(f"Unknown structure token {token}")
    else:
        raise ValueError("Missing end-of-tree token")
    expected = {
        ("/", "compatible"): b"xiaomi,wayne\0qcom,sdm660\0",
        ("/", "qcom,msm-id"): struct.pack(">2I", 317, 0),
        ("/chosen", "stdout-path"): b"serial0:115200n8\0",
        ("/soc@0/mmc@c0c4000", "status"): b"okay\0",
        ("/reserved-memory/ramoops@a0000000", "reg"): struct.pack(">4I", 0, 0xa0000000, 0, 0x400000),
        ("/reserved-memory/tzbuffer@94a00000", "reg"): struct.pack(">4I", 0, 0x94a00000, 0, 0x600000),
    }
    for (node, prop), value in expected.items():
        if nodes.get(node, {}).get(prop) != value:
            raise ValueError(f"Unexpected Wayne property: {node}:{prop}")
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": total,
            "nodes": len(nodes), "board_checks_passed": len(expected),
            "kernel_compiled": False, "boot_tested": False, "schema_validated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dtb", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    arguments = parser.parse_args()
    result = json.dumps(inspect(arguments.dtb), indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(result, encoding="utf-8")
    print(result, end="")
