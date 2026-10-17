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

# ---------------------------------------------------------------------------
# Model recipes
# ---------------------------------------------------------------------------
MODEL_OPTIONS = ["flux3_klein", "qwen_image_2.1", "minimax_h3"]

# 规则引擎：各模型的 positive 质量标签（增强片段）
_RULE_POSITIVE = {
    "flux3_klein": (
        "masterpiece, best quality, extremely detailed, highly detailed face and hands, "
        "natural lighting, cinematic composition, sharp focus, rich textures, 8k uhd"
    ),
    "qwen_image_2.1": (
        "高质量图像，细节丰富，主体清晰，光影自然，构图考究，画质细腻，"
        "色彩准确，高分辨率，sharp focus, highly detailed"
    ),
    "minimax_h3": (
        "电影级画面，电影感光线，浅景深，主体突出，画面通透，细节丰富，"
        "构图讲究，专业摄影质感, cinematic lighting, film grain"
    ),
}

# 规则引擎：各模型的 negative 标签
_RULE_NEGATIVE = {
    "flux3_klein": (
        "lowres, bad anatomy, bad hands, missing fingers, extra digits, blurry, "
        "jpeg artifacts, watermark, text, signature, deformed, ugly, oversaturated"
    ),
    "qwen_image_2.1": (
        "低分辨率, 模糊, 畸变, 手指异常, 多余肢体, 水印, 文字, 签名, 变形, 过饱和, "
        "lowres, bad anatomy, blurry, jpeg artifacts, watermark, text"
    ),
    "minimax_h3": (
        "低画质, 模糊, 畸变, 闪烁, 伪影, 水印, 文字, 变形, 过饱和, 相机抖动, "
        "lowres, blurry, flicker, artifacts, watermark, text, deformed, jitter"
    ),
}

# 规则引擎：主体/场景细节补充片段（原始提示过短时追加，避免空泛）
_RULE_DETAIL_TAIL = {
    "flux3_klein": ", intricate details, depth of field, ambient occlusion, ultra detailed",
    "qwen_image_2.1": "，细节层次丰富，明暗过渡自然，景深控制得当，画面干净",
    "minimax_h3": "，运动感与氛围感兼具，镜头语言明确，光影层次丰富",
}

# ---------------------------------------------------------------------------
# LLM system prompts (per model x language)
# ---------------------------------------------------------------------------
_LLM_SYS = {
    ("flux3_klein", "zh"): (
        "你是资深 AI 图像提示词工程师，专精 FLUX3 Image Klein 模型。"
        "把用户的中文粗略想法改写成一段可直接用于出图的详细图像提示词。要求："
        "1) 描述具体可画的视觉要素：主体、场景、构图、光线、材质、细节；"
        "2) 中文为主，可混合少量英文视觉关键词（如 cinematic lighting、8k）；"
        "3) 只输出改写后的提示词，不要解释、不要分段编号；"
        "4) 忠于用户原意，不添加原意之外的敏感或违规内容。"
    ),
    ("flux3_klein", "en"): (
        "You are a master prompt engineer for the FLUX3 Image Klein model. "
        "Rewrite the user's rough idea into a dense, concrete image prompt. "
        "Describe subject, scene, composition, lighting, materials and detail. "
        "Output only the rewritten prompt, no explanation."
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
        subject = "通用场景：自然光下的主体特写，层次分明" if target_model != "qwen_image_2.1" else "通用场景，自然光主体特写"

    # 短提示自动补场景细节
    if len(subject) < 12:
        subject = subject + tail

    if target_model == "qwen_image_2.1":
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
        "Chinese-first prompt enhancer for FLUX3 Klein / Qwen-Image 2.1 / MiniMax H3. "
        "Enhances a rough Chinese prompt into a detailed image prompt (positive + negative). "
        "Uses the local Strata LLM (auto-starts it when selected and offline) and falls back "
        "to a built-in rule engine."
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
                "engine": (["auto", "strata_local", "rule_only"], {"default": "auto"}),
                "language": (["zh", "en"], {"default": "zh"}),
                "max_tokens": ("INT", {"default": 512, "min": 64, "max": 2048, "step": 32}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.1, "max": 1.5, "step": 0.05}),
            },
            "optional": {
                "negative_hint": ("STRING", {"default": "", "multiline": True}),
                "system_prompt": ("STRING", {"default": "", "multiline": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "execute"
    CATEGORY = "BSAI/FLUX3"

    def execute(self, raw_prompt, target_model="flux3_klein", engine="auto",
                language="zh", max_tokens=512, temperature=0.7, negative_hint="",
                system_prompt=""):
        pos = None
        neg = None
        engine_used = "rule_only"

        use_llm = engine in ("auto", "strata_local")
        if use_llm:
            try:
                if not strata_health():
                    # Strata selected but offline → auto-start the backend and wait.
                    ensure_strata(log=print)
                if strata_health():
                    # Custom system prompt (e.g. official FLUX3 prompting SKILL methodology)
                    # overrides the built-in recipe prompt when provided.
                    sys_prompt = (system_prompt or "").strip() or _build_system(target_model, language)
                    messages = [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"用户的粗略想法：{raw_prompt}"},
                    ]
                    pos = strata_chat(messages, max_tokens=max_tokens, temperature=temperature)
                    engine_used = "strata_local"
            except Exception as e:
                pos = None
                print(f"[BSAI-FLUX3-Enhancer] Strata LLM failed, falling back to rule engine: {type(e).__name__}: {e}")

        if pos is None:
            pos, neg = _rule_enhance(raw_prompt, target_model)
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
