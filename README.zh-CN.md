# BSAI FLUX3 ComfyUI 工具包

面向 BSAI ComfyUI 发行版的 **FLUX 3 Image Klein**（5.6B open weights，Black Forest Labs）一键部署与配套工具，外加一个**中文优先的提示词增强器**自定义节点。

> English docs: [README.md](./README.md)

## 仓库结构

```
BSAI-FLUX3-ComfyUI/
├── adapter/                          # Intel XPU / GPU / NPU + NVIDIA 适配包
│   ├── BSAI-FLUX3_README.md         # 适配包说明（硬件档位/许可/待办）
│   ├── 01_下载FLUX3权重.bat          # 权重下载（hf-mirror + aria2 断点续传）
│   ├── 02_启动FLUX3_5090.bat         # NVIDIA CUDA 启动（端口 8193）
│   ├── 03_启动FLUX3_IntelXPU.bat     # Intel XPU/核显 启动（端口 8194，Arc 就绪）
│   ├── bsai_flux3_check.py           # 模型完整性检查（退出码 0 = 就绪）
│   ├── run_flux3_test.py             # 实测驱动：提交→计时→显存峰值
│   ├── workflows/flux3_klein_t2i_api.json            # 第0档：原始提示词
│   ├── workflows/flux3_klein_t2i_upsampler_api.json  # 第2档：官方上采样器
│   ├── _license/                     # FLUX Kommunity License v1.0 存档
│   ├── 许可核对报告_FLUX_Kommunity_License.md
│   └── 实测报告_5090_FLUX3_Klein.md  # RTX 5090 Laptop 实测
├── docs/                             # 生态与集成指南
│   ├── FLUX3_ECOSYSTEM.md            # BSAI x KK x 官方重置版（英文）
│   └── FLUX3_ECOSYSTEM.zh-CN.md      # 同上（中文）
├── workflows/                       # 示例工作流（ComfyUI 中导入使用）
│   ├── flux3_klein_t2i_enhanced_api.json    # 第1档：增强器（rule / Strata LLM）
│   ├── flux3_klein_t2i_upsampler_api.json   # 第2档：官方上采样器
│   └── flux3_klein_edit_bsai_x_kk.json      # BSAI x KK 协同（图像编辑）
└── __init__.py / enhancer.py / router.py / strata_*.py / test_enhancer.py
                                     # 仓库根即 ComfyUI 插件本体
                                     # （分类 BSAI/FLUX3，节点 "BSAI FLUX3 Prompt Enhancer"）
```

## 快速开始

1. 下载权重（约 30GB，可续传）：`adapter/01_下载FLUX3权重.bat`，完成后自动跑完整性检查（8/8）。
2. 启动：
   - NVIDIA：`adapter/02_启动FLUX3_5090.bat` → http://127.0.0.1:8193
   - Intel Arc/核显：`adapter/03_启动FLUX3_IntelXPU.bat` → http://127.0.0.1:8194
3. 安装增强器：将本仓库整体 clone 到 `ComfyUI/custom_nodes/`（仓库根即插件，根目录含 `__init__.py`），重启 ComfyUI 后从 `workflows/` 导入示例工作流即可。

## NInfer 引擎（提示词增强用，可选）

`ninfer-serve.exe` 是 500MB+ 的预编译二进制且不可再分发，**不在本仓库里**（`engine/` 已被 .gitignore 排除）。缺失时增强器自动退回规则引擎，不影响出图；需要 NInfer 提速时，按以下顺序自动查找引擎目录：

1. 环境变量 `BSAI_NINFER_ENGINE_DIR` 指向的 `engine/` 目录；
2. 本插件自己的 `engine/`（手动放置，见下）；
3. 同目录下 `ComfyUI-AIManzi-MultimodalPrompt/engine/`（上游来源，装了该插件即可直接用）；
4. `custom_nodes/*/engine/` 中任何已含 `ninfer-sm120|sm89/ninfer-serve.exe` 的插件。

引擎需要的 `runtime/`、`ninfer-sm120/`（RTX 50 系）、`ninfer-sm89/`（RTX 40 系）三个子目录要放在一起。模型放 `ComfyUI/models/LLM/**/*.ninfer`。

## 本机实测（RTX 5090 Laptop 24G，蒸馏版 INT8，1024² / 16 步）

| 配置 | 总耗时（含冷加载） | 热跑 | 显存峰值 |
|---|---|---|---|
| INT8 蒸馏 | 98.3 s | **35.6 s** | ~13.8 GB |
| BF16 蒸馏 | 190.1 s | — | ~19.4 GB |
| INT8 + 低显存模式（约 9.4G 预算） | 126.1 s | — | **~10.4 GB** |

"8G 显存能跑"对 INT8 蒸馏版成立（需动态卸载）；真 8G 卡建议从 512–768px 起步。详见 `adapter/实测报告_5090_FLUX3_Klein.md`。

## 提示词增强器

节点 `BSAI FLUX3 Prompt Enhancer (CN-First)`（分类 `BSAI/FLUX3`）：
- 中文优先：一句中文粗略想法 → 可直接出图的详细提示词。
- 双引擎：本地 Strata LLM（127.0.0.1:8080，复用 BSAI-LLM-Strata）在线走 LLM，离线自动降级规则引擎，永不出错。
- Strata 自动启动为"复用优先"：只要已有 Strata 实例（模型就绪 / 8080 端口已监听 / 引擎进程加载中 / **新版 Manager 已运行在 8081**），节点只等待、绝不重复拉起第二个实例；仅在完全无实例时才自动启动。新版架构（BSAI-LLM-Strata `bsai_model_manager.py`，Manager=8081 / 引擎=8080）下，节点会自动通过 `POST /api/switch` 触发模型加载并等待引擎就绪——无需再手动在 Web UI 里选模型。
- FLUX3 Klein **基础版 / step-distilled 蒸馏版**（配合 Qwen3-VL-4B 文本编码器 + Flux2 VAE）/ Qwen-Image 2.1 **原版 / Turbo 8步蒸馏版** / MiniMax H3 五套配方；输出 `positive` + `negative`。`target_model` 下拉直接选配方：`flux3_klein`=基础版、`flux3_klein_sd`=蒸馏版、`qwen_image_2.1_turbo`=8步加速档。
- UI 为英文（符合 ComfyUI 自定义节点规范），中文体验由搜索别名 + README.zh-CN.md 提供。

## 检查点变体（与 ComfyUI 0.41 原生 FLUX.3 支持对齐）

| 变体 | 文件（`models/diffusion_models/`） | 典型用途 |
|---|---|---|
| 基础版（INT8 / BF16） | `flux3_image_klein_int8_convrot.safetensors` / `flux3_image_klein_bf16.safetensors` | 全质量出图，LoRA/微调底座 |
| 蒸馏版（INT8 / BF16） | `flux3_image_klein_sd_int8_convrot.safetensors` / `flux3_image_klein_sd_bf16.safetensors` | 快速出图，4–16 步 |

两种变体均用 `UNETLoader` 加载（自动识别为 FLUX3）；文本编码器 `CLIPLoader` + `qwen3vl_4b_*` + `type=flux3`；VAE 用 `flux2-vae.safetensors`。`bsai_flux3_check.py` 会检查全部 4 个扩散模型变体 + Qwen3-VL-4B + Flux2 VAE；`01_下载FLUX3权重.bat` 已同时下载基础版与蒸馏版权重。

## 三档提示词管线（同一句提示词，三套工作流）

| 档位 | 工作流 | 行为 |
|---|---|---|
| 0. 原始 | `adapter/workflows/flux3_klein_t2i_api.json` | 提示词原样进 FLUX3 |
| 1. 增强器 | `workflows/flux3_klein_t2i_enhanced_api.json` | rule_only=原文+质量词缀；auto/strata_local=Strata LLM 电影感扩写（中文优先） |
| 2. 官方上采样器 | `workflows/flux3_klein_t2i_upsampler_api.json` | ComfyUI 原生 `TextGenerate` + BFL `qwen3.5-9B`：短请求→完整英文场景描述 |
| 3. 图像编辑（BSAI × KK） | `workflows/flux3_klein_edit_bsai_x_kk.json` | 中文增强 → KK 官方 9B 扩写 → 参考图编辑（需安装 kkget 插件） |

第 2 档只用 ComfyUI 0.41 原生节点（无需额外插件）：上采样器权重
`qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors`（~9.1GB，`models/text_encoders/`）
被识别为 `QWEN35_9B`，用 `CLIPLoader` + `type=flux3` 加载，`TextGenerate` 自回归扩写后接入正片。
5090 Laptop 24G 实测：仅扩写首跑 ≈249s（冷加载为主），1024² 全流程首跑 ≈453s。
上采样器模型许可为 Apache-2.0。也可 1→2 串联（增强器 `positive` → `TextGenerate.prompt`）。

## FLUX.3 生态与 KK 集成

与社区上采样器插件、官方「重置大幅优化版」的分工，完整指南见 **[docs/FLUX3_ECOSYSTEM.zh-CN.md](./docs/FLUX3_ECOSYSTEM.zh-CN.md)**：

- **BSAI 增强器** = 增强与编排（中文优先、Strata、自动拉起、Intel 适配）。
- **kkget/ComfyUI-Flux3-Prompt-Upsampler**（Apache-2.0，并列安装）= 官方能力实现：至多 10 张参考图 + 框坐标编辑。
- **官方重置版**（视频描述中的夸克网盘链接）= 新蒸馏模型、原生 FLUX.3 子图工作流、**4–16 步**。
- `workflows/flux3_klein_edit_bsai_x_kk.json` 串起全链路：中文需求 → BSAI 增强器 → KK 官方 9B 扩写 → 参考图编辑。

许可边界：KK 插件为 Apache-2.0（引用不内置）；KK Skill 仓库**无 LICENSE**（仅链接引用）；FLUX.3 权重仍受 FLUX Kommunity License v1.0 管辖。

## 许可

- 本仓库代码：MIT（`LICENSE`）。
- FLUX 3 Image Klein 权重**不内置**，由 [FLUX Kommunity License v1.0](adapter/_license/LICENSE.md) 管辖（免费商用需年收入 < 500 万美元；禁止用 FLUX 输出训练/蒸馏同类图像模型；再分发须附许可与 Attribution Notice）。下载脚本指向非 gated 镜像，再分发前请先核对许可。

> Intel XPU/核显链路已备好（Arc 目标），但本机为 5090 + Arc 核显，Arc 独显实测待补（见 `adapter/README.md`）。
