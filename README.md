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

## NInfer engine (optional, used for prompt enhancement)

`ninfer-serve.exe` is a 300-400MB prebuilt binary, above GitHub's 100MB per-file limit, so it **cannot go through plain git** (`engine/` is git-ignored) and is distributed as a **Release asset** instead. Without it the enhancer falls back to the deterministic rule engine; images still render.

**Get the engine (pick either option A or B)**

**Option A: cloud-drive bundle (recommended for users in mainland China, all-in-one)**

- Download `BSAI-FLUX3-ComfyUI-full-ninfer.zip` (~574MB: plugin + `ninfer-sm120` + `ninfer-sm89` + `runtime`, no GPU picking needed)
- Quark cloud drive: <https://pan.quark.cn/s/9e3e390c4471> (no passcode; the Quark client gives much faster speeds for large files)
- Checksum file (sha256.txt): <https://pan.quark.cn/s/c276548108ae>
- SHA256: `b0dba545bf732af8ffc44e08693df68f6c74c0921d6b12e56b42a58e5b190d90`
- Extract and drop the whole `BSAI-FLUX3-ComfyUI` folder into `custom_nodes\`; the engine is already inside, so skip to step 3.

**Option B: GitHub Release (one bundle per GPU family)**

1. Open [Releases](../../releases/tag/v1-ninfer-engine) and download one:
   - `engine-sm120.zip` — RTX 50 series (compute capability 12.0+), ~323MB
   - `engine-sm89.zip` — RTX 40 series (compute capability 8.9), ~393MB
2. Extract into this plugin's root so you end up with `BSAI-FLUX3-ComfyUI/engine/ninfer-smXX/ninfer-serve.exe` plus `engine/runtime/`:

```powershell
Expand-Archive -Path engine-sm120.zip -DestinationPath <ComfyUI>\custom_nodes\BSAI-FLUX3-ComfyUI -Force
```

3. Restart ComfyUI (either option). Models go to `ComfyUI/models/LLM/**/*.ninfer` (not shipped).

Once installed, the engine directory is resolved automatically in this order:

1. the directory pointed to by the `BSAI_NINFER_ENGINE_DIR` env var;
2. this plugin's own `engine/` (where step 2 extracted it);
3. `ComfyUI-AIManzi-MultimodalPrompt/engine/` from a sibling plugin (upstream source);
4. any `custom_nodes/*/engine/` that already contains `ninfer-sm120|sm89|sm86/ninfer-serve.exe`.

## Supported GPUs & upgrade steps / 支持的显卡与升级步骤

**中文**：反推（NInfer 提示词增强）链路现在按**显卡算力精确命中**选引擎，不做区间外推——跨代硬跑会直接 abort。
30 系（sm_86）已有独立槽位 `engine/ninfer-sm86/`，但上游没有 sm86 构建，30 系的正确做法是改用
**llama.cpp (local GGUF)** 后端；20 系 / 16 系同理。

| 显卡家族 | 算力 | NInfer 反推引擎 | llama.cpp 后端（GGUF） |
|---|---|---|---|
| RTX 50（5090 / 5080 / 5070 / 5060） | sm_120（12.1 也读 120） | ✅ `engine-sm120.zip` | ✅ 插件根 CUDA 13，驱动 ≥ **580.65** |
| RTX 40（4090 / 4080 / 4070 / 4060） | sm_89 | ✅ `engine-sm89.zip` | ✅ 同上 |
| RTX 30（3090 / 3080 / 3070 / 3060 / 3060 Ti） | sm_86 | ⚠️ 只有槽位：自建 `engine/ninfer-sm86/` 才会被选中，否则明确提示切换后端 | ✅ 插件根 CUDA 13，驱动 ≥ **580.65** |
| RTX 20（2080 Ti / 2070 / 2060） | sm_75 | ❌ 无构建 | ✅ `engine-cuda12`，驱动 ≥ **525.60** |
| GTX 16（1660 / 1650 / 1650S） | sm_61 / sm_70 | ❌ 无构建 | ✅ `engine-cuda12` |
| 任意 NVIDIA（驱动 ≥ 470） | — | ❌ | ✅ `engine-vulkan`（与算力无关，实测解码仅 0.7 t/s，仅作兜底） |

**English**: the NInfer captioning / prompt-enhance path now picks its engine by an **exact compute-capability
match** — no range extrapolation, because a cross-generation run aborts. RTX 30 (sm_86) has its own
`engine/ninfer-sm86/` slot, but there is no upstream sm86 build: 30-series should use the
**llama.cpp (local GGUF)** backend instead. Same for 20-series / 16-series.

| GPU family | Compute cap | NInfer engine | llama.cpp backend (GGUF) |
|---|---|---|---|
| RTX 50 (5090 / 5080 / 5070 / 5060) | sm_120 (12.1 also maps to 120) | ✅ `engine-sm120.zip` | ✅ plugin-root CUDA 13, driver ≥ **580.65** |
| RTX 40 (4090 / 4080 / 4070 / 4060) | sm_89 | ✅ `engine-sm89.zip` | ✅ same |
| RTX 30 (3090 / 3080 / 3070 / 3060 / 3060 Ti) | sm_86 | ⚠️ slot only: used when you drop your own `engine/ninfer-sm86/`, otherwise the plugin tells you to switch backends | ✅ plugin-root CUDA 13, driver ≥ **580.65** |
| RTX 20 (2080 Ti / 2070 / 2060) | sm_75 | ❌ no build | ✅ `engine-cuda12`, driver ≥ **525.60** |
| GTX 16 (1660 / 1650 / 1650S) | sm_61 / sm_70 | ❌ no build | ✅ `engine-cuda12` |
| any NVIDIA with driver ≥ 470 | — | ❌ | ✅ `engine-vulkan` (arch-independent; measured at only 0.7 tok/s, last resort) |

### Upgrade steps / 升级步骤

1. **拉最新插件代码 / Pull the latest code**：`git pull`，或用 ComfyUI-Manager 更新本插件后重启一次。
2. **40 系 / 50 系（Ada / Blackwell）**：只需按卡重新下载对应引擎包（已装过则跳过）——
   `engine-sm120.zip` 或 `engine-sm89.zip`，解压到插件根，保持 `engine/ninfer-smXX/ninfer-serve.exe` 结构。
3. **30 系 / 20 系 / 16 系**：不需要 NInfer 包，改用 llama.cpp 后端：
   1) 装 `BSAI-llama.cpp`（阈值见上表）；
   2) 驱动能升到 **580.65** 就直接用它的插件根 CUDA 13 构建；
   3) 驱动升不动就跑 `BSAI-llama.cpp\下载CUDA12引擎.bat` 补齐 `engine-cuda12` / `engine-vulkan`；
   4) 在 ComfyUI 里把反推节点后端切到 **llama.cpp (local GGUF)**，GGUF 权重放
      `ComfyUI/models/LLM/`（本机为 G 盘库 + C 盘 Junction，一份权重两盘可见）。
4. **重启 ComfyUI**，节点首次运行时会打印实际选中的引擎目录（`ninfer-smXX` 或 `engine-*`）。
5. **验证 / Verify**：

```bat
nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv
python custom_nodes\BSAI-llama.cpp\bsai_engine_select.py --show
custom_nodes\BSAI-llama.cpp\engine-vulkan\llama-server.exe --list-devices
```

6. **回滚 / Rollback**：`engine-selection.json` / `engine-force.txt` 在 `BSAI-llama.cpp` 里，
   删掉或写 `auto` 即回到按算力自动选择；NInfer 侧把 `engine/ninfer-smXX/` 目录移走即可让它退回规则引擎。

> 已实测（本机 RTX 5090 Laptop，sm_120 / 驱动 616.56）：NInfer 选型 `12.0→sm120`、`8.9→sm89`、
> `8.6→sm86 槽位（无构建则明确报缺）`、`7.5/6.1→拒绝并提示改用 GGUF`；
> llama.cpp 侧 8B Q4 实测 pp 963 / tg 38.4 tok/s，Vulkan 档 tg 0.73 tok/s（慢于纯 CPU 的 3.84）。
> Measured on RTX 5090 Laptop (sm_120, driver 616.56): NInfer maps 12.0→sm120, 8.9→sm89,
> 8.6→sm86 slot (clear "engine missing" error), 7.5/6.1→refused with a GGUF hint; on the
> llama.cpp side, 8B Q4 hits pp 963 / tg 38.4 tok/s, while the Vulkan tier is 0.73 tok/s
> (slower than CPU-only 3.84).

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
