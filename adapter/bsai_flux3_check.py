"""BSAI FLUX3 模型完整性检查（Windows/ComfyUI 本地版）。

检查 ComfyUI/models 下 FLUX3 Klein 所需权重是否就位（存在 + 最低体积），
输出 OK / MISSING / SIZE_WARN 清单。退出码 0 = 全部就绪。

用法： python bsai_flux3_check.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 发行版根目录
MODELS = os.path.join(ROOT, "ComfyUI", "models")

# (相对路径, 最低体积MB, 说明)
REQUIRED = [
    ("diffusion_models/flux3_image_klein_sd_int8_convrot.safetensors", 5000,
     "蒸馏版 INT8（8G 显存档，首选）"),
    ("diffusion_models/flux3_image_klein_sd_bf16.safetensors", 9000,
     "蒸馏版 BF16（16G+ 显存档，画质更佳）"),
    ("diffusion_models/flux3_image_klein_int8_convrot.safetensors", 5000,
     "基础版 INT8（可选，微调/LoRA 用）"),
    ("diffusion_models/flux3_image_klein_bf16.safetensors", 9000,
     "基础版 BF16（可选，微调/LoRA 用）"),
    ("text_encoders/qwen3vl_4b_int8_convrot.safetensors", 4000,
     "文本编码器 INT8（8G 档）"),
    ("text_encoders/qwen3vl_4b_bf16.safetensors", 7000,
     "文本编码器 BF16（16G+ 档）"),
    ("text_encoders/qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors", 8000,
     "官方提示词上采样器 INT8（可选，增强画质/细节）"),
    ("vae/flux2-vae.safetensors", 250,
     "VAE（必需）"),
]


def main():
    missing = []
    warn = []
    ok = 0
    print("=" * 70)
    print("[BSAI] FLUX3 Klein 模型完整性检查")
    print(f"[BSAI] models 目录: {MODELS}")
    print("=" * 70)
    for rel, min_mb, note in REQUIRED:
        path = os.path.join(MODELS, rel)
        if not os.path.exists(path):
            missing.append((rel, note))
            print(f"  [缺] {rel}  {note}")
            continue
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb < min_mb:
            warn.append((rel, size_mb, min_mb, note))
            print(f"  [!体积异常] {rel}  {size_mb:.0f}MB < {min_mb}MB  {note}")
            continue
        ok += 1
        print(f"  [OK] {rel}  {size_mb/1024:.2f}GB  {note}")

    print("-" * 70)
    print(f"就绪 {ok}/{len(REQUIRED)}")
    if missing:
        print("缺文件：请运行 01_下载FLUX3权重.bat 补齐后再启动。")
        for rel, note in missing:
            print(f"  - {rel}（{note}）")
    if warn:
        print("体积警告：文件可能未下载完整，请重新续传下载。")
    print("=" * 70)
    return 0 if not missing and not warn else 1


if __name__ == "__main__":
    sys.exit(main())
