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

### Official prompt upsampler workflow (third tier)

`workflows/flux3_klein_t2i_upsampler_api.json` — a complete FLUX 3 Image Klein distilled (INT8)
text-to-image workflow that chains the **official FLUX3 prompt upsampler** in front of the sampler.
It runs entirely on ComfyUI 0.41 native nodes — no extra plugin needed:

```
短请求 ──▶ CLIPLoader(upsampler, type=flux3) ──▶ TextGenerate ──▶ 完整场景描述 ──▶ CLIPTextEncode (positive)
```

- The upsampler checkpoint `qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors`
  (~9.1 GB, `models/text_encoders/`) is detected by ComfyUI as `QWEN35_9B` and loaded with
  `CLIPLoader` using `type=flux3`; `TextGenerate` then rewrites your short request into a full
  English scene caption (framing, lighting, layout) before generation.
- The upsampler model is Apache-2.0 licensed (separate from the FLUX Kommunity License).
- Verified on RTX 5090 Laptop 24 GB (CUDA): text rewrite alone ≈ 249 s first run (mostly cold
  model load), full 1024² image end-to-end ≈ 453 s first run.

Three tiers, one prompt — pick the stage that fits your need:

| Tier | Workflow | Behavior |
|---|---|---|
| 0. Raw | `flux3_klein_t2i_api.json` (adapter) | prompt goes to FLUX3 exactly as typed |
| 1. Enhancer | `flux3_klein_t2i_enhanced_api.json` | rule_only: original + quality affixes; auto/strata_local: Strata LLM cinematic rewrite (Chinese-first) |
| 2. Official upsampler | `flux3_klein_t2i_upsampler_api.json` | BFL qwen3.5-9B rewrites to a full English caption (Apache-2.0) |

You can also chain tier 1 → tier 2: connect the enhancer `positive` output to `TextGenerate.prompt`
to run both enhancer and the official upsampler.

### One workflow, three tiers (router)

`workflows/flux3_klein_t2i_3tier.json` — a single UI workflow that puts **all three tiers into one
graph**, switched by one node. This is the recommended starting point:

```
                    ┌─ BSAI FLUX3 Prompt Enhancer ─┐
中文提示词(×3 同源) ─┤  BSAI FLUX3 Prompt Router    ├─▶ positive ─▶ CLIPTextEncode
                    └─ CLIPLoader(upsampler)+TextGenerate ┘   └─▶ negative ─▶ CLIPTextEncode
```

- New node **`BSAI_FLUX3_PromptRouter`** (category `BSAI/FLUX3`): a `mode` combo with
  `raw` / `enhancer` / `upsampler`. It routes the positive/negative pair accordingly and is
  **lazy**: only the selected tier runs — unselected branches (e.g. the ~9.1 GB upsampler) are
  never loaded (verified: raw & enhancer runs leave no upsampler load in the log).
- Raw tier: prompt goes to FLUX3 exactly as typed (router `raw_prompt`).
- Enhancer tier: enhancer `positive`/`negative` wired into the router (`engine=rule_only` by
  default in the file; switch to `auto`/`strata_local` in the enhancer node to use Strata LLM).
- Upsampler tier: `CLIPLoader` (upsampler, `type=flux3`) → `TextGenerate` → router `upsampled`
  input. Includes the official BFL prompt-upsampler system prompt (embedded in the file) and
  `max_length=768`; TextGenerate runs only when this tier is selected.
- The three prompt boxes (router / enhancer / TextGenerate) are pre-filled with the same request;
  edit any of them independently.
- Verified on RTX 5090 Laptop 24 GB (CUDA), 1024×1024, INT8 distilled checkpoint:
  raw ≈ 96–179 s · enhancer(rule_only) ≈ 76–170 s · upsampler ≈ 40–44 s (warm) — the upsampler
  tier output matches the official rewrite (e.g. the requested neon text renders in the image).

Import `flux3_klein_t2i_3tier.json` (drag & drop / File → Open). If your install stores the
distilled UNET under `models/diffusion_models/Flux3/`, keep the `unet_name` value as saved;
otherwise point it at the correct file.


### Strata LLM (optional)

The LLM path reuses the **BSAI-LLM-Strata** service (OpenAI-compatible, `127.0.0.1:8080`, model `qwen3.8-flash-next`).
- **Auto-start**: whenever `engine=strata_local` (or `auto`) runs while the backend is offline, the
  node launches the Strata service itself (the same `run-q2_0.bat` you use manually, no console
  window) and waits for it to become healthy — a real `/models` response with a loaded model, so a
  "process up but not ready" false start is detected, not trusted. Startup is polled for up to
  180 s; if it never becomes healthy the node falls back to the rule engine — it never errors out.
- If Strata is already running, it is reused as-is (no second process is spawned).

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
