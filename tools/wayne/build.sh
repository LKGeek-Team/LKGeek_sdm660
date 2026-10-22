#!/usr/bin/env bash
set -euo pipefail

mode=${1:-baseline}
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
if [[ $mode == dependencies ]]; then
    (( EUID == 0 )) || { printf 'Run dependency installation as root.\n' >&2; exit 1; }
    apt-get update
    apt-get install -y build-essential git bc bison flex libssl-dev libelf-dev \
        libncurses-dev python3 python-is-python3 rsync cpio kmod device-tree-compiler \
        clang-18 lld-18 llvm-18 gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi
    exit 0
fi
work_root=${WAYNE_WORK_ROOT:-"$HOME/wayne-kernel"}
vendor="$work_root/vendor"
upstream="$work_root/linux-6.12"
baseline_sha=3316cb3851478cb1d63cf79b40eea6dc1df8bee4
# Linux v6.12 is a fixed starting point, not a claim of current security fixes.
upstream_ref=v6.12
jobs=${JOBS:-4}

die() { printf '%s\n' "$*" >&2; exit 1; }
[[ $(uname -s) == Linux ]] || die 'Run this script in Linux / WSL.'
case "$work_root" in /mnt/*) die 'Use the Linux filesystem for WAYNE_WORK_ROOT, not /mnt/*.' ;; esac
mkdir -p "$work_root/logs"
log="$work_root/logs/$mode-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
exec > >(tee "$log") 2>&1
trap 'rc=$?; if ((rc)); then printf "Task failed (%s). Log: %s\n" "$rc" "$log" >&2; fi' EXIT

deps() {
    for tool in git make python3 flex bison aarch64-linux-gnu-gcc arm-linux-gnueabi-gcc clang ld.lld llvm-ar; do
        command -v "$tool" >/dev/null || die "Missing $tool. Run the setup task first."
    done
}

if [[ $mode == setup ]]; then
    export PATH="/usr/lib/llvm-18/bin:$PATH"
    (deps) || sudo bash "$repo_root/tools/wayne/build.sh" dependencies
    if [[ ! -d $vendor ]]; then
        # Clone Git objects, not the sparse Windows worktree: restore case-sensitive paths and symlinks.
        git clone --no-hardlinks "$repo_root" "$vendor"
        git -C "$vendor" switch -c build/wayne-baseline "$baseline_sha"
    fi
    [[ $(git -C "$vendor" rev-parse HEAD) == "$baseline_sha" ]] || \
        die "Existing vendor checkout has a different HEAD. Inspect it instead of resetting it."
    mkdir -p "$vendor/tools/wayne" "$vendor/.vscode" "$vendor/porting"
    if [[ $(realpath "$repo_root") != "$(realpath "$vendor")" ]]; then
        rsync -a "$repo_root/tools/wayne/" "$vendor/tools/wayne/"
        rsync -a "$repo_root/.vscode/" "$vendor/.vscode/"
        rsync -a "$repo_root/porting/" "$vendor/porting/"
    fi
    printf 'Ready: %s\nOpen this Linux checkout in VS Code with the open-linux task.\n' "$vendor"
    exit 0
fi

export PATH="/usr/lib/llvm-18/bin:$PATH"
deps
[[ $jobs =~ ^[1-9][0-9]*$ ]] || die 'JOBS must be a positive integer.'

if [[ $mode == baseline ]]; then
    [[ -f $vendor/Makefile ]] || die 'Run setup before the baseline build.'
    python3 "$repo_root/tools/wayne/apply-vendor-fixes.py" "$vendor" \
        "$repo_root/porting/vendor-4.19/0001-remove-stale-kernelsu.patch"
    out="$work_root/out-vendor"
    defconfig=${WAYNE_DEFCONFIG:-vendor/wayne-oss-perf_defconfig}
    args=(-C "$vendor" O="$out" ARCH=arm64 LLVM=1 LLVM_IAS=1 \
        CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- \
        CLANG_TRIPLE=aarch64-linux-gnu-)
    make "${args[@]}" "$defconfig"
    make "${args[@]}" -j"$jobs" Image.gz-dtb dtbs
    test -s "$out/arch/arm64/boot/Image.gz-dtb"
    test -s "$out/arch/arm64/boot/dts/vendor/qcom/sdm660-mtp-wayne.dtb"
    sha256sum "$out/arch/arm64/boot/Image.gz-dtb" \
        "$out/arch/arm64/boot/dts/vendor/qcom/sdm660-mtp-wayne.dtb"
    printf 'Compiled baseline only; Android 14 boot and hardware remain untested.\n'
    exit 0
fi

case "$mode" in prepare-6.12|dtbs-6.12|image-6.12) ;; *) die "Unknown task: $mode" ;; esac
if [[ ! -d $upstream ]]; then
    cached_upstream="$repo_root/../wayne-kernel-cache/linux-6.12.git"
    if git --git-dir="$cached_upstream" rev-parse --verify "$upstream_ref^{commit}" >/dev/null 2>&1; then
        git clone --no-hardlinks --branch "$upstream_ref" "$cached_upstream" "$upstream"
    else
        git clone --depth 1 --branch "$upstream_ref" --single-branch \
            https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git "$upstream"
    fi
fi
[[ -f $upstream/Makefile ]] || die 'Incomplete 6.12 checkout; inspect it before retrying.'
python3 "$repo_root/tools/wayne/apply-port.py" "$upstream" "$repo_root/porting/linux-6.12"
out="$work_root/out-6.12"
args=(-C "$upstream" O="$out" ARCH=arm64 LLVM=1 LLVM_IAS=1 CROSS_COMPILE=aarch64-linux-gnu-)
make "${args[@]}" defconfig
(cd "$upstream"; ARCH=arm64 LLVM=1 LLVM_IAS=1 CROSS_COMPILE=aarch64-linux-gnu- \
    KCONFIG_CONFIG="$out/.config" bash scripts/kconfig/merge_config.sh -m -O "$out" \
    "$out/.config" "$repo_root/porting/linux-6.12/wayne.config")
make "${args[@]}" olddefconfig
python3 "$repo_root/tools/wayne/check-config.py" "$out/.config" \
    "$repo_root/porting/linux-6.12/wayne.config"
if [[ $mode == prepare-6.12 ]]; then
    printf 'Prepared configuration only. No kernel has been compiled.\n'
    exit 0
fi
make "${args[@]}" -j"$jobs" qcom/sdm660-xiaomi-wayne.dtb
test -s "$out/arch/arm64/boot/dts/qcom/sdm660-xiaomi-wayne.dtb"
if [[ $mode == image-6.12 ]]; then
    make "${args[@]}" -j"$jobs" Image.gz
    test -s "$out/arch/arm64/boot/Image.gz"
    sha256sum "$out/arch/arm64/boot/Image.gz"
fi
sha256sum "$out/arch/arm64/boot/dts/qcom/sdm660-xiaomi-wayne.dtb"
printf 'Experimental 6.12 output only. Boot image packaging, device boot and Android vendor support are incomplete.\n'
