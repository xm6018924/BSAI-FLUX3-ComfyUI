"""BSAI-FLUX3-Enhancer: a Chinese-first, lightweight prompt enhancer
(FLUX3 Klein / Qwen-Image 2.1 / MiniMax H3) for ComfyUI.

- Local Strata LLM enhancement (127.0.0.1:8080/v1) with automatic
  fallback to a deterministic rule engine when Strata is offline.
- Independent of FLUX weights / outputs: no FLUX Kommunity License risk.

中文辅助说明：节点 UI 为英文（符合 ComfyUI 自定义节点规范），
中文体验通过 README.zh-CN.md 与节点搜索中文别名提供。
"""
from .enhancer import BSAI_FLUX3_PromptEnhancer

NODE_CLASS_MAPPINGS = {
    "BSAI_FLUX3_PromptEnhancer": BSAI_FLUX3_PromptEnhancer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BSAI_FLUX3_PromptEnhancer": "BSAI FLUX3 Prompt Enhancer (CN-First)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
