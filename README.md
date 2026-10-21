# BSAI FLUX3 ComfyUI Pack

One-click deployment & tooling for **FLUX 3 Image Klein** (5.6B open weights, Black Forest Labs) on the BSAI ComfyUI distribution, plus a **Chinese-first prompt enhancer** custom node.

> 中文说明见 [README.zh-CN.md](./README.zh-CN.md)。

## What's inside

```
BSAI-FLUX3-ComfyUI/
├── adapter/                          # Intel XPU / GPU / NPU + NVIDIA adapter pack
│   ├── BSAI-FLUX3_README.md         # adapter guide (hardware tiers, license, TODOs)
│   ├── 01_下载FLUX3权重.bat          # weight downloader (hf-mirror + aria2, resumable)
│   ├── 02_启动FLUX3_5090.bat         # NVIDIA CUDA launcher (port 8193)
│   ├── 03_启动FLUX3_IntelXPU.bat     # Intel XPU/iGPU launcher (port 8194, Arc-ready)
│   ├── bsai_flux3_check.py           # model integrity checker (exit 0 = ready)
│   ├── run_flux3_test.py             # benchmark driver: submit → time → VRAM peak
│   ├── workflows/flux3_klein_t2i_api.json            # tier 0: raw prompt
│   ├── workflows/flux3_klein_t2i_upsampler_api.json  # tier 2: official prompt upsampler
│   ├── _license/                     # FLUX Kommunity License v1.0 archive
│   ├── 许可核对报告_FLUX_Kommunity_License.md
│   └── 实测报告_5090_FLUX3_Klein.md  # real measurements on RTX 5090 Laptop
├── docs/                             # ecosystem & integration guide
│   ├── FLUX3_ECOSYSTEM.md            # BSAI x KK x official reset (EN)
│   └── FLUX3_ECOSYSTEM.zh-CN.md      # 同上（中文）
├── workflows/                       # example workflows (import in ComfyUI)
│   ├── flux3_klein_t2i_enhanced_api.json    # tier 1: enhancer (rule / Strata LLM)
│   ├── flux3_klein_t2i_upsampler_api.json   # tier 2: official upsampler
│   └── flux3_klein_edit_bsai_x_kk.json      # BSAI x KK integration (image edit)
└── __init__.py / enhancer.py / router.py / strata_*.py / test_enhancer.py
                                     # repo root IS the ComfyUI custom node
                                     # (category BSAI/FLUX3, node "BSAI FLUX3 Prompt Enhancer")
```

## Quick start

1. Download the weights (≈30 GB total, resumable):
   `adapter/01_下载FLUX3权重.bat` — the script checks integrity afterwards (8/8 required files).
2. Launch:
   - NVIDIA: `adapter/02_启动FLUX3_5090.bat` → http://127.0.0.1:8193
   - Intel Arc / iGPU: `adapter/03_启动FLUX3_IntelXPU.bat` → http://127.0.0.1:8194
3. Install the enhancer node: clone this whole repo into `ComfyUI/custom_nodes/` (the repo root **is** the plugin: `__init__.py` sits at the root). Restart ComfyUI, then import an example workflow from `workflows/`.

## Measured results (RTX 5090 Laptop 24G, distilled INT8, 1024² / 16 steps)

| Config | Total (cold) | Warm | VRAM peak |
|---|---|---|---|
| INT8 distilled | 98.3 s | **35.6 s** | ~13.8 GB |
| BF16 distilled | 190.1 s | — | ~19.4 GB |
| INT8 + low-VRAM mode (~9.4 GB budget) | 126.1 s | — | **~10.4 GB** |

The "8 GB VRAM" claim holds for the INT8 distilled model under dynamic offloading; start from 512–768 px on true 8 GB cards. Details: `adapter/实测报告_5090_FLUX3_Klein.md`.

## Prompt enhancer

`BSAI FLUX3 Prompt Enhancer (CN-First)` (category `BSAI/FLUX3`):
- Chinese-first: rough Chinese idea → dense, usable image prompt.
- Dual engine: local Strata LLM (`127.0.0.1:8080`, via BSAI-LLM-Strata) with automatic rule-engine fallback — never errors.
- Strata auto-start is reuse-first: if a Strata instance is already present (model healthy, port 8080 listening, engine process loading, **or the new-arch Manager on port 8081 is up**), the node waits for it and **never spawns a second instance**; it only starts Strata when nothing is running. With the new-arch Manager (BSAI-LLM-Strata `bsai_model_manager.py`, Manager=8081 / engine=8080), the node auto-triggers the model load via `POST /api/switch` and waits for the engine to become ready — you no longer need to pick a model in the Web UI manually.
- Recipes for FLUX3 Klein (**base / step-distilled**, paired with the Qwen3-VL-4B text encoder + Flux2 VAE) / Qwen-Image 2.1 (**native / Turbo 8-step distilled**) / MiniMax H3; outputs `positive` + `negative`.
- English UI per ComfyUI custom-node conventions; Chinese support via search aliases + README.zh-CN.md.

## Checkpoint variants (aligned with ComfyUI 0.41 native FLUX.3 support)

| Variant | File (`models/diffusion_models/`) | Typical use |
|---|---|---|
| Base (INT8 / BF16) | `flux3_image_klein_int8_convrot.safetensors` / `flux3_image_klein_bf16.safetensors` | full-quality generation, LoRA / fine-tune base |
| Step-distilled (INT8 / BF16) | `flux3_image_klein_sd_int8_convrot.safetensors` / `flux3_image_klein_sd_bf16.safetensors` | fast render, 4–16 steps |

Both load via `UNETLoader` (detected as FLUX3); text encoder = `CLIPLoader` `qwen3vl_4b_*` with `type=flux3`; VAE = `flux2-vae.safetensors`. The enhancer's `target_model` dropdown selects the matching prompt recipe (`flux3_klein` = base, `flux3_klein_sd` = step-distilled). `bsai_flux3_check.py` checks all four diffusion variants + Qwen3-VL-4B + Flux2 VAE; `01_下载FLUX3权重.bat` now downloads base and distilled checkpoints.

## Three prompt tiers (same prompt, three workflows)

| Tier | Workflow | Behavior |
|---|---|---|
| 0. Raw | `adapter/workflows/flux3_klein_t2i_api.json` | prompt goes to FLUX3 exactly as typed |
| 1. Enhancer | `workflows/flux3_klein_t2i_enhanced_api.json` | rule_only: original + quality affixes; auto / strata_local: Strata LLM cinematic rewrite (Chinese-first) |
| 2. Official upsampler | `workflows/flux3_klein_t2i_upsampler_api.json` | ComfyUI native `TextGenerate` + BFL `qwen3.5-9B` upsampler: short request → full English scene caption |
| 3. Edit (BSAI × KK) | `workflows/flux3_klein_edit_bsai_x_kk.json` | Chinese-first enhancement → KK official 9B upsampler → reference-image editing (requires the kkget plugin) |

Tier 2 runs on native ComfyUI 0.41 nodes only (no extra plugin): the upsampler checkpoint
`qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors` (~9.1 GB, `models/text_encoders/`) is
detected as `QWEN35_9B` and loaded via `CLIPLoader` with `type=flux3`; `TextGenerate` does the
autoregressive rewrite. Measured on RTX 5090 Laptop 24G: rewrite alone ≈ 249 s first run (mostly cold
load), full 1024² end-to-end ≈ 453 s first run. The upsampler model is Apache-2.0. You can also chain
tier 1 → tier 2 by feeding the enhancer `positive` output into `TextGenerate.prompt`.

## FLUX.3 ecosystem & KK integration

Division of labor with the community upsampler plugin and the official "reset/optimized" release — see **[docs/FLUX3_ECOSYSTEM.md](./docs/FLUX3_ECOSYSTEM.md)** for the full guide:

- **BSAI enhancer** = enhancement & orchestration (Chinese-first, Strata, auto-start, Intel adapter).
- **kkget/ComfyUI-Flux3-Prompt-Upsampler** (Apache-2.0, install side by side) = official feature implementation: up to 10 reference images + bounding-box editing.
- **Official reset release** (Quark netdisk link in the video description) = new distilled models, native FLUX.3 subgraph workflows, **4–16 steps**.
- `workflows/flux3_klein_edit_bsai_x_kk.json` chains them: Chinese request → BSAI enhancer → KK official 9B upsampler → reference-image editing.

Licensing boundary: the KK plugin is Apache-2.0 (referenced, not vendored); the KK Skill repo has **no LICENSE file** (referenced by link only); FLUX.3 weights remain under the FLUX Kommunity License v1.0.

## License

- This repo: MIT (`LICENSE`).
- FLUX 3 Image Klein weights are **not included**; they are governed by the [FLUX Kommunity License v1.0](adapter/_license/LICENSE.md) (free commercial use below US$5M annual revenue; no training/distillation of similar image models from FLUX outputs; redistribution must include the license + attribution notice). The download script points to a non-gated mirror; review the license before redistribution.

> Intel XPU/iGPU path is Arc-ready but was validated on an RTX 5090 + Arc iGPU machine only; a dedicated Arc dGPU test is a TODO (see `adapter/README.md`).
