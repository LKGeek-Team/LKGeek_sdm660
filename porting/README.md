# 小米 6X / wayne：6.12 移植与 Android 14 构建

当前阶段：**4.19 基线编译完成，6.12 Image 编译进行中；尚无可刷机交付物或真机启动结果。**

用户目标是为小米 6X 升级真实的 Linux 6.12，并同时构建类原生系统。当前按用户要求仅编译内核，Android 14 整包同步和编译已暂停。后续逐项完成 6.12 硬件与 Android 接口移植。仓库根目录仍然是 4.19，实验性 6.12 使用独立源码树；没有修改版本号冒充升级。

## 已确认的源码

| 用途 | 来源与固定版本 |
| --- | --- |
| 原内核 | [scarlet_sdm660](https://github.com/ciallo-0d00721/scarlet_sdm660/tree/3316cb3851478cb1d63cf79b40eea6dc1df8bee4)，Linux 4.19.325 |
| 原版配置 | `arch/arm64/configs/vendor/wayne-oss-perf_defconfig`；包含 OSS 相机和 EROFS，符合所选 ROM 的配置方向，尚待整机验证 |
| 实验内核 | [Linux v6.12](https://github.com/torvalds/linux/tree/adc218676eef25575469234709c2d87185ca223a)；初始固定版本，后续仍需合入 6.12.y 安全修复 |
| ROM manifest | [LineageOS-wayne/android](https://github.com/LineageOS-wayne/android/tree/0a964c35d486402caac9842d93e1634ddfc840e9)，Android 14 / LineageOS 21 社区源码 |
| ROM device | [wayne device tree](https://github.com/LineageOS-wayne/android_device_xiaomi_wayne/tree/e8f24a6736237fa8afde2986cf08e32717f9f508) |
| ROM vendor | [wayne vendor tree](https://github.com/LineageOS-wayne/android_vendor_xiaomi_wayne/tree/8a2b1eab1f9e1f12f58eb525a7458863b09172dc)，使用其现有二进制组件；硬件兼容性尚未验证 |

社区组织名含有 LineageOS，并不表示这是 LineageOS 官方支持或官方构建。

## Work 构建结果（2026-10-22）

本次构建使用 PVE Work 虚拟机：Ubuntu 24.04、24 vCPU、约 8 GiB RAM，Clang/LLD 18.1.3 和 AArch64/ARM GCC 13。通过 VS Code Remote SSH 打开 Linux 上的完整源码目录；当前无需安装 WSL。

4.19 基线构建退出码 0，产出 SHA256：

```text
e8aa195af4b65ee814a4e55c66da248c43fb8a3bac37999d3a01bceb24767129a  Image.gz-dtb
e837f85052bf72a1d442a7134d110e8d1ed3761be588989f43183871dee94f224  sdm660-mtp-wayne.dtb
```

DSH 完成遗留 KernelSU 引用的最小清理，主助手审查后在真实 Kbuild 中验证通过。`vendor-4.19/0001-remove-stale-kernelsu.patch` 保存同一修复，构建脚本自动应用到固定旧基线并检查重复执行。

Linux 6.12 已完成实际 Kbuild 配置生成，44 个配置片段选项保留检查通过，Wayne DTB 已由 Kbuild 生成；完整 Image 尚在编译。上述产物尚未做真机启动或完整设备树 schema 检查。

## 较早的离线验证结果

- 在 Windows 上以 pcpp 1.30 预处理、DTC 1.8.1 编译了实验性 Wayne DTB；输出 45,359 字节。
- 完整遍历了 DTB 的二进制节点和属性结构，343 个节点，以及机型、SoC ID、串口、eMMC、ramoops 和 CDSP 保留区的 6 项检查通过。结果见 `linux-6.12/dtb-validation.json`。
- DTC 有一条继承自上游 `pm660.dtsi` 的 `avoid_unnecessary_addr_size` 警告，位于 PMIC@1；没有隐藏它。尚未执行完整 `dtbs_check`。
- PowerShell、Bash、Python 和任务 JSON 做过语法检查。内核 Kbuild 结果见上一节；Android 整包构建尚未执行。
- 44 个 6.12 配置片段符号已确认存在于上游 Kconfig；在 Work 的实际 Kbuild 配置中，44 个选项保留检查已通过。移植注册和 ROM 配置 include 的重复执行检查、本地编辑保护检查、损坏 DTB 拒绝检查均已通过。
- 对比 OSS 配置：680 个启用的 vendor 配置符号中，278 个名称未在 v6.12 Kconfig 中找到，见 `linux-6.12/migration-inventory.json`。这包括重命名、删除或下游专用选项，不能据此认定有 278 个独立驱动故障；同名也不代表 ABI 兼容。

## 可选的本机 WSL 环境（本次未使用）

初始检查：Windows、12 个逻辑处理器、约 16 GB RAM，C: 约 25 GB 可用，D: 约 940 GB 可用；没有 WSL/Linux 编译器。VS Code 已打开仓库，WSL 扩展已安装。

Windows 不适合直接检出完整内核：本次遇到 `aux.c` 保留名和 26 个大小写冲突路径。Windows 视图使用本地 sparse-checkout 暂时排除这些路径，没有删除 Git 中的源文件。实际构建会从 Git 对象在 Linux 文件系统重新检出全部路径与符号链接。

在管理员 PowerShell 运行 `tools/wayne/install-wsl.ps1`，按安装器要求手动重启并完成 Ubuntu-24.04 的用户创建。脚本不会自动重启系统。[微软安装说明](https://learn.microsoft.com/en-us/windows/wsl/install)。

**整包 ROM 开始同步前，需要把 Ubuntu-24.04 的虚拟磁盘放到 D:。** 当前 C: 余量不足以容纳整包源码。安装结束后先核对新安装的 WSL 版本与存储位置，再用该版本支持的迁移命令处理；不要直接在资源管理器移动正在使用的 VHDX，也不要注销发行版。Windows 任务会检查发行版所在物理盘的空间，Linux 任务也检查可用空间。

ROM 初次同步要求 400 GiB 可用空间。当前 AOSP 文档给出的整机环境基线为 400 GB 磁盘和 64 GB RAM；本机低于其内存要求，Android 14 的实际构建需结合交换空间、较低并发和构建日志调节，耗时可能很长。[AOSP 环境要求](https://source.android.com/docs/setup/start/requirements)。

## VS Code 任务

当前应在 VS Code Remote SSH 中打开 Work 的 vendor 源码目录，通过“终端 → 运行任务”选择内核任务。以下 WSL 安装与打开任务仅供可选本机构建：

1. `Wayne: setup Linux build environment`
2. `Wayne: open full source in WSL`
3. `Wayne: build 4.19 baseline`，或 Ctrl+Shift+B
4. `Wayne: prepare 6.12 config`
5. `Wayne: compile experimental 6.12 DTB`
6. `Wayne: compile experimental 6.12 image`

原版源码位于 Linux 的 `~/wayne-kernel/vendor`，6.12 源码位于 `~/wayne-kernel/linux-6.12`，各自的输出目录在 `~/wayne-kernel/out-*`。编译日志自动保存在 `~/wayne-kernel/logs`。Windows 源码视图中的后续代码修改不会自动同步到 Linux 副本；开始实际开发后应在 Linux / Remote SSH 中编辑完整源码。

Linux 终端也可执行：

```bash
export WAYNE_WORK_ROOT="$HOME/wayne-kernel"
bash tools/wayne/build.sh setup
bash tools/wayne/build.sh baseline
bash tools/wayne/build.sh dtbs-6.12
bash tools/wayne/build.sh image-6.12
```

可用 `JOBS=2` 限制内核并发；也可用 `WAYNE_WORK_ROOT` 指向另一个 Linux 文件系统目录。请勿指向 `/mnt/c` 或 `/mnt/d`。

在 WSL 就绪前，Windows DTB 检查可复现如下（需要已准备的 DTC、pcpp 和上游稀疏检出缓存）：

```powershell
python tools/wayne/dtb-windows.py --source D:/kernel-cache/linux-6.12-review --dtc D:/kernel-cache/dtc-windows/ucrt64/bin/dtc.exe --python-tools D:/kernel-cache/python-tools --output D:/kernel-cache/linux-6.12-review/sdm660-xiaomi-wayne.dtb
```

该检查不执行 Kbuild。DTC 来自 [MSYS2 UCRT64 包](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-dtc)，1.8.1-1 包 SHA256 为 `0f3c4df43133b99e040f7d42666e36e50c9aea2f59a494e0aad3b475f3fdd32d`；依赖 libyaml 0.2.5-2 包 SHA256 为 `bf4c28a3a92a46db3c809b0789aef731ae9a0c4283db368c7e8624550fed07f3`，均已核对。

ROM 任务（当前已暂停，未同步和编译）：

1. `Wayne ROM: setup Android 14 build environment`
2. `Wayne ROM: sync Android 14 sources`
3. `Wayne ROM: build Android 14 baseline (4.19)`

ROM 工作目录为 `~/wayne-android14`，默认编译并发为 2；可通过 `WAYNE_ROM_ROOT` 和 `JOBS` 调整。同步会保存 `wayne-resolved-manifest.xml`，用于记录所有实际项目提交。`porting/android14/wayne.xml` 替换社区 manifest 的内核项目为用户仓库，并固定 device/vendor 的提交；`ScarletKernel.mk` 选择用户内核中真实存在的 OSS defconfig。

ROM 脚本当前构建的是 **4.19 的 Android 14 基线**。6.12 尚无完整 Android vendor 适配，不能把初始 DTB 加一个内核 Image 就视作可用整包。现有设备树还假定改造后的动态分区布局；安装前必须核对真机分区，当前脚本没有执行刷机或重新分区。

## 6.12 后续验收

实验设备树目前只覆盖串口、电源键、eMMC 供电、显示缓冲保留、CDSP 保留区和 ramoops。沿用上游 SoC/PMIC 描述并不代表这些功能已在 Wayne 实机正常运行。

| 阶段 | 必须取得的结果 | 当前状态 |
| --- | --- | --- |
| 原版构建 | 4.19 `Image.gz-dtb`、Wayne DTB，固定配置和工具链 | Work 编译完成，未真机测试 |
| ROM 基线 | Android 14 整包完成构建，原内核可启动 | manifest/任务已准备，未同步整包 |
| 新内核编译 | Kconfig 选项保留检查、Kbuild DTB 和 Image、设备树 schema 检查 | Work 配置和 Kbuild DTB 通过，Image 编译中，schema 待做 |
| 初始启动 | 核实 RAM/保留区、boot header/偏移，串口或 ramoops 日志可采集 | 未真机测试 |
| 核心硬件 | 显示、触摸、USB、存储、调频/温控、充电与电池 | 未完成 |
| Android 接口 | ION/DMA-BUF、KGSL/DRM、MDSS、相机、音频、QSEECom、SELinux、init/fstab | 未完成 |
| 通信与外设 | Wi-Fi、蓝牙、基带、通话、数据、GPS、传感器、指纹 | 未完成 |
| 交付 | 可启动的 6.12 ROM、回归测试、真实内核版本与日志、可复现的构建清单 | 未完成 |

原有专有 HAL 所需的接口在 6.12 上必须逐项保留、适配或替换。编译成功不等同于手机正常启动；能够启动也不等同于相机、通话、充电和待机都已通过验证。
