@echo off
setlocal
title BSAI FLUX3 快速启动 - NVIDIA 5090 (CUDA)
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo ============================================================
echo   BSAI FLUX3 快速启动（NVIDIA CUDA 后端 / 默认端口 8193）
echo   模型：flux3_image_klein_sd_int8_convrot（8G 档）
echo         或改 flux3_image_klein_sd_bf16（画质档，5090 推荐）
echo ============================================================

if not exist "%ROOT%\python_embeded_cuda\python.exe" (
    echo [ERROR] 未找到 python_embeded_cuda 运行时
    pause & exit /b 1
)

"%ROOT%\python_embeded\python.exe" -s "%~dp0bsai_flux3_check.py" 2>nul
if errorlevel 1 (
    echo.
    echo [BSAI] 权重未就绪！请先运行 01_下载FLUX3权重.bat
    pause & exit /b 1
)

set OMNIXPU_ENABLE=0
set PYOPENGL_USE_ACCELERATE=false
set HF_ENDPOINT=https://hf-mirror.com
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,garbage_collection_threshold:0.6,max_split_size_mb:256
set VDN_H3_WINDOW_SDPA=mem_efficient
set BSAI_H3_LLM_GPU_LAYERS=0
set TRANSFORMERS_DISABLE_DOCSTRING_VALIDATION=1

echo [BSAI] 启动 ComfyUI（CUDA + sage-attention）...
"%ROOT%\python_embeded_cuda\python.exe" -u -s ComfyUI\main.py ^
    --reserve-vram 1 --cuda-malloc --preview-method auto ^
    --windows-standalone-build --listen --port 8193 ^
    --async-offload --enable-dynamic-vram ^
    --database-url "sqlite:///ComfyUI/user/comfyui_8193.db" ^
    --fast --use-sage-attention --disable-comfy-compiler

pause
