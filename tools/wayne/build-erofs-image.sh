#!/usr/bin/env bash
# Build one filesystem image. Does not package or flash a ROM.
set -euo pipefail

part=${1:?usage: build-erofs-image.sh system|vendor SOURCE_ROOT OUTPUT_IMAGE}
source_root=${2:?source root}
output=${3:?output image}
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
mkfs=${EROFS_MKFS:-$repo_root/.third-update-artifacts/erofs-utils-src/mkfs/mkfs.erofs}
fsck=${EROFS_FSCK:-$repo_root/.third-update-artifacts/erofs-utils-src/fsck/fsck.erofs}

test -d "$source_root"
test -x "$mkfs"
test -x "$fsck"
test ! -e "$output" || { echo "Refusing to overwrite $output" >&2; exit 1; }
args=(-z lz4hc,level=12 -E legacy-compress --workers=2)
case "$part" in
    system)
        # Reject obsolete boot-time compilation even when reusing an old tree.
        system_tree="$source_root"
        if [ -d "$source_root/system" ]; then system_tree="$source_root/system"; fi
        for removed in bin/lkgeek-ui-dexopt.sh etc/init/lkgeek_ui_dexopt.rc; do
            if [ -e "$system_tree/$removed" ] || [ -L "$system_tree/$removed" ]; then
                echo "Remove obsolete boot dexopt file before building: $system_tree/$removed" >&2
                exit 1
            fi
        done
        args+=(-C 32768 --max-extent-bytes=65536
               --compress-hints="$script_dir/erofs-performance.hints")
        ;;
    vendor)
        args+=(-C 4096 --max-extent-bytes=131072)
        ;;
    *) echo 'Expected system or vendor' >&2; exit 1 ;;
esac
"$mkfs" "${args[@]}" "$output" "$source_root"
"$fsck" --extract "$output"
echo 'Image decoded successfully. Verify complete file contents/metadata before packaging.'
