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

### Strata LLM（可选）

LLM 路径复用 **BSAI-LLM-Strata** 服务（OpenAI 兼容，`127.0.0.1:8080`，模型 `qwen3.8-flash-next`）。
Strata 未运行时节点静默降级到规则引擎，不会报错。

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
