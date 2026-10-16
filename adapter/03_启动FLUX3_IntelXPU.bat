@echo off
setlocal
title BSAI FLUX3 快速启动 - Intel XPU/核显
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo ============================================================
echo   BSAI FLUX3 快速启动（Intel XPU 后端 / 默认端口 8194）
echo   模型：flux3_image_klein_sd_int8_convrot（INT8 量化档）
echo   适用：Arc 独显 / Arc 核显（Core Ultra）/ 无 NVIDIA 机型
echo   注意：XPU 侧共享内存，建议 >=16GB 物理内存；4K 出图会很慢
echo ============================================================

if not exist "%ROOT%\python_embeded\python.exe" (
    echo [ERROR] 未找到 python_embeded（XPU 运行时）
    pause & exit /b 1
)

"%ROOT%\python_embeded\python.exe" -s "%~dp0bsai_flux3_check.py" 2>nul
if errorlevel 1 (
    echo.
    echo [BSAI] 权重未就绪！请先运行 01_下载FLUX3权重.bat
    pause & exit /b 1
)

set OMNIXPU_ENABLE=1
set OMNIXPU_PROVIDER_BOOTSTRAP=auto
set OMNI_IMAGE_XPU_TARGET=bmg
set OMNI_ATTN_BACKEND=cute
set UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
set OMNIXPU_INTERPOLATE_FIX=0
set SOL_ATTN_XPU_EXPERIMENTAL=1
set OMNI_COMFYUI_RESERVE_VRAM_GB=4
set PYOPENGL_USE_ACCELERATE=false
set HF_ENDPOINT=https://hf-mirror.com
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,garbage_collection_threshold:0.6,max_split_size_mb:256
set TRANSFORMERS_DISABLE_DOCSTRING_VALIDATION=1

echo [BSAI] 启动 ComfyUI（XPU 后端）...
"%ROOT%\python_embeded\python.exe" -u -s ComfyUI\main.py ^
    --reserve-vram 4 --preview-method auto --windows-standalone-build ^
    --listen --port 8194 --async-offload --enable-dynamic-vram ^
    --database-url "sqlite:///ComfyUI/user/comfyui_8194.db" ^
    --fast --disable-comfy-compiler

pause
