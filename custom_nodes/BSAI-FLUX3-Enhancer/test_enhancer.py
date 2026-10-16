"""Standalone test for BSAI-FLUX3-Enhancer (no ComfyUI server required).

Usage:
  python test_enhancer.py                      # rule engine (rule_only)
  python test_enhancer.py --engine auto        # Strata LLM if available, else rule fallback
  python test_enhancer.py --model qwen_image_2.1 --lang zh
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from enhancer import BSAI_FLUX3_PromptEnhancer, MODEL_OPTIONS  # noqa: E402
from strata_client import strata_health  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="BSAI FLUX3 Prompt Enhancer test harness")
    ap.add_argument("--prompt", default="A stray tabby cat under neon lights on a rainy night, wet fur")
    ap.add_argument("--model", choices=MODEL_OPTIONS, default="flux3_klein")
    ap.add_argument("--engine", choices=["auto", "strata_local", "rule_only"], default="rule_only")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--max_tokens", type=int, default=512)
    args = ap.parse_args()

    print("=" * 72)
    print("[BSAI-FLUX3-Enhancer] test start")
    print(f"  raw prompt  : {args.prompt}")
    print(f"  target model: {args.model}")
    print(f"  engine      : {args.engine}")
    print(f"  language    : {args.lang}")
    print(f"  Strata      : {'running' if strata_health() else 'not running'}")
    print("=" * 72)

    node = BSAI_FLUX3_PromptEnhancer()
    positive, negative = node.execute(
        raw_prompt=args.prompt,
        target_model=args.model,
        engine=args.engine,
        language=args.lang,
        max_tokens=args.max_tokens,
        temperature=0.7,
    )

    print("\n[enhanced positive]")
    print(positive)
    print("\n[negative]")
    print(negative)
    print("\n[check]")
    if positive and negative:
        print(f"  ✓ positive / negative both non-empty")
        print(f"  ✓ positive length {len(positive)} chars")
    else:
        print("  ✗ empty output, please investigate")
        sys.exit(1)


if __name__ == "__main__":
    main()
