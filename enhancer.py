"""BSAI FLUX3 Prompt Enhancer (CN-First) — a ComfyUI custom node.

Dual engine:
  1. Local Strata LLM enhancement (reuses the BSAI-LLM-Strata endpoint at 127.0.0.1:8080/v1)
  2. Deterministic rule-engine fallback (node always produces output, even offline)

Per-target-model recipes (FLUX3 Klein / Qwen-Image 2.1 / MiniMax H3),
outputs a positive + negative prompt pair.

中文辅助说明（辅助信息，不影响英文 UI）：本节点定位为"工作流内嵌"的中文优先提示词增强器，
LLM 路径复用百声 Strata 服务；选中 strata 档（strata_local / auto）且服务未运行时，
节点会自动拉起 Strata 后台并等待就绪（按 /models 已加载模型判定），实在起不来才降级规则引擎。
"""
import os
import sys

# Make strata_client importable both under ComfyUI and standalone
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from strata_client import strata_health, strata_chat  # noqa: E402
from strata_launcher import ensure_strata  # noqa: E402
from ninfer_client import (  # noqa: E402
    ninfer_health, ninfer_chat, ensure_ninfer,
    list_ninfer_model_names,
)


def list_nemotron_model_names():
    """List non-mmproj GGUF models under models/LLM/Nemotron/ (rel paths)."""
    try:
        import importlib.util as _ilu
        _p = os.path.join(_HERE, "..", "BSAI-LLM-Strata", "strata_manager.py")
        if not os.path.exists(_p):
            return []
        _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
        _m = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        return [rel for rel, _abs, kind in _m.NemotronManager.list_models() if kind == "model"]
    except Exception:
        return []


def list_strata_quant_options():
    """Strata quant dropdown: Auto + the four Qwen3.8-Flash-Next quant levels."""
    try:
        import importlib.util as _ilu
        _p = os.path.join(_HERE, "..", "BSAI-LLM-Strata", "strata_manager.py")
        if not os.path.exists(_p):
            return ["Auto (auto)"]
        _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
        _m = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        opts = list(_m.QUANT_OPTIONS.keys())
        return opts or ["Auto (auto)"]
    except Exception:
        return ["Auto (auto)"]

# ---------------------------------------------------------------------------
# Model recipes
# ---------------------------------------------------------------------------
# 与 ComfyUI 0.41 官方新增对齐：
#   flux3_klein         = FLUX.3 Image Klein 基础检查点（配合 Qwen3-VL-4B 文本编码器 + Flux2 VAE）
#   flux3_klein_sd      = FLUX.3 Image Klein step-distilled 检查点（更少步数出图）
#   qwen_image_2.1      = Qwen-Image 2.1 基础（25步/CFG1 官方 day-0 档）
#   qwen_image_2.1_turbo= Qwen-Image 2.1 Turbo 8步加速（Pruna 8-step LoRA / ManualSigmas）
#   minimax_h3          = MiniMax H3 视频/图像
MODEL_OPTIONS = ["flux3_klein", "flux3_klein_sd", "qwen_image_2.1", "qwen_image_2.1_turbo", "minimax_h3"]

# Rule engine: per-model positive quality tags (appended to the output prompt)
_RULE_POSITIVE = {
    "flux3_klein": (
        "masterpiece, best quality, extremely detailed, highly detailed face and hands, "
        "natural lighting, cinematic composition, sharp focus, rich textures, 8k uhd"
    ),
    "flux3_klein_sd": (
        "masterpiece, best quality, extremely detailed, crisp clean render, "
        "highly detailed face and hands, natural lighting, cinematic composition, "
        "sharp focus, rich textures, 8k uhd, step-distilled fast render"
    ),
    "qwen_image_2.1": (
        "high quality image, rich details, clear subject, natural lighting, "
        "well-considered composition, fine texture, accurate colors, high resolution, "
        "sharp focus, highly detailed"
    ),
    "qwen_image_2.1_turbo": (
        "high quality image, rich details, clear subject, natural lighting, "
        "well-considered composition, fine texture, accurate colors, high resolution, "
        "8-step accelerated render, crisp details, sharp focus, highly detailed"
    ),
    "minimax_h3": (
        "cinematic frame, cinematic lighting, shallow depth of field, prominent subject, "
        "clean and crisp image, rich details, considered composition, "
        "professional photography feel, film grain"
    ),
}

# Rule engine: per-model negative tags
_RULE_NEGATIVE = {
    "flux3_klein": (
        "lowres, bad anatomy, bad hands, missing fingers, extra digits, blurry, "
        "jpeg artifacts, watermark, text, signature, deformed, ugly, oversaturated"
    ),
    "flux3_klein_sd": (
        "lowres, bad anatomy, bad hands, missing fingers, extra digits, blurry, "
        "jpeg artifacts, watermark, text, signature, deformed, ugly, oversaturated"
    ),
    "qwen_image_2.1": (
        "low resolution, blurry, distorted, bad fingers, extra limbs, watermark, text, "
        "signature, deformed, oversaturated, lowres, bad anatomy, jpeg artifacts"
    ),
    "qwen_image_2.1_turbo": (
        "low resolution, blurry, distorted, bad fingers, extra limbs, watermark, text, "
        "signature, deformed, oversaturated, lowres, bad anatomy, jpeg artifacts"
    ),
    "minimax_h3": (
        "low quality, blurry, distorted, flickering, artifacts, watermark, text, "
        "deformed, oversaturated, camera shake, lowres, flicker, jitter"
    ),
}

# Rule engine: subject/scene detail tail (appended when the prompt is too short)
_RULE_DETAIL_TAIL = {
    "flux3_klein": ", intricate details, depth of field, ambient occlusion, ultra detailed",
    "flux3_klein_sd": ", intricate details, depth of field, ambient occlusion, crisp edges, ultra detailed",
    "qwen_image_2.1": ", rich detail layers, natural light transitions, well-controlled depth of field, clean image",
    "qwen_image_2.1_turbo": ", rich detail layers, natural light transitions, well-controlled depth of field, 8-step accelerated render, clean and crisp image",
    "minimax_h3": ", both motion and atmosphere, clear camera language, rich lighting layers",
}

# ---------------------------------------------------------------------------
# LLM system prompts (per model x language)
# ---------------------------------------------------------------------------
_LLM_SYS = {
    ("flux3_klein", "zh"): (
        "你是资深 AI 图像提示词工程师，专精 FLUX3 Image Klein 基础模型。"
        "把用户的中文粗略想法改写成一段可直接用于出图的详细图像提示词。要求："
        "1) 描述具体可画的视觉要素：主体、场景、构图、光线、材质、细节；"
        "2) 中文为主，可混合少量英文视觉关键词（如 cinematic lighting、8k）；"
        "3) 只输出改写后的提示词，不要解释、不要分段编号；"
        "4) 忠于用户原意，不添加原意之外的敏感或违规内容。"
    ),
    ("flux3_klein", "en"): (
        "You are a master prompt engineer for the FLUX3 Image Klein base model. "
        "Rewrite the user's rough idea into a dense, concrete image prompt. "
        "Describe subject, scene, composition, lighting, materials and detail. "
        "Output only the rewritten prompt, no explanation."
    ),
    ("flux3_klein_sd", "zh"): (
        "你是资深 AI 图像提示词工程师，专精 FLUX3 Image Klein step-distilled 蒸馏模型"
        "（配合 Qwen3-VL-4B 文本编码器与 Flux2 VAE，少步数快速出图）。"
        "把用户的中文粗略想法改写成一段可直接用于出图的详细图像提示词，要求主体明确、"
        "构图清楚、光影自然、细节锐利。只输出改写后的提示词，不要解释、不要分段编号。"
    ),
    ("flux3_klein_sd", "en"): (
        "You are a master prompt engineer for the FLUX3 Image Klein step-distilled model "
        "(paired with the Qwen3-VL-4B text encoder and the Flux2 VAE). "
        "Rewrite the user's rough idea into a dense, concrete image prompt with a clear subject, "
        "composition, natural lighting and crisp detail. Output only the rewritten prompt, no explanation."
    ),
    ("qwen_image_2.1", "zh"): (
        "你是资深 AI 图像提示词工程师，专精阿里 Qwen-Image 2.1 模型（中文理解强）。"
        "把用户的中文粗略想法改写成详细的中文图像提示词，具体描述主体、场景、构图、"
        "光线、风格与细节。只输出改写后的提示词，不要解释。"
    ),
    ("qwen_image_2.1", "en"): (
        "You are a prompt engineer for Qwen-Image 2.1. Rewrite the user's idea into a "
        "detailed image prompt (Chinese preferred when the input is Chinese). Output only the prompt."
    ),
    ("qwen_image_2.1_turbo", "zh"): (
        "你是资深 AI 图像提示词工程师，专精阿里 Qwen-Image 2.1 Turbo 8步加速模型"
        "（CFG=1.0 + 空负向 + 固定 sigma 蒸馏档）。把用户的中文粗略想法改写成详细的中文"
        "图像提示词，具体描述主体、场景、构图、光线、风格与细节，要求画面干净、细节锐利。"
        "只输出改写后的提示词，不要解释。"
    ),
    ("qwen_image_2.1_turbo", "en"): (
        "You are a prompt engineer for the Qwen-Image 2.1 Turbo 8-step distilled model "
        "(CFG=1.0, empty negative, fixed sigmas). Rewrite the user's idea into a detailed, "
        "clean and crisp image prompt (Chinese preferred when the input is Chinese). Output only the prompt."
    ),
    ("minimax_h3", "zh"): (
        "你是资深影视分镜提示词工程师，专精 MiniMax H3 视频/图像模型。"
        "把用户的中文粗略想法改写成电影感强的详细提示词，包含主体、场景、镜头感、"
        "光线氛围与画面细节。只输出改写后的提示词，不要解释。"
    ),
    ("minimax_h3", "en"): (
        "You are a cinematic prompt engineer for MiniMax H3. Rewrite the user's idea into "
        "a detailed cinematic prompt with subject, scene, camera feel, lighting and detail. "
        "Output only the prompt."
    ),
}


def _build_system(target_model, language):
    key = (target_model, language)
    if key not in _LLM_SYS:
        key = (target_model, "zh")
    return _LLM_SYS[key]


# ---------------------------------------------------------------------------
# Rule engine (deterministic fallback)
# ---------------------------------------------------------------------------
def _rule_enhance(raw_prompt, target_model):
    pos = _RULE_POSITIVE.get(target_model, _RULE_POSITIVE["flux3_klein"])
    neg = _RULE_NEGATIVE.get(target_model, _RULE_NEGATIVE["flux3_klein"])
    tail = _RULE_DETAIL_TAIL.get(target_model, "")

    subject = (raw_prompt or "").strip()
    if not subject:
        subject = ("generic scene: subject close-up in natural light, clear separation of planes"
                   if target_model != "qwen_image_2.1"
                   else "generic scene, subject close-up in natural light")

    # 短提示自动补场景细节
    if len(subject) < 12:
        subject = subject + tail

    if target_model in ("qwen_image_2.1", "qwen_image_2.1_turbo"):
        positive = f"{subject}，{pos}"
    else:
        positive = f"{pos}, {subject}"
    return positive.strip(), neg.strip()


# ---------------------------------------------------------------------------
# ComfyUI node
# ---------------------------------------------------------------------------
class BSAI_FLUX3_PromptEnhancer:
    """BSAI FLUX3 Prompt Enhancer (CN-First).

    Chinese-first, multi-model prompt enhancer with a local LLM path
    (Strata at 127.0.0.1:8080) and a deterministic rule-engine fallback.
    """

    DESCRIPTION = (
        "Chinese-first prompt enhancer for FLUX3 Image Klein (base / step-distilled, "
        "paired with the Qwen3-VL-4B text encoder + Flux2 VAE) / Qwen-Image 2.1 (native / "
        "Turbo 8-step distilled) / MiniMax H3. Enhances a rough Chinese prompt into a "
        "detailed image prompt (positive + negative). Uses the local Strata LLM "
        "(auto-starts it when selected and offline) and falls back to a built-in rule engine."
    )
    SEARCH_ALIASES = [
        "prompt enhancer", "prompt expander", "prompt engineer", "text enhancer",
        "chinese prompt", "cn first", "bsai flux3", "qwen image prompt", "h3 prompt",
        # 中文辅助搜索别名（UI 仍为英文）
        "提示词增强", "提示词扩展", "中文提示词", "提示词优化", "增强器",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "raw_prompt": ("STRING", {"multiline": True, "dynamicPrompts": False}),
                "target_model": (MODEL_OPTIONS, {"default": "flux3_klein"}),
                "engine": (["auto", "strata_local", "nemotron", "ninfer", "rule_only", "none"], {"default": "ninfer"}),
                "language": (["zh", "en"], {"default": "zh"}),
                "max_tokens": ("INT", {"default": 512, "min": 64, "max": 2048, "step": 32}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.1, "max": 1.5, "step": 0.05}),
                # 模型下拉允许「清空/（none）」：engine=none 直通模式不需要任何模型，
                # 空值必须在选项列表里，否则 ComfyUI 校验直接拒绝整个提示词。
                "ninfer_model": (["", "(none)", "(Auto — first model found)"] + list_ninfer_model_names(),
                                 {"default": "(Auto — first model found)",
                                  "tooltip": "NInfer backend only: *.ninfer model to load (models/LLM). Auto picks the preferred/first available model; empty/(none) = no model requested (not needed when engine=none)."}),
                "nemotron_model": (["", "(none)", "(Auto — first model found)"] + list_nemotron_model_names(),
                                   {"default": "(Auto — first model found)",
                                    "tooltip": "Nemotron backend only: GGUF model to load (models/LLM/Nemotron, mmproj excluded). Auto picks the first available model; empty/(none) = no model requested (not needed when engine=none)."}),
            },
            "optional": {
                "negative_hint": ("STRING", {"default": "", "multiline": True}),
                "system_prompt": ("STRING", {"default": "", "multiline": True}),
                # Append at the end so old workflows keep their widgets_values indices
                "strata_quant": (list_strata_quant_options(), {"default": "Auto (auto)",
                    "tooltip": "Strata backend only: Qwen3.8-Flash-Next quant level (Auto plus Q2_0/IQ2_XS/IQ3_XXS/IQ3_S). Applies only when Strata is not running and has to be auto-started."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "execute"
    CATEGORY = "BSAI/FLUX3"

    @classmethod
    def VALIDATE_INPUTS(cls, ninfer_model=None, nemotron_model=None, strata_quant=None, **kwargs):
        """Saved workflows carry the old Chinese widget values; accept them and let
        execute() map them onto the current English ones."""
        return True

    def execute(self, raw_prompt, target_model="flux3_klein", engine="ninfer",
                language="zh", max_tokens=512, temperature=0.7, negative_hint="",
                system_prompt="", ninfer_model="(Auto — first model found)",
                nemotron_model="(Auto — first model found)",
                strata_quant="Auto (auto)"):
        # Legacy widget values from earlier builds / saved workflows.
        if str(ninfer_model) == "（无）":
            ninfer_model = "(none)"
        if str(nemotron_model) == "（无）":
            nemotron_model = "(none)"
        pos = None
        neg = None
        engine_used = "rule_only"

        # --- NONE: pure passthrough, no enhancement at all ---
        if engine == "none":
            print(f"[BSAI-FLUX3-Enhancer] engine=none (passthrough) model={target_model} lang={language}")
            return (raw_prompt, (negative_hint or "").strip())

        sys_prompt = (system_prompt or "").strip() or _build_system(target_model, language)

        # --- NInfer engine (bundled ninfer-serve.exe on 127.0.0.1:8082) ---
        if engine == "ninfer":
            try:
                model_name = None if str(ninfer_model).startswith("(Auto") or str(ninfer_model) in ("", "（无）") else ninfer_model
                ensure_ninfer(model_name=model_name)
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"用户的粗略想法：{raw_prompt}"},
                ]
                pos = ninfer_chat(messages, max_tokens=max_tokens, temperature=temperature,
                                  model_name=model_name)
                engine_used = "ninfer"
            except Exception as e:
                pos = None
                print(f"[BSAI-FLUX3-Enhancer] NInfer failed, falling back to rule engine: {type(e).__name__}: {e}")

        # --- Strata engine (local Strata service on 127.0.0.1:8080) ---
        use_llm = engine in ("auto", "strata_local")
        if pos is None and use_llm:
            try:
                if not strata_health():
                    # Strata selected but offline → auto-start the backend and wait.
                    # 优先走 StrataManager（支持 strata_quant 量化档选择），
                    # 加载失败时回退到旧的 strata_launcher（固定 Q2_0）。
                    _started = False
                    try:
                        import importlib.util as _ilu, os as _os
                        _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                           "..", "BSAI-LLM-Strata", "strata_manager.py")
                        if _os.path.exists(_p):
                            _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
                            _m = _ilu.module_from_spec(_spec)
                            _spec.loader.exec_module(_m)
                            _ok, _msg = _m.StrataManager.ensure_running(
                                quant_label=strata_quant or "Auto (auto)")
                            _started = bool(_ok)
                            if not _ok:
                                print(f"[BSAI-FLUX3-Enhancer] StrataManager auto-start failed: {_msg}")
                    except Exception as _e:
                        print(f"[BSAI-FLUX3-Enhancer] StrataManager unavailable ({type(_e).__name__}: {_e}); using legacy launcher")
                    if not _started and not strata_health():
                        ensure_strata(log=print)
                if strata_health():
                    messages = [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"用户的粗略想法：{raw_prompt}"},
                    ]
                    pos = strata_chat(messages, max_tokens=max_tokens, temperature=temperature)
                    engine_used = "strata_local"
            except Exception as e:
                pos = None
                print(f"[BSAI-FLUX3-Enhancer] Strata LLM failed, falling back to rule engine: {type(e).__name__}: {e}")

        # --- Nemotron engine (local llama.cpp on 127.0.0.1:8085) ---
        use_llm = engine in ("auto", "nemotron")
        if pos is None and use_llm:
            try:
                import importlib.util as _ilu, os as _os
                _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                   "..", "BSAI-LLM-Strata", "strata_manager.py")
                if _os.path.exists(_p):
                    _spec = _ilu.spec_from_file_location("bsai_strata_manager", _p)
                    _m = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_m)
                    _mp = None if str(nemotron_model).startswith("(Auto") or str(nemotron_model) in ("", "（无）") else nemotron_model
                    ok, msg = _m.NemotronManager.ensure_running(model_path=_mp)
                    if ok:
                        mids = _m.NemotronManager.models()
                        messages = [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": f"用户的粗略想法：{raw_prompt}"},
                        ]
                        r = _m.NemotronManager.chat(
                            messages,
                            model=(mids[0] if mids else None),
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                        pos = r["choices"][0]["message"]["content"].strip()
                        engine_used = "nemotron"
            except Exception as e:
                pos = None
                print(f"[BSAI-FLUX3-Enhancer] Nemotron LLM failed, falling back to rule engine: {type(e).__name__}: {e}")

        # LLM 返回空字符串（模型加载成功但生成内容为空）时也走规则引擎兜底，
        # 避免 positive 输出为空导致下游无法出图。
        if not pos:
            pos, neg = _rule_enhance(raw_prompt, target_model)
            engine_used = "rule_only"
        else:
            neg = _RULE_NEGATIVE.get(target_model, _RULE_NEGATIVE["flux3_klein"])

        # Append user-provided negative terms (deduplicated)
        hint = (negative_hint or "").strip()
        if hint and neg:
            existing = set(x.strip() for x in neg.split(","))
            extra = [x.strip() for x in hint.split(",") if x.strip() and x.strip() not in existing]
            if extra:
                neg = neg + ", " + ", ".join(extra)
        elif hint and not neg:
            neg = hint

        print(f"[BSAI-FLUX3-Enhancer] engine={engine_used} model={target_model} lang={language}")
        return (pos, neg)
