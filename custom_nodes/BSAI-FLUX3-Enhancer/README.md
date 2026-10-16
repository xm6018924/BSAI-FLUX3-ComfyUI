# BSAI FLUX3 Prompt Enhancer (CN-First)

A Chinese-first, lightweight prompt enhancer custom node for ComfyUI.
Designed for **FLUX 3 Image Klein** (also covers **Qwen-Image 2.1** and **MiniMax H3**).

> 中文说明见 [README.zh-CN.md](./README.zh-CN.md)。

## Why

- **Chinese-first**: feed it a rough Chinese idea ("雨夜霓虹灯下的流浪猫") and get a dense, directly usable image prompt — in Chinese, with English visual keywords mixed in.
- **Dual engine, never fails**: uses the local **Strata LLM** (the BSAI-LLM-Strata service at `127.0.0.1:8080/v1`) when available; automatically falls back to a built-in deterministic rule engine when Strata is offline.
- **Multi-model recipes**: FLUX3 Klein / Qwen-Image 2.1 / MiniMax H3 each get their own positive/negative recipe templates.
- **License-clean**: it is your own code calling your own LLM — it does not consume FLUX weights or FLUX outputs, so it carries no FLUX Kommunity License obligations.

## Features

| Item | Detail |
|---|---|
| Outputs | `positive` + `negative` (STRING pair) |
| Engines | `auto` (default) · `strata_local` · `rule_only` |
| Target models | `flux3_klein` · `qwen_image_2.1` · `minimax_h3` |
| Languages | `zh` (default) · `en` |
| Tunables | `max_tokens` (64–2048), `temperature` (0.1–1.5), optional `negative_hint` |
| Category | `BSAI/FLUX3` |

## Installation

1. Copy (or clone) this folder into `ComfyUI/custom_nodes/BSAI-FLUX3-Enhancer/`.
2. Restart ComfyUI. The node appears under **BSAI/FLUX3**:
   **BSAI FLUX3 Prompt Enhancer (CN-First)**.
   - Search hint: type `prompt enhancer` / `提示词增强` in the node menu.

No Python dependencies are required — `enhancer.py` and `strata_client.py` use only the standard library.

## Usage

Add the node to your workflow and wire it like this:

```
中文提示词 ──▶ BSAI FLUX3 Prompt Enhancer ──▶ positive ──▶ CLIPTextEncode (positive)
                 (engine=auto)             └─▶ negative ──▶ CLIPTextEncode (negative)
```

- `raw_prompt`: your rough Chinese (or English) idea.
- `engine=auto`: use Strata LLM if it answers on port 8080, otherwise the rule engine.
- `target_model`: pick the recipe matching the model in your workflow.
- FLUX3 distilled checkpoints run at `cfg=1.0`, where the negative prompt is mostly ignored; for Qwen-Image 2.1 / H3 workflows wire the negative too.

### Example workflow

`workflows/flux3_klein_t2i_enhanced_api.json` — a complete FLUX 3 Image Klein distilled (INT8) text-to-image API workflow with the enhancer wired in:

1. Import the JSON into ComfyUI (drag & drop or File → Open), or POST it to `/prompt`.
2. Requires the model files (see below), then Queue.

Required checkpoints for the example (place them under `ComfyUI/models/`):

| File | Path | Size |
|---|---|---|
| `flux3_image_klein_sd_int8_convrot.safetensors` | `models/diffusion_models/` | ~5.4 GB |
| `qwen3vl_4b_int8_convrot.safetensors` | `models/text_encoders/` | ~4.5 GB |
| `flux2-vae.safetensors` | `models/vae/` | ~0.3 GB |

Model sources are gated on the official HF repo; download via a non-gated mirror, and review the
FLUX Kommunity License before redistribution (free commercial use requires annual revenue < US$5M).

### Strata LLM (optional)

The LLM path reuses the **BSAI-LLM-Strata** service (OpenAI-compatible, `127.0.0.1:8080`, model `qwen3.8-flash-next`).
If Strata is not running, the node silently falls back to the rule engine — it never errors out.

### Standalone test

```bash
python test_enhancer.py                      # rule engine
python test_enhancer.py --engine auto        # Strata LLM when available
```

## Compatibility

- ComfyUI 0.41+ (uses `DESCRIPTION` / `SEARCH_ALIASES` class attributes; older builds still register the node with an English display name).
- Python 3.10+ (standard library only).

## License

MIT — see [LICENSE](./LICENSE).
This node is independent of FLUX model weights; the FLUX Kommunity License governs the model itself, not this code.
