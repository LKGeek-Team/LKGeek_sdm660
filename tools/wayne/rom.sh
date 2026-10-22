#!/usr/bin/env bash
set -euo pipefail
mode=${1:-setup}
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
[[ $(uname -s) == Linux ]] || { printf 'Use Linux / WSL.\n' >&2; exit 1; }
if [[ $mode == dependencies ]]; then
    (( EUID == 0 )) || { printf 'Install dependencies as root.\n' >&2; exit 1; }
    apt-get update
    apt-get install -y repo git-lfs git gnupg flex bison build-essential zip curl \
        zlib1g-dev libc6-dev-i386 libx11-dev lib32z1-dev libgl1-mesa-dev \
        libxml2-utils xsltproc unzip fontconfig python3 python-is-python3 \
        bc ccache libssl-dev libelf-dev rsync lz4 libncurses-dev adb fastboot
    exit 0
fi
rom_root=${WAYNE_ROM_ROOT:-"$HOME/wayne-android14"}
case "$rom_root" in /mnt/*) printf 'Put the ROM tree on the Linux filesystem.\n' >&2; exit 1 ;; esac
jobs=${JOBS:-2}
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { printf 'Invalid JOBS.\n' >&2; exit 1; }
mkdir -p "$rom_root"
cd "$rom_root"
log="$rom_root/wayne-$mode-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
exec > >(tee "$log") 2>&1
trap 'rc=$?; if ((rc)); then printf "ROM task failed (%s): %s\n" "$rc" "$log" >&2; fi' EXIT

if [[ $mode == setup ]]; then
    command -v repo >/dev/null || sudo bash "$repo_root/tools/wayne/rom.sh" dependencies
    printf 'Android 14 workspace: %s\n' "$rom_root"
    printf 'Before syncing: place the WSL virtual disk on D: and reserve at least 400 GiB.\n'
    free -h
    df -h .
    exit 0
fi

case "$mode" in sync|build) ;; *) printf 'Unknown ROM task: %s\n' "$mode" >&2; exit 1 ;; esac
command -v repo >/dev/null || { printf 'Run rom-setup first.\n' >&2; exit 1; }
if [[ $mode == sync ]]; then
    available_kib=$(df -Pk . | awk 'END {print $4}')
    (( available_kib >= 400 * 1024 * 1024 )) || { printf 'Need 400 GiB free for the first ROM sync/build.\n' >&2; exit 1; }
    if [[ ! -d .repo ]]; then
        repo init -u https://github.com/LineageOS-wayne/android.git \
            -b 0a964c35d486402caac9842d93e1634ddfc840e9 --depth=1 --git-lfs
    fi
    manifest_url=$(git -C .repo/manifests remote get-url origin)
    [[ $manifest_url == https://github.com/LineageOS-wayne/android.git ]] || \
        { printf 'This workspace uses another manifest; inspect it before changing it.\n' >&2; exit 1; }
    [[ $(git -C .repo/manifests rev-parse HEAD) == 0a964c35d486402caac9842d93e1634ddfc840e9 ]] || \
        { printf 'Unexpected manifest revision; inspect it before continuing.\n' >&2; exit 1; }
    mkdir -p .repo/local_manifests
    if [[ -f .repo/local_manifests/wayne.xml ]] && \
        ! cmp -s .repo/local_manifests/wayne.xml "$repo_root/porting/android14/wayne.xml"; then
        printf 'Local wayne.xml has edits; refusing to overwrite it.\n' >&2; exit 1
    fi
    cp "$repo_root/porting/android14/wayne.xml" .repo/local_manifests/wayne.xml
    repo sync -c --no-tags --no-clone-bundle --fail-fast -j"$jobs"
    repo manifest -r -o "$rom_root/wayne-resolved-manifest.xml"
    printf 'Sources synced. The ROM has not been built.\n'
    exit 0
fi

test -f build/envsetup.sh
test -f device/xiaomi/wayne/BoardConfig.mk
test -f vendor/xiaomi/wayne/wayne-vendor.mk
test -f kernel/xiaomi/wayne/arch/arm64/configs/vendor/wayne-oss-perf_defconfig
[[ $(git -C kernel/xiaomi/wayne rev-parse HEAD) == 3316cb3851478cb1d63cf79b40eea6dc1df8bee4 ]] || \
    { printf 'Unexpected kernel revision. Review it before building.\n' >&2; exit 1; }
python3 "$repo_root/tools/wayne/apply-rom.py" "$rom_root" "$repo_root/porting/android14"
python3 "$repo_root/tools/wayne/apply-vendor-fixes.py" "$rom_root/kernel/xiaomi/wayne" \
    "$repo_root/porting/vendor-4.19/0001-remove-stale-kernelsu.patch"
# envsetup relies on unset variables; retain pipefail so compilation failures survive tee.
set +u
source build/envsetup.sh
lunch lineage_wayne-userdebug
m -j"$jobs" bacon
set -u
find out/target/product/wayne -maxdepth 1 -name 'lineage-21*.zip' -print
printf 'Compiled Android 14 baseline with 4.19; boot, hardware and installation remain untested.\n'
