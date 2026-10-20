# Built-in theme store repair

The port's `/my_stock/del-app/KeKeThemeSpace` installation can register
`/data/preapps-lib/KeKeThemeSpace/lib` without extracting its native libraries.
ThemeApp then fails to load `libmmkv.so` and crashes during MMKV initialization.

Run `builtin-theme-store.py SYSTEM_ROOT` as root against a writable mounted
system-as-root image before EROFS compression. The script moves the original
APK and its libraries into `/system/app/KeKeThemeSpace`, preserving their
contents and metadata. It checks every packaged ARM64 library against the APK,
including `libmmkv.so`, and rejects duplicate installations or invalid labels.
Running it again validates the existing result without moving anything.

Build EROFS with the existing Wayne-compatible compression settings. Run a
complete decode and compare the mounted output against the patched source with
`compare-ro-trees.py` from the ROM build workspace. Retain the resulting JSON
verification report.

Package the verified image using:

```sh
python3 tools/wayne/repack-theme-rom.py \
  --source-rom SOURCE_ROM.zip \
  --system-image PATCHED_SYSTEM.erofs.img \
  --verification SYSTEM_COMPARE.json \
  --output NEW_ROM.zip
```

The source ZIP must contain the working Wayne recovery installer and its
`manifest.json`, `image-sizes.txt`, and `images.sha256`. The packager updates
those files, verifies all packaged image hashes and ZIP checksums, and retains
unchanged vendor and boot entries. To also package a separately verified kernel,
provide both `--boot-image BOOT.img` and `--kernel-commit COMMIT`.

Existing installations may still use a previously installed `/data/app` update.
Confirm the running package's code and native-library paths when validating the
built-in copy. Preserve user data and retain a rollback before replacing any
installed update. Do not clear theme-store data to work around missing libraries.
