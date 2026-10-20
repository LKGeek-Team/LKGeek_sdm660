#!/usr/bin/env python3
"""Move the stock theme store into the normal system-app scan directory.

Run against a writable, mounted system image root before building EROFS.
The original APK, native libraries, ownership and SELinux labels are retained.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile


def verify(app):
    apk = app / "KeKeThemeSpace.apk"
    libraries = []
    with zipfile.ZipFile(apk) as archive:
        for name in archive.namelist():
            if not name.startswith("lib/arm64-v8a/") or name.endswith("/"):
                continue
            path = app / "lib/arm64" / Path(name).name
            if path.read_bytes() != archive.read(name):
                raise ValueError(f"Native library differs from APK: {path}")
            libraries.append(path.name)
    if "libmmkv.so" not in libraries:
        raise ValueError("Theme store is missing libmmkv.so")
    for path in [app, *app.rglob("*")]:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"Unexpected symlink: {path}")
        expected = 0o755 if path.is_dir() else 0o644
        if (metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)) != (0, 0, expected):
            raise ValueError(f"Unexpected ownership or permissions: {path}")
        if os.getxattr(path, "security.selinux").rstrip(b"\0") != b"u:object_r:system_file:s0":
            raise ValueError(f"Unexpected SELinux label: {path}")
    return {"apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
            "native_libraries": sorted(libraries)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system_root", type=Path)
    args = parser.parse_args()
    root = args.system_root.resolve()
    source = root / "my_stock/del-app/KeKeThemeSpace"
    target = root / "system/app/KeKeThemeSpace"
    if not (root / "system/app").is_dir():
        raise ValueError("Expected a mounted system-as-root image")
    if source.exists() and target.exists():
        raise ValueError("Duplicate theme stores; inspect the image before continuing")
    if source.exists():
        before = verify(source)
        # Same-filesystem rename preserves file contents and all metadata.
        source.rename(target)
        assert verify(target) == before
    result = verify(target)
    result.update(package="com.heytap.themestore", location="/system/app/KeKeThemeSpace",
                  original_del_app_removed=not source.exists())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
