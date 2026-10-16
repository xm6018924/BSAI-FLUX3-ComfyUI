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
└── custom_nodes/
    └── BSAI-FLUX3-Enhancer/          # ComfyUI 提示词增强器节点
        ├── README.md / README.zh-CN.md
        └── workflows/
            ├── flux3_klein_t2i_enhanced_api.json    # 第1档：增强器（rule / Strata LLM）
            └── flux3_klein_t2i_upsampler_api.json   # 第2档：官方上采样器
```

## 快速开始

1. 下载权重（约 30GB，可续传）：`adapter/01_下载FLUX3权重.bat`，完成后自动跑完整性检查（8/8）。
2. 启动：
   - NVIDIA：`adapter/02_启动FLUX3_5090.bat` → http://127.0.0.1:8193
   - Intel Arc/核显：`adapter/03_启动FLUX3_IntelXPU.bat` → http://127.0.0.1:8194
3. 安装增强器：把 `custom_nodes/BSAI-FLUX3-Enhancer/` 复制到 `ComfyUI/custom_nodes/`，重启后导入示例工作流即可。

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
- FLUX3 Klein / Qwen-Image 2.1 / MiniMax H3 三套配方；输出 `positive` + `negative`。
- UI 为英文（符合 ComfyUI 自定义节点规范），中文体验由搜索别名 + README.zh-CN.md 提供。

## 三档提示词管线（同一句提示词，三套工作流）

| 档位 | 工作流 | 行为 |
|---|---|---|
| 0. 原始 | `adapter/workflows/flux3_klein_t2i_api.json` | 提示词原样进 FLUX3 |
| 1. 增强器 | `custom_nodes/BSAI-FLUX3-Enhancer/workflows/flux3_klein_t2i_enhanced_api.json` | rule_only=原文+质量词缀；auto/strata_local=Strata LLM 电影感扩写（中文优先） |
| 2. 官方上采样器 | `custom_nodes/BSAI-FLUX3-Enhancer/workflows/flux3_klein_t2i_upsampler_api.json` | ComfyUI 原生 `TextGenerate` + BFL `qwen3.5-9B`：短请求→完整英文场景描述 |

第 2 档只用 ComfyUI 0.41 原生节点（无需额外插件）：上采样器权重
`qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors`（~9.1GB，`models/text_encoders/`）
被识别为 `QWEN35_9B`，用 `CLIPLoader` + `type=flux3` 加载，`TextGenerate` 自回归扩写后接入正片。
5090 Laptop 24G 实测：仅扩写首跑 ≈249s（冷加载为主），1024² 全流程首跑 ≈453s。
上采样器模型许可为 Apache-2.0。也可 1→2 串联（增强器 `positive` → `TextGenerate.prompt`）。

## 许可

- 本仓库代码：MIT（`LICENSE`）。
- FLUX 3 Image Klein 权重**不内置**，由 [FLUX Kommunity License v1.0](adapter/_license/LICENSE.md) 管辖（免费商用需年收入 < 500 万美元；禁止用 FLUX 输出训练/蒸馏同类图像模型；再分发须附许可与 Attribution Notice）。下载脚本指向非 gated 镜像，再分发前请先核对许可。

> Intel XPU/核显链路已备好（Arc 目标），但本机为 5090 + Arc 核显，Arc 独显实测待补（见 `adapter/README.md`）。
