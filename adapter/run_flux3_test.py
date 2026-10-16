"""FLUX3 Klein 实测驱动脚本：提交 ComfyUI API 工作流，计时 + 采样显存，输出报告。

前提：ComfyUI 已启动（02_启动FLUX3_5090.bat / 03_启动FLUX3_IntelXPU.bat）。

用法：
  python run_flux3_test.py                          # 默认 http://127.0.0.1:8193
  python run_flux3_test.py --url http://127.0.0.1:8194 --steps 16 --size 1024
  python run_flux3_test.py --model flux3_image_klein_sd_bf16.safetensors --clip qwen3vl_4b_bf16.safetensors
"""
import argparse
import json
import os
import sys
import time
import threading
import urllib.request
import subprocess

WORKFLOW = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "workflows", "flux3_klein_t2i_api.json")


def _post_json(url, obj, timeout=60):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _vram_watcher(stop_event, results):
    """每 0.3s 采样 nvidia-smi 显存使用，记录峰值。"""
    peak = 0
    while not stop_event.is_set():
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            val = max(int(x) for x in out.splitlines() if x.strip().isdigit())
            peak = max(peak, val)
        except Exception:
            pass
        time.sleep(0.3)
    results["peak_mb"] = peak


def main():
    ap = argparse.ArgumentParser(description="FLUX3 Klein 实测驱动")
    ap.add_argument("--url", default="http://127.0.0.1:8193")
    ap.add_argument("--workflow", default=WORKFLOW)
    ap.add_argument("--prompt", default="一只在雨夜霓虹灯下的流浪猫，毛发湿漉漉，专业摄影构图，电影感光影，细节丰富")
    ap.add_argument("--model", default="flux3_image_klein_sd_int8_convrot.safetensors")
    ap.add_argument("--clip", default="qwen3vl_4b_int8_convrot.safetensors")
    ap.add_argument("--vae", default="flux2-vae.safetensors")
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    # 健康检查
    try:
        stats = _get_json(args.url + "/system_stats")
        devs = [d.get("name", "?") for d in stats.get("devices", [])]
        print(f"[BSAI] ComfyUI 已连接 @ {args.url}  设备: {devs}")
    except Exception as e:
        print(f"[BSAI] 无法连接 {args.url}：{e}")
        print("[BSAI] 请先启动 ComfyUI（02/03 启动脚本）。")
        sys.exit(1)

    wf = json.load(open(args.workflow, encoding="utf-8"))
    wf["4"]["inputs"]["unet_name"] = args.model
    wf["10"]["inputs"]["clip_name"] = args.clip
    wf["8"]["inputs"]["vae_name"] = args.vae
    wf["3"]["inputs"]["steps"] = args.steps
    wf["3"]["inputs"]["seed"] = args.seed
    wf["5"]["inputs"]["width"] = args.size
    wf["5"]["inputs"]["height"] = args.size
    wf["6"]["inputs"]["text"] = args.prompt

    stop = threading.Event()
    vram = {}
    watcher = threading.Thread(target=_vram_watcher, args=(stop, vram), daemon=True)
    watcher.start()

    print(f"[BSAI] 提交任务: model={args.model} steps={args.steps} size={args.size}x{args.size}")
    t0 = time.time()
    try:
        resp = _post_json(args.url + "/prompt", {"prompt": wf}, timeout=60)
    except Exception as e:
        stop.set()
        print(f"[BSAI] 提交失败: {e}")
        sys.exit(1)
    pid = resp.get("prompt_id")
    if not pid:
        stop.set()
        print(f"[BSAI] 提交响应异常: {json.dumps(resp, ensure_ascii=False)[:500]}")
        sys.exit(1)
    print(f"[BSAI] prompt_id={pid}  等待生成…")

    # 轮询 /history
    last_status = ""
    while True:
        try:
            hist = _get_json(args.url + f"/history/{pid}")
            if pid in hist:
                entry = hist[pid]
                status = entry.get("status", {})
                if status.get("completed", False):
                    t1 = time.time()
                    stop.set()
                    outs = entry.get("outputs", {})
                    imgs = []
                    for nid, out in outs.items():
                        for im in out.get("images", []):
                            imgs.append(im.get("filename"))
                    print(f"\n[BSAI] 生成完成！耗时 {t1-t0:.1f}s  峰值显存 {vram.get('peak_mb', 'N/A')} MB")
                    print(f"[BSAI] 输出图: {imgs}")
                    # 输出文件实际在 ComfyUI/output 下
                    return 0
                elif status.get("status_str") != last_status:
                    last_status = status.get("status_str", "")
                    print(f"[BSAI] 状态: {last_status}")
        except Exception as e:
            pass
        time.sleep(1.0)


if __name__ == "__main__":
    sys.exit(main())
