# FLUX.3 Klein 生态指南

说明 BSAI FLUX3 ComfyUI 适配包、社区提示词扩写插件与官方「重置大幅优化版」三者如何分工，以及如何串成一条工作流使用。

> English version: [FLUX3_ECOSYSTEM.md](./FLUX3_ECOSYSTEM.md)

## 1. 分工（各司其职）

| 组件 | 角色 | 职责范围 |
|---|---|---|
| **BSAI-FLUX3-ComfyUI**（本仓库，根目录即增强器插件） | 增强与编排层 | 中文优先提示词增强（规则 / Strata 本地 LLM 双引擎）、三档提示词路由、Strata 自动拉起（防重复实例）、Intel XPU / GPU / NPU 适配与一键部署 |
| **kkget/ComfyUI-Flux3-Prompt-Upsampler** | 官方能力实现 | 把官方 BFL `qwen3.5_9b` 上采样器封装为节点：至多 **10 张参考图**、**框坐标（bbox）编辑**（原位 / 移动 / 缩放 / 删除 / 新增）、t2i ↔ i2i 系统提示词自动切换、官方参考图预处理策略 |
| **官方重置大幅优化版**（夸克网盘，本地镜像 `G:\flux3 image(1)`） | 共同新基底 | 新蒸馏模型（bf16 / int8 / base-int8）、原生 FLUX.3 子图工作流、**4–16 步**（替代原 50 步） |
| **kkget/Comfyui-Flux3-promt-Skill** | 提示词方法论（Agent 技能，非节点） | 依据 BFL 官方文档整理的提示词模式：文生图、三视图、角色一致、多图合成、bbox 布局；**只引用方法论、不复制内容**（上游仓库无 LICENSE 文件） |

**原则**：BSAI 不重写 KK 的上采样器节点。两插件功能互补、并列安装；本仓库提供集成工作流与文档。

## 2. 快速决策表

| 需求 | 用哪个 |
|---|---|
| 中文想法 → 图片提示词并出图 | BSAI 增强器（tier 1） |
| 官方 9B 上采样扩写（纯文生图） | Tier 2 原生 `TextGenerate` 工作流（无需额外插件） |
| **参考图 + 框坐标编辑图片** | KK `FLUX.3 Prompt Upsampler`（10 图 + bbox） |
| 中文增强 + 多图编辑一条龙 | `workflows/flux3_klein_edit_bsai_x_kk.json`（本仓库） |
| 最快 / 最新权重 | 官方重置蒸馏模型，4–16 步（见第 5 节） |

## 3. 前置条件

1. **BSAI 包**：将本仓库整体 clone 到 `ComfyUI/custom_nodes/`（仓库根即插件），重启 ComfyUI。
2. **KK 插件**：`https://github.com/kkget/ComfyUI-Flux3-Prompt-Upsampler` 克隆到 `ComfyUI/custom_nodes/`，重启（Apache-2.0，无额外 pip 依赖）。节点名 `FLUX.3 Prompt Upsampler`，分类 `FLUX.3/text`。
3. **模型**（基础链路本机已有；新重置权重下载中）：

| 位置 | 文件 |
|---|---|
| `models/text_encoders/` | `qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors`（KK 节点必需） |
| `models/text_encoders/` | `qwen3vl_4b_int8_convrot.safetensors`（提示词编码） |
| `models/vae/` | `flux2-vae.safetensors` |
| `models/diffusion_models/Flux3/` | `flux3_image_klein_int8_convrot.safetensors`（Base，50 步）或 `flux3_image_klein_sd_int8_convrot.safetensors`（蒸馏，16 步） |

## 4. 集成工作流（BSAI × KK）

`workflows/flux3_klein_edit_bsai_x_kk.json`：

```
中文编辑需求
   │
   ▼
BSAI_FLUX3_PromptEnhancer (engine=strata_local, zh) ──positive──▶ FLUX.3 Prompt Upsampler (KK)
                                                                     │ clip = qwen3.5_9b（官方上采样器）
   LoadImage（参考图）─────────────────────────────────────────────▶ images.image0
                                                                     ▼
                                                                  caption
                                                                     │
                                                                     ▼
                                                      CLIPTextEncode (positive) ──▶ ReferenceMultiLatent
   LoadImage（参考图）────────────────────────────────────────────────────────────▶ images.image0
                                                                                     ▼
                                                                             KSampler(50 步, CFG 3.5)
                                                                                     ▼
                                                                             VAEDecode → SaveImage
```

使用方法：

1. 在 ComfyUI 中导入该 JSON（需同时安装 BSAI 与 KK 插件）。
2. 替换 `LoadImage` 中的参考图。
3. 在增强器里填写中文编辑需求（选 `strata_local` 会自动拉起 Strata 后台，绝不产生第二个实例）。
4. 运行。`PreviewAny` 在采样前展示官方上采样器扩写后的完整 caption。

进阶——10 图 / 框坐标编辑：

- 打开 KK 官方示例 `image_flux3_klein_edit_10refs_bbox.json`（KK 仓库 `examples/`，本地夸克下载包亦有镜像）。
- 把本工作流增强器的 `positive` 输出接入其中 `Flux3PromptUpsampler.prompt` 输入，再按 KK README 用 `CreateBoundingBoxes` 画布 + `FLUX.3 Edit Prompt + Box Coordinates` 操作。

## 5. 官方重置大幅优化版（新基底）

来源：B 站视频描述中的官方更新版本链接 `https://pan.quark.cn/s/797537943335`；本地镜像 `G:\flux3 image(1)`（工作流 JSON 已齐全，模型文件下载中）。

变化要点（依据随附工作流与视频）：

- **新蒸馏模型**——`flux3-image-klein-base-int8-convrot-2b0a0cd339b4`、`flux3_image_klein_bf16-a5a072738617`、`flux3_image_klein_int8_convrot-aee2b5344d1a`（另有 `qwen3vl_4b_bf16` 文本编码器）。
- **原生 FLUX.3 子图工作流**——`image_flux3_klein_distilled_t2i新.json` 等使用内置 FLUX.3 节点（uuid 子图）+ `ResolutionSelector` + `CreateBoundingBoxes`；随附注释明确 **"try 4-16 steps"**。
- **迭代更快**——蒸馏模型 4–16 步替代 50 步默认。

下载完成后接入 BSAI 流程：

1. 新权重按随附目录放入 `models/`（`diffusionmodels/` → `models/diffusion_models/Flux3/`，`text_encoders/` → `models/text_encoders/`）。
2. 先跑一次官方蒸馏工作流验证；再把任意 BSAI 工作流的 `UNETLoader` 换为新文件、`KSampler` steps 改为 4–16（蒸馏模型 CFG≈1）。
3. 实测数据将在本地验证后补充到本文档（RTX 5090 Laptop 24G）。

## 6. 许可与引用边界

- **KK 上采样器插件**：Apache-2.0——可安全安装、使用、引用；BSAI 仓库**不内置**其代码。
- **KK Skill 仓库**：**无 LICENSE 文件**——不得将其内容复制进本仓库，仅按链接引用（本文档中的方法论摘要均依据 BFL 官方文档自行撰写）。
- **FLUX 3 Image Klein 权重**：受 [FLUX Kommunity License v1.0](../adapter/_license/LICENSE.md) 约束——不包含在本仓库内，通过适配脚本 / 官方镜像下载。
- **官方上采样器权重**（`qwen3.5_9b_flux3_prompt_upsampler_*`）：按 BFL 模型卡为 Apache-2.0。

## 7. BSAI 明确不做的事

- 不重写多图 / 框坐标编辑（KK 插件已覆盖）。
- 不打包模型权重。
- 不复制 KK Skill 内容（上游无 LICENSE）。
- 增强器节点保持英文 UI / PR 合规；中文支持位于搜索别名与中文文档。
