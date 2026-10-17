# FLUX.3 Klein Ecosystem Guide

How the BSAI FLUX3 ComfyUI Pack, the community upsampler plugin, and the official "reset/optimized" release fit together — and how to use them as one workflow.

> 中文版见 [FLUX3_ECOSYSTEM.zh-CN.md](./FLUX3_ECOSYSTEM.zh-CN.md)

## 1. Division of labor (what each piece is for)

| Piece | Role | Scope |
|---|---|---|
| **BSAI-FLUX3-ComfyUI** (this repo, root = enhancer node) | Enhancement & orchestration layer | Chinese-first prompt enhancement (rule / Strata local LLM), 3-tier prompt routing, Strata auto-start with duplicate protection, Intel XPU / GPU / NPU + one-click deployment |
| **kkget/ComfyUI-Flux3-Prompt-Upsampler** | Official feature implementation | Wraps the official BFL `qwen3.5_9b` upsampler as a node: up to **10 reference images**, **bounding-box editing** (edit in place / move / resize / remove / add), automatic t2i ↔ i2i system prompts, official reference-image preprocessing |
| **Official reset/optimized release** (Quark netdisk, mirrored locally in `G:\flux3 image(1)`) | Shared new base | New distilled models (bf16 / int8 / base-int8), native FLUX.3 subgraph workflows, **4–16 steps** instead of 50 |
| **kkget/Comfyui-Flux3-promt-Skill** | Prompt methodology (Agent skill, not a node) | BFL-doc-based prompting patterns: t2i, 3-view, character consistency, multi-image compositing, bbox layout; referenced for methodology, not copied (repo has no LICENSE file) |

**Policy:** BSAI does not re-implement the KK upsampler node. The two plugins are complementary and installed side by side; this repo provides the integration workflow and documentation.

## 2. Quick decision table

| You want to | Use |
|---|---|
| Chinese idea → image prompt, then generate | BSAI enhancer (tier 1) |
| Official 9B upsampler rewrite (t2i only) | Tier 2 native `TextGenerate` workflow (no extra plugin) |
| **Edit an image with reference image(s) + bbox** | KK `FLUX.3 Prompt Upsampler` (10 refs + bbox) |
| Chinese-first enhancement **+** multi-image editing in one graph | `workflows/flux3_klein_edit_bsai_x_kk.json` (this repo) |
| Fastest / newest weights | Official reset distilled model, 4–16 steps (Section 5) |

## 3. Prerequisites

1. **BSAI pack** — clone this whole repo into `ComfyUI/custom_nodes/` (repo root = plugin), restart ComfyUI.
2. **KK plugin** — clone `https://github.com/kkget/ComfyUI-Flux3-Prompt-Upsampler` into `ComfyUI/custom_nodes/`, restart ComfyUI (Apache-2.0, no extra pip deps). The node is `FLUX.3 Prompt Upsampler`, category `FLUX.3/text`.
3. **Models** (already on this machine for the base flows; new reset weights are downloading):

| Location | File |
|---|---|
| `models/text_encoders/` | `qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors` (needed by KK node) |
| `models/text_encoders/` | `qwen3vl_4b_int8_convrot.safetensors` (prompt encoding) |
| `models/vae/` | `flux2-vae.safetensors` |
| `models/diffusion_models/Flux3/` | `flux3_image_klein_int8_convrot.safetensors` (base, 50 steps) or `flux3_image_klein_sd_int8_convrot.safetensors` (distilled, 16 steps) |

## 4. Integration workflow (BSAI × KK)

`workflows/flux3_klein_edit_bsai_x_kk.json`:

```
Chinese edit request
   │
   ▼
BSAI_FLUX3_PromptEnhancer (engine=strata_local, zh)  ──positive──▶ FLUX.3 Prompt Upsampler (KK)
                                                                      │ clip = qwen3.5_9b (official upsampler)
   LoadImage (reference) ────────────────────────────────────────────▶ images.image0
                                                                      ▼
                                                                   caption
                                                                      │
                                                                      ▼
                                                       CLIPTextEncode (positive) ──▶ ReferenceMultiLatent
   LoadImage (reference) ────────────────────────────────────────────────────────▶ images.image0
                                                                                      ▼
                                                                              KSampler(50 steps, CFG 3.5)
                                                                                      ▼
                                                                              VAEDecode → SaveImage
```

How to run:

1. Import the JSON in ComfyUI (needs both BSAI and KK plugins installed).
2. Replace the reference image in `LoadImage`.
3. Set your Chinese edit request in the enhancer (Strata is auto-started when `strata_local` is selected; no duplicate instance is ever spawned).
4. Run. `PreviewAny` shows the official upsampler's expanded caption before sampling.

Going further — 10 images / bbox editing:

- Open KK's own example `image_flux3_klein_edit_10refs_bbox.json` (from the KK repo `examples/`, also mirrored in the local Quark download).
- Feed this workflow's enhancer `positive` output into its `Flux3PromptUpsampler.prompt` input, then use the bbox canvas (`CreateBoundingBoxes`) + `FLUX.3 Edit Prompt + Box Coordinates` as described in the KK README.

## 5. Official reset/optimized release (new base)

Source: official updated version link in the Bilibili video description — `https://pan.quark.cn/s/797537943335`; mirrored locally at `G:\flux3 image(1)` (workflow JSONs complete, model files downloading).

What changed (from the bundled workflows + video):

- **New distilled models** — `flux3-image-klein-base-int8-convrot-2b0a0cd339b4`, `flux3_image_klein_bf16-a5a072738617`, `flux3_image_klein_int8_convrot-aee2b5344d1a` (plus `qwen3vl_4b_bf16` text encoder).
- **Native FLUX.3 subgraph workflows** — `image_flux3_klein_distilled_t2i新.json` etc. use the built-in FLUX.3 node (uuid subgraph) with `ResolutionSelector` and `CreateBoundingBoxes`; the bundled note says **"try 4-16 steps"**.
- **Faster iterations** — distilled models at 4–16 steps replace the 50-step base default.

To adopt in BSAI flows once the download completes:

1. Place the new weights in `models/` following the bundled folder layout (`diffusionmodels/` → `models/diffusion_models/Flux3/`, `text_encoders/` → `models/text_encoders/`).
2. Run the official distilled workflow once to verify; then switch any BSAI workflow's `UNETLoader` to the new file and set `KSampler` steps to 4–16 (CFG ~1 for distilled).
3. Measured numbers will be appended to this doc after local validation (RTX 5090 Laptop 24G).

## 6. Licensing & attribution boundaries

- **KK upsampler plugin**: Apache-2.0 — safe to install, use, and reference. The BSAI repo does **not** vendor its code.
- **KK Skill repo**: has **no LICENSE file** — do not copy its content into this repo; reference it by link only (methodology summaries here are written from BFL official docs).
- **FLUX 3 Image Klein weights**: governed by the [FLUX Kommunity License v1.0](../adapter/_license/LICENSE.md) — not included in this repo; download via the adapter script / official mirror.
- **Official upsampler checkpoint** (`qwen3.5_9b_flux3_prompt_upsampler_*`): Apache-2.0 per BFL model card.

## 7. What BSAI deliberately does NOT do

- Does not re-implement multi-image / bbox editing (KK plugin covers it).
- Does not bundle model weights.
- Does not copy the KK Skill content (no LICENSE upstream).
- Keeps the enhancer node English-UI / PR-compliant; Chinese support lives in search aliases + zh-CN docs.
