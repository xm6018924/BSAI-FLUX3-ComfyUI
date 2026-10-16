# BSAI FLUX3 提示词增强器（中文优先）

面向 **FLUX 3 Image Klein** 的中文优先、轻量提示词增强器 ComfyUI 自定义节点，
同时覆盖 **Qwen-Image 2.1** 与 **MiniMax H3**。

> English docs: [README.md](./README.md)

## 它能做什么

- **中文优先**：输入一句中文粗略想法（如"雨夜霓虹灯下的流浪猫"），输出一段可直接出图的详细图像提示词——以中文为主、混入英文视觉关键词。
- **双引擎、永不出错**：本地 **Strata LLM**（BSAI-LLM-Strata 服务，`127.0.0.1:8080/v1`）在线时用 LLM 扩写；离线时自动降级为内置确定性规则引擎，节点永远有输出。
- **多模型配方**：FLUX3 Klein / Qwen-Image 2.1 / MiniMax H3 各自独立的正负向提示词模板。
- **许可干净**：节点是自有代码 + 自有 LLM，不消费 FLUX 权重或输出，无 FLUX Kommunity License 义务。

## 参数

| 参数 | 说明 |
|---|---|
| `raw_prompt` | 原始想法（多行文本，中文优先） |
| `target_model` | `flux3_klein` / `qwen_image_2.1` / `minimax_h3` |
| `engine` | `auto`（默认，Strata 在线用 LLM、离线降级）/ `strata_local` / `rule_only` |
| `language` | `zh`（默认）/ `en` |
| `max_tokens` / `temperature` | LLM 扩写强度 |
| `negative_hint`（可选） | 追加自定义负面词 |
| 输出 | `positive` + `negative` 双字符串 |

## 安装

1. 把本目录复制（或 clone）到 `ComfyUI/custom_nodes/BSAI-FLUX3-Enhancer/`。
2. 重启 ComfyUI，节点出现在 **BSAI/FLUX3** 分类：**BSAI FLUX3 Prompt Enhancer (CN-First)**。
   - 节点菜单搜索 `提示词增强` / `prompt enhancer` 均可找到（UI 为英文，中文别名辅助搜索）。

无任何 Python 依赖（仅标准库）。

## 使用方法

```
中文提示词 ──▶ BSAI FLUX3 Prompt Enhancer ──▶ positive ──▶ CLIPTextEncode (positive)
                 (engine=auto)             └─▶ negative ──▶ CLIPTextEncode (negative)
```

- FLUX3 蒸馏版 cfg=1.0 时 negative 基本不影响，可只接 positive；Qwen-Image 2.1 / H3 工作流请两路都接。

### 示例工作流

`workflows/flux3_klein_t2i_enhanced_api.json` —— 一个完整的 FLUX 3 Image Klein 蒸馏版（INT8）文生图 API 工作流，已接好增强器：

1. 把 JSON 拖进 ComfyUI（或 File → Open）导入，或直接 POST 到 `/prompt`。
2. 需要以下模型文件（`ComfyUI/models/` 下）：

| 文件 | 路径 | 体积 |
|---|---|---|
| `flux3_image_klein_sd_int8_convrot.safetensors` | `models/diffusion_models/` | ~5.4 GB |
| `qwen3vl_4b_int8_convrot.safetensors` | `models/text_encoders/` | ~4.5 GB |
| `flux2-vae.safetensors` | `models/vae/` | ~0.3 GB |

官方 HF 仓库为 gated，请通过非 gated 镜像下载；再分发前请阅读 FLUX Kommunity License
（免费商用要求年收入 < 500 万美元）。

### 官方提示词上采样器工作流（第三档）

`workflows/flux3_klein_t2i_upsampler_api.json` —— 在采样器前串联**官方 FLUX3 提示词上采样器**的完整文生图工作流，全部使用 ComfyUI 0.41 原生节点（`TextGenerate`），无需额外插件：

```
短请求 ──▶ CLIPLoader(上采样器, type=flux3) ──▶ TextGenerate ──▶ 完整场景描述 ──▶ CLIPTextEncode (positive)
```

- 上采样器权重 `qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors`（~9.1 GB，放 `models/text_encoders/`）会被 ComfyUI 识别为 `QWEN35_9B`，用 `CLIPLoader` + `type=flux3` 加载；`TextGenerate` 把你的短请求扩写成完整英文场景描述（机位、光线、构图）后再生成。
- 上采样器模型许可为 **Apache-2.0**（与 FLUX Kommunity License 相互独立）。
- RTX 5090 Laptop 24GB（CUDA）实测：仅扩写首跑 ≈249 秒（大头是冷加载）；1024² 全流程首跑 ≈453 秒。

三档对比，同一句提示词：

| 档位 | 工作流 | 行为 |
|---|---|---|
| 0. 原始 | `flux3_klein_t2i_api.json`（适配包） | 提示词原样进 FLUX3 |
| 1. 增强器 | `flux3_klein_t2i_enhanced_api.json` | rule_only=原文+质量词缀；auto/strata_local=Strata LLM 电影感扩写（中文优先） |
| 2. 官方上采样器 | `flux3_klein_t2i_upsampler_api.json` | BFL qwen3.5-9B 扩写成完整英文场景描述（Apache-2.0） |

也可以 1→2 串联：把增强器 `positive` 输出接到 `TextGenerate.prompt`，同时跑增强器与官方上采样器。

### 一个工作流、三档切换（路由器节点）

`workflows/flux3_klein_t2i_3tier.json` —— 把**三档全部放进同一张图**、用一个节点切换的 UI 工作流，推荐从这里开始：

```
                    ┌─ BSAI FLUX3 Prompt Enhancer ─┐
中文提示词(三处同源) ─┤  BSAI FLUX3 Prompt Router    ├─▶ positive ─▶ CLIPTextEncode
                    └─ CLIPLoader(上采样器)+TextGenerate ┘   └─▶ negative ─▶ CLIPTextEncode
```

- 新增节点 **`BSAI_FLUX3_PromptRouter`**（分类 `BSAI/FLUX3`）：`mode` 下拉 `raw / enhancer / upsampler` 三选一，负责把正负向提示词路由到对应档位，且**懒执行**——只算选中的档，未选档（如 ~9.1GB 上采样器）完全不加载（raw / enhancer 档日志中无上采样器加载痕迹，已实测验证）。
- raw 档：提示词原样进 FLUX3（路由器 `raw_prompt` 输入框）。
- enhancer 档：增强器 `positive/negative` 接入路由器（文件默认 `engine=rule_only`；在增强器节点上切 `auto/strata_local` 即走 Strata LLM）。
- upsampler 档：`CLIPLoader`（上采样器, type=flux3）→ `TextGenerate` → 路由器 `upsampled` 输入。文件内已内置官方 BFL 上采样系统提示词与 `max_length=768`；仅选中此档时 TextGenerate 才会执行。
- 三个提示词输入框（路由器 / 增强器 / TextGenerate）默认填同一句，可分别修改。
- RTX 5090 Laptop 24GB（CUDA）、1024×1024、INT8 蒸馏版实测：raw ≈96–179 秒 · enhancer(rule_only) ≈76–170 秒 · upsampler ≈40–44 秒（热实例）；upsampler 档出图与官方扩写文案对应（如画面中出现要求的霓虹文字）。

把 `flux3_klein_t2i_3tier.json` 拖进 ComfyUI 即可（或 File → Open）。若你的安装把蒸馏 UNET 放在 `models/diffusion_models/Flux3/` 子目录，保持文件里的 `unet_name` 不变；否则改成你机器上的实际路径。


### Strata LLM（可选）

LLM 路径复用 **BSAI-LLM-Strata** 服务（OpenAI 兼容，`127.0.0.1:8080`，模型 `qwen3.8-flash-next`）。
- **自动启动**：`engine=strata_local`（或 `auto`）运行时若后台未启动，节点会自动拉起 Strata 服务
  （即手动用的 `run-q2_0.bat`，无控制台窗口）并等待就绪——以 `/models` 真实返回已加载模型为判据，
  规避"进程起了但端口/模型没就绪"的假成功；最多等待 180 秒，仍起不来才降级规则引擎，节点不会报错。
- 若 Strata 已在运行则直接复用，不会重复拉起。

### 独立测试

```bash
python test_enhancer.py                      # 规则引擎
python test_enhancer.py --engine auto        # Strata 在线时走 LLM
```

## 兼容性

- ComfyUI 0.41+（使用 `DESCRIPTION` / `SEARCH_ALIASES` 类属性；旧版本仍能以英文显示名注册）。
- Python 3.10+（仅标准库）。

## 许可

MIT，见 [LICENSE](./LICENSE)。
本节点与 FLUX 模型权重相互独立；FLUX Kommunity License 约束的是模型本身，不是本代码。
