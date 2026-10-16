@echo off
setlocal
title BSAI FLUX3 权重一键下载（断点续传）
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo ============================================================
echo   BSAI FLUX3 Klein 权重一键下载（hf-mirror + aria2 多线程）
echo   约 30GB，支持断点续传；下载后可随时中断重启继续
echo ============================================================

if not exist "%~dp0_download_list.txt" (
    echo [ERROR] 未找到 _download_list.txt
    pause & exit /b 1
)

if not exist "%ROOT%\.launcher\aria2c.exe" (
    echo [ERROR] 未找到 aria2c.exe（.launcher\aria2c.exe）
    pause & exit /b 1
)

echo [BSAI] 启动 aria2 下载（16 线程/文件，断点续传）...
"%ROOT%\.launcher\aria2c.exe" --continue=true -x 16 -s 16 -k 4M ^
    --file-allocation=none --auto-file-renaming=false --allow-overwrite=false ^
    -i "%~dp0_download_list.txt" --console-log-level=notice --summary-interval=60 ^
    --log="%~dp0_download.log"

echo.
echo [BSAI] 下载结束，开始完整性检查...
"%ROOT%\python_embeded\python.exe" -s "%~dp0bsai_flux3_check.py"
if errorlevel 1 (
    echo [BSAI] 仍有缺失/不完整文件，可再次运行本脚本续传。
) else (
    echo [BSAI] 全部就绪，可以启动 FLUX3 了！
)
pause
