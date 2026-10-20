# Wayne EROFS performance profile

Use `build-erofs-image.sh system SOURCE_ROOT OUTPUT_IMAGE` when rebuilding the
pending system image. This builds a filesystem image only; it does not create a
ROM ZIP or write a device. Vendor retains its existing 4KiB cluster profile.

The system profile keeps the existing LZ4 decoder and legacy-compatible on-disk
features. It changes the default physical cluster from 64KiB to 32KiB and caps
each logical decompression extent at 64KiB rather than 128KiB. Compression hints
select 16KiB clusters for framework code, Launcher, SystemUI and Settings, and
4KiB clusters for frequently faulted rendering/runtime libraries. Retaining LZ4
compression for those libraries avoids the mixed results and space growth seen
with fully uncompressed files. LZ4HC's level controls image construction, not a
different phone-side decompression algorithm.

A 408,019,863-byte sample of ten actual system files was compared using identical
4KiB random offsets through host erofsfuse. Per-file page-cache eviction was
requested before reads, while the image backing cache remained uncontrolled.
The selected profile increased this sample image from 214,814,720 to 224,432,128
bytes (4.5%). All ten files had lower median latency in that run. Full file hashes
and decode checks passed. The average logical extent of libhwui fell from
52,267 to 8,251 bytes. These are host-side results, not Android kernel, eMMC,
application-startup or frame-rate measurements. Full-system size, complete
metadata comparison and on-device performance still need checking at the next
image build. Do not claim a specific phone performance gain from this sample.

`lkgeek-ui-dexopt.sh` and `lkgeek_ui_dexopt.rc` optionally go in `/system/bin` and
`/system/etc/init`, with root:root ownership, 0755/0644 permissions and system_file
labels. They upgrade Launcher and Settings to ART's speed filter at background
priority. They do not force recompilation, touch app data or modify thermal/CPU
limits. Once compiled, subsequent boots only check the filter. Initial selective
compilation can take several minutes; it runs after boot without blocking init.
