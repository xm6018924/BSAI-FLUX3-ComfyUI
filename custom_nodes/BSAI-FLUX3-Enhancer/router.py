"""BSAI_FLUX3_PromptRouter: a lazy 3-tier prompt selector for FLUX3 workflows.

Selects which prompt pipeline feeds the positive/negative CLIPTextEncode:
  mode="raw"       -> the typed raw prompt (no processing)
  mode="enhancer"  -> output of BSAI_FLUX3_PromptEnhancer (rule engine / Strata LLM)
  mode="upsampler" -> output of ComfyUI's native TextGenerate running the official
                      FLUX3 prompt upsampler (qwen3.5-9B, Apache-2.0)

Lazy execution (check_lazy_status): only the selected branch is computed, so the
9GB upsampler is NOT loaded unless mode="upsampler".
"""
# Fixed English negative blacklist used by the raw / upsampler tiers.
DEFAULT_NEGATIVE = (
    "lowres, bad anatomy, bad hands, missing fingers, extra digits, blurry, "
    "jpeg artifacts, watermark, text, signature, deformed, ugly, oversaturated"
)


class BSAI_FLUX3_PromptRouter:
    """Route among the three prompt pipelines. English UI + Chinese search aliases."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["raw", "enhancer", "upsampler"], {"default": "enhancer"}),
                "raw_prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_fallback": ("STRING", {"multiline": True, "default": DEFAULT_NEGATIVE}),
            },
            "optional": {
                "enhanced_positive": ("STRING", {"forceInput": True}),
                "enhanced_negative": ("STRING", {"forceInput": True}),
                "upsampled": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "route"
    CATEGORY = "BSAI/FLUX3"
    DESCRIPTION = (
        "Select which prompt pipeline feeds positive/negative conditioning. "
        "raw: no processing; enhancer: BSAI FLUX3 Prompt Enhancer output "
        "(rule_only / Strata LLM); upsampler: official FLUX3 prompt upsampler "
        "via TextGenerate. Lazy: only the selected branch executes."
    )
    SEARCH_ALIASES = [
        "tier", "prompt router", "prompt selector", "3 tier",
        "三档", "档位", "提示词路由", "提示词选择",
    ]

    def check_lazy_status(self, mode, raw_prompt="", negative_fallback=DEFAULT_NEGATIVE,
                          enhanced_positive=None, enhanced_negative=None, upsampled=None):
        if mode == "enhancer":
            return ["enhanced_positive", "enhanced_negative"]
        if mode == "upsampler":
            return ["upsampled"]
        return []

    def route(self, mode, raw_prompt="", negative_fallback=DEFAULT_NEGATIVE,
              enhanced_positive=None, enhanced_negative=None, upsampled=None):
        if mode == "enhancer":
            positive = (enhanced_positive or "").strip()
            negative = (enhanced_negative or "").strip()
        elif mode == "upsampler":
            positive = (upsampled or "").strip()
            negative = (negative_fallback or "").strip()
        else:  # raw
            positive = (raw_prompt or "").strip()
            negative = (negative_fallback or "").strip()
        return (positive, negative)
