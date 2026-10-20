#!/usr/bin/env python3
"""Replace a verified system image in an existing Wayne recovery ZIP.

Unchanged entries, including vendor, retain their original compressed streams.
The source ZIP must already have a working recovery installer.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-rom", required=True, type=Path)
    parser.add_argument("--system-image", required=True, type=Path)
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--boot-image", type=Path)
    parser.add_argument("--kernel-commit")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"Refusing to overwrite {output}")
    if bool(args.boot_image) != bool(args.kernel_commit):
        raise ValueError("Supply --boot-image and --kernel-commit together")
    verification = json.loads(args.verification.read_text())
    if verification["errors"] or verification["extra_paths"]:
        raise ValueError("System image verification failed")
    with args.system_image.open("rb") as stream:
        stream.seek(1024)
        superblock = stream.read(128)
    if struct.unpack_from("<I", superblock)[0] != 0xE0F5E1E2:
        raise ValueError("Expected an EROFS system image")
    if struct.unpack_from("<I", superblock, 80)[0] & ~3:
        raise ValueError("Image uses EROFS features unsupported by this kernel")

    replacements = {"system": args.system_image.resolve()}
    if args.boot_image:
        replacements["boot"] = args.boot_image.resolve()
    with zipfile.ZipFile(args.source_rom) as source:
        manifest = json.loads(source.read("manifest.json"))
        if manifest["device"] != "wayne":
            raise ValueError("Expected a Wayne ROM")
        original_images = json.loads(json.dumps(manifest["images"]))
        for name, path in replacements.items():
            manifest["images"][name] = {"bytes": path.stat().st_size,
                                        "sha256": digest(path)}
        if args.kernel_commit:
            manifest["kernel_commit"] = args.kernel_commit
            manifest["charge_stack"] = "Pre-import 1e1c11baf6e4 charging drivers and DT settings"
            manifest["known_issues"] = ["Charging input remains limited in device testing; speed is not fixed"]
        fixes = manifest.setdefault("built_in_fixes", [])
        if "theme_store_native_libraries" not in fixes:
            fixes.append("theme_store_native_libraries")
        manifest["theme_store"] = {"package": "com.heytap.themestore",
                                   "path": "/system/app/KeKeThemeSpace",
                                   "original_apk_and_libraries": True}
        # Existing package verification does not imply this new image has booted.
        manifest["erofs_device_boot_tested"] = False

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    if partial.exists():
        raise ValueError(f"Refusing to overwrite {partial}")
    with tempfile.TemporaryDirectory(prefix="theme-rom-", dir=output.parent) as directory:
        stage = Path(directory)
        (stage / "images").mkdir()
        for name, path in replacements.items():
            (stage / f"images/{name}.img").symlink_to(path)
        images = manifest["images"]
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (stage / "images.sha256").write_text("".join(
            item["sha256"] + f"  images/{name}.img\n" for name, item in images.items()))
        (stage / "image-sizes.txt").write_text("".join(
            f"{name} {item['bytes']}\n" for name, item in images.items()))
        (stage / "README.txt").write_text(
            "LKGeek ColorOS 15 / Xiaomi Mi 6X wayne / MI 6X MIKU\n\n"
            "Built-in theme repair: original theme store APK and all ARM64 libraries "
            "moved to /system/app/KeKeThemeSpace. No first-boot reinstall is required.\n"
            "Other system fixes and vendor image are retained from the source ROM. "
            "See manifest.json for the current kernel, image hashes and known issues.\n"
            "Charging speed remains unresolved; this package does not claim to fix it.\n\n"
            "Install with compatible custom recovery and the existing Wayne partition layout. "
            "The installer verifies partition capacities and written image checksums. "
            "It preserves userdata and recovery and does not repartition or flash firmware.\n"
            "Retain your own backup. Host image verification is separate from device boot testing.\n")
        shutil.copyfile(args.source_rom, partial)
        subprocess.run(["7z", "u", "-tzip", "-mx=1", str(partial),
                        *[f"images/{name}.img" for name in replacements],
                        "manifest.json", "images.sha256", "image-sizes.txt", "README.txt"],
                       cwd=stage, check=True, stdout=subprocess.DEVNULL)

    with zipfile.ZipFile(partial) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        if any(item.extract_version >= 45 for item in archive.infolist()):
            raise ValueError("Unexpected ZIP64 entry")
        for name, item in manifest["images"].items():
            with archive.open(f"images/{name}.img") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != item["sha256"]:
                raise ValueError(f"Packaged {name} checksum differs")
        for name, item in original_images.items():
            if name not in replacements and item != manifest["images"][name]:
                raise ValueError(f"Unexpected change to {name}")
    partial.rename(output)
    sha = digest(output)
    output.with_suffix(output.suffix + ".sha256").write_text(f"{sha}  {output.name}\n")
    print(json.dumps({"path": str(output), "bytes": output.stat().st_size,
                      "sha256": sha, "images": manifest["images"]}, indent=2))


if __name__ == "__main__":
    main()
