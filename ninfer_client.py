"""BSAI FLUX3 Enhancer — bundled NInfer engine client.

Ports the ninfer-serve.exe engine originally shipped in
ComfyUI-AIManzi-MultimodalPrompt into this plugin. The engine is an
OpenAI-compatible local LLM server (text-only, no vision) that we launch
on demand from the resolved engine dir (``ENGINE_DIR``, see
``_resolve_engine_dir`` — own ``./engine/`` first, then a sibling plugin's).

Design notes
------------
* Port 8082 is used on purpose: Strata already owns 127.0.0.1:8080 and the
  Strata Manager owns 8081. 8082 leaves both existing services untouched.
* HTTP uses the same blocking-socket pattern as ``strata_client.py`` —
  avoids WinError 10035 / asyncio issues under Python 3.14 on Windows.
* GPU profile is picked from ``nvidia-smi --query-gpu=compute_cap``:
    >= 12.0 -> ninfer-sm120 (RTX 50-series)
    >=  8.9 -> ninfer-sm89  (RTX 40-series)
  anything else raises a clear error.
* Model discovery scans ``ComfyUI/models/LLM`` recursively for ``*.ninfer``
  files and prefers ``Ternary-Bonsai-2-27B.ninfer`` (small, fast, ~8 GiB).
* Thinking is disabled (``--no-thinking``) because this enhancer only
  rewrites a rough prompt — no chain-of-thought needed, and disabling it
  saves VRAM / KV context and cuts startup time.
"""
from __future__ import annotations

import gc
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import folder_paths  # ComfyUI-provided
except ImportError:  # standalone / diagnostic import
    folder_paths = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_PLUGIN_DIR = Path(__file__).resolve().parent


def _resolve_engine_dir() -> Path:
    """Engine dir bundling ninfer-sm<XX>/ + runtime/ (may live in another plugin).

    The binaries are too large for git and are not redistributed here, so fall
    back to $BSAI_NINFER_ENGINE_DIR, the upstream AIManzi plugin, or any
    sibling custom_nodes plugin that already carries an engine dir.
    """
    env_dir = os.environ.get("BSAI_NINFER_ENGINE_DIR", "").strip()
    cands = ([Path(env_dir)] if env_dir else []) + [
        _PLUGIN_DIR / "engine",
        _PLUGIN_DIR.parent / "ComfyUI-AIManzi-MultimodalPrompt" / "engine",
    ]
    try:
        cands += sorted(p / "engine" for p in _PLUGIN_DIR.parent.iterdir() if p.is_dir())
    except OSError:
        pass
    for d in cands:
        if any((d / sub / "ninfer-serve.exe").is_file()
               for sub in ("ninfer-sm120", "ninfer-sm89")):
            return d
    return _PLUGIN_DIR / "engine"


ENGINE_DIR = _resolve_engine_dir()

NINFER_HOST = "127.0.0.1"
NINFER_PORT = 8082
NINFER_BASE_URL = f"http://{NINFER_HOST}:{NINFER_PORT}/v1"

# 8k context is more than enough for a system prompt + a rough idea + a
# dense rewritten prompt. The engine will still accept larger values, but
# KV cache is allocated up front and we want to leave VRAM for diffusion.
NINFER_CONTEXT_TOKENS = 8192
NINFER_STARTUP_TIMEOUT = 180  # seconds, cold load of ~8 GiB model
NINFER_CHAT_TIMEOUT = 180

# Preferred model filename when auto-matching.
PREFERRED_NINFER_MODEL = "Ternary-Bonsai-2-27B.ninfer"

# Process handle of the ninfer-serve.exe we started this session.
_OWNED_PROCESS: subprocess.Popen | None = None
# Absolute path of the model currently loaded by the running server. Used to
# detect when the user switches models in the widget and a reload is needed.
_LOADED_MODEL_PATH: str | None = None


# ---------------------------------------------------------------------------
# Blocking HTTP helpers (mirrors strata_client.py)
# ---------------------------------------------------------------------------
def _open_sock(host: str, port: int, timeout: float) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.setblocking(True)
    s.connect((host, port))
    return s


def _blocking_get(path: str, timeout: float = 3.0):
    p = urlparse(NINFER_BASE_URL)
    s = _open_sock(p.hostname, p.port or 80, timeout)
    try:
        conn = http.client.HTTPConnection(p.hostname, p.port or 80, timeout=timeout)
        conn.sock = s
        conn.request("GET", path or "/", headers={"Accept": "application/json"})
        r = conn.getresponse()
        body = r.read().decode("utf-8", "replace")
        return r.status, body
    finally:
        try:
            s.close()
        except Exception:
            pass


def _blocking_post(path: str, body_bytes: bytes, timeout: float = 60.0):
    p = urlparse(NINFER_BASE_URL)
    s = _open_sock(p.hostname, p.port or 80, timeout)
    try:
        conn = http.client.HTTPConnection(p.hostname, p.port or 80, timeout=timeout)
        conn.sock = s
        conn.request(
            "POST", path or "/", body=body_bytes,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body_bytes)),
            },
        )
        r = conn.getresponse()
        body = r.read().decode("utf-8", "replace")
        return r.status, body
    finally:
        try:
            s.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# GPU / engine profile
# ---------------------------------------------------------------------------
@__import__("functools").lru_cache(maxsize=1)
def _gpu_profile() -> dict:
    """Return the bundled NInfer profile for this NVIDIA GPU.

    Raises RuntimeError with a human-readable message when the GPU is not
    supported or nvidia-smi is unavailable.
    """
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        )
        cap = float(out.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
        raise RuntimeError(
            "NInfer 需要受支持的 NVIDIA 显卡及 nvidia-smi。"
        ) from exc

    if cap >= 12.0:
        engine_sub = "ninfer-sm120"
    elif cap >= 8.9:
        engine_sub = "ninfer-sm89"
    else:
        raise RuntimeError(
            "内置 NInfer 引擎仅支持 RTX 40 系 (sm89) 与 RTX 50 系 (sm120) 显卡。"
        )

    exe = ENGINE_DIR / engine_sub / "ninfer-serve.exe"
    if not exe.is_file():
        raise RuntimeError(
            f"当前 GPU 对应引擎缺失：{exe}。NInfer 引擎体积过大，不随插件分发："
            "请安装 ComfyUI-AIManzi-MultimodalPrompt 插件（自带 engine/），"
            "或把 engine/ 放到本插件目录，或设置环境变量 BSAI_NINFER_ENGINE_DIR。"
        )
    return {
        "engine_dir": engine_sub,
        "exe": exe,
        "kv_dtype": "fp8",
    }


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------
def _llm_root() -> Path:
    """ComfyUI/models/LLM without persisting a drive letter."""
    if folder_paths is not None and getattr(folder_paths, "models_dir", None):
        return Path(os.path.abspath(folder_paths.models_dir)) / "LLM"
    # Standalone fallback: .../ComfyUI/models/LLM
    return (Path(__file__).resolve().parents[2] / "models" / "LLM")


@__import__("functools").lru_cache(maxsize=1)
def _scan_ninfer_models() -> list[Path]:
    root = _llm_root()
    if not root.is_dir():
        return []
    return sorted(
        (p for p in root.rglob("*.ninfer") if p.is_file()),
        key=lambda p: p.name.lower(),
    )


def list_ninfer_model_names() -> list[str]:
    """Return basenames of all discovered .ninfer files (for the ComfyUI dropdown).

    PREFERRED_NINFER_MODEL is surfaced first when present; otherwise the list
    falls back to alphabetical order. If no model exists, returns a single
    placeholder so the widget still renders.
    """
    models = _scan_ninfer_models()
    if not models:
        return ["未找到 .ninfer 模型"]
    names = [m.name for m in models]
    preferred = PREFERRED_NINFER_MODEL
    if preferred in names:
        names = [preferred] + [n for n in names if n != preferred]
    return names


def find_ninfer_model(selected_name: str | None = None) -> Path:
    """Resolve a .ninfer model path.

    If ``selected_name`` is given, match it by basename against the discovered
    list. Otherwise prefer PREFERRED_NINFER_MODEL and fall back to the first
    discovered model. Raises RuntimeError when nothing is found.
    """
    models = _scan_ninfer_models()
    if not models:
        raise RuntimeError(
            f"未找到任何 .ninfer 模型。请将模型放入 ComfyUI 的 {_llm_root()} 目录。"
        )
    if selected_name:
        for m in models:
            if m.name == selected_name:
                return m
        raise RuntimeError(
            f"未找到模型“{selected_name}”。请确认文件仍在 {_llm_root()} 下。"
        )
    for m in models:
        if m.name.lower() == PREFERRED_NINFER_MODEL.lower():
            return m
    return models[0]


# ---------------------------------------------------------------------------
# VRAM release (best-effort)
# ---------------------------------------------------------------------------
def _release_comfy_vram() -> None:
    """Ask ComfyUI to unload diffusion models before a ~8 GiB LLM load."""
    try:
        import comfy.model_management as mm  # type: ignore
        mm.unload_all_models()
        try:
            mm.soft_empty_cache(True)
        except TypeError:
            mm.soft_empty_cache()
    except (ImportError, AttributeError):
        pass
    gc.collect()
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------
def _server_alive(timeout: float = 2.0) -> bool:
    try:
        status, _ = _blocking_get("/v1/models", timeout=timeout)
        return status < 400
    except Exception:
        return False


def _build_command(model: Path, profile: dict) -> list[str]:
    return [
        str(profile["exe"]),
        str(model),
        "--host", NINFER_HOST,
        "--port", str(NINFER_PORT),
        "--max-context", str(NINFER_CONTEXT_TOKENS),
        "--kv-capacity", str(NINFER_CONTEXT_TOKENS),
        "--max-concurrency", "1",
        "--kv-dtype", profile["kv_dtype"],
        "--default-max-tokens", str(NINFER_CONTEXT_TOKENS),
        "--no-thinking",
    ]


def _build_env(profile: dict) -> dict:
    runtime = ENGINE_DIR / "runtime"
    engine_bin_dir = profile["exe"].parent
    env = os.environ.copy()
    # Prepend our bundled runtime DLLs so VCRUNTIME/MSVCP/av* resolve.
    env["PATH"] = (
        str(engine_bin_dir) + os.pathsep + str(runtime) + os.pathsep + env.get("PATH", "")
    )
    return env


def _startup_log_tail(lines: int = 25) -> str:
    log = ENGINE_DIR / "ninfer-startup.log"
    try:
        content = log.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:]) or "(引擎未输出日志)"
    except OSError:
        return "(未生成引擎日志)"


def _iter_our_ninfer_processes():
    """Yield psutil.Process objects for ninfer-serve.exe launched from OUR engine dir.

    Uses process_iter rather than net_connections because the latter requires
    elevated privileges on Windows and fails silently under a normal ComfyUI.
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        return
    engine_root = ENGINE_DIR.resolve()
    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name != "ninfer-serve.exe":
                continue
            exe = Path(proc.info.get("exe") or "").resolve()
            if engine_root not in exe.parents:
                continue
            yield proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
            continue


def _adopt_orphan(model_key: str) -> bool:
    """If an orphan ninfer-serve.exe already has the requested model and port, adopt it.

    Avoids a 30s cold start after a ComfyUI restart when the previously
    launched engine is still resident with the same weights.
    """
    wanted_port = f"--port {NINFER_PORT}"
    wanted_model = model_key.lower()
    for proc in _iter_our_ninfer_processes():
        try:
            cmdline = " ".join(proc.cmdline()).lower()
        except Exception:
            continue
        if wanted_port not in cmdline:
            continue
        if wanted_model not in cmdline:
            continue
        global _OWNED_PROCESS, _LOADED_MODEL_PATH
        _LOADED_MODEL_PATH = model_key
        class _Adopted:
            def __init__(self, p): self._p = p
            def poll(self): return None if self._p.is_running() else 0
            def terminate(self): self._p.terminate()
            def kill(self): self._p.kill()
            def wait(self, timeout=None): self._p.wait(timeout=timeout)
        _OWNED_PROCESS = _Adopted(proc)  # type: ignore[assignment]
        try:
            _server_model_id.cache_clear()  # type: ignore[attr-defined]
        except Exception:
            pass
        print(f"[BSAI-FLUX3-Enhancer] adopted resident ninfer process for {Path(model_key).name}")
        return True
    return False


def _kill_orphan_on_port() -> bool:
    """Terminate any ninfer-serve.exe from OUR engine dir listening on NINFER_PORT."""
    killed = False
    wanted_port = f"--port {NINFER_PORT}"
    for proc in _iter_our_ninfer_processes():
        try:
            cmdline = " ".join(proc.cmdline()).lower()
        except Exception:
            continue
        if wanted_port not in cmdline:
            continue
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
                proc.wait(timeout=10)
            killed = True
        except Exception:
            pass
    return killed


def _terminate_owned_server() -> None:
    """Kill the ninfer-serve.exe we own (if any) and forget its state."""
    global _OWNED_PROCESS, _LOADED_MODEL_PATH
    proc = _OWNED_PROCESS
    if proc is not None:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
                    proc.wait(timeout=10)
        except Exception:
            pass
    _OWNED_PROCESS = None
    _LOADED_MODEL_PATH = None
    try:
        _server_model_id.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass


def ensure_ninfer(model_name: str | None = None) -> None:
    """Start (or reuse) the bundled ninfer-serve.exe with the requested model.

    Safe to call on every execute():
    * A healthy server already running the requested model is reused.
    * A healthy server running a *different* model is terminated and relaunched.
    * No server -> launches one.
    """
    global _LOADED_MODEL_PATH, _OWNED_PROCESS

    profile = _gpu_profile()
    model = find_ninfer_model(model_name)
    model_key = str(model)

    # Fast path: a healthy server already has the model we want.
    if _server_alive(timeout=2.0) and _LOADED_MODEL_PATH == model_key:
        return

    # If we have no record of the running process (e.g. after a ComfyUI
    # restart), see whether the resident orphan already has this model.
    if _server_alive(timeout=2.0) and _LOADED_MODEL_PATH is None:
        if _adopt_orphan(model_key):
            return

    # A server alive but loaded with a different model must be restarted.
    if _server_alive(timeout=2.0) and _LOADED_MODEL_PATH != model_key:
        prev = Path(_LOADED_MODEL_PATH).name if _LOADED_MODEL_PATH else "(orphan)"
        print(f"[BSAI-FLUX3-Enhancer] ninfer model switch: {prev} -> {model.name}, restarting engine...")
        _terminate_owned_server()
        # If the port is still occupied after killing our Popen handle, we may
        # be looking at an orphan from a previous ComfyUI session.
        if _server_alive(timeout=1.0):
            _kill_orphan_on_port()
        for _ in range(30):
            if not _server_alive(timeout=1.0):
                break
            time.sleep(0.2)

    if _OWNED_PROCESS is not None and _OWNED_PROCESS.poll() is not None:
        _OWNED_PROCESS = None

    _release_comfy_vram()

    command = _build_command(model, profile)
    log_path = ENGINE_DIR / "ninfer-startup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} start ---\n")
        log_file.flush()
        _OWNED_PROCESS = subprocess.Popen(
            command,
            shell=False,
            cwd=str(_PLUGIN_DIR),
            env=_build_env(profile),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    deadline = time.time() + NINFER_STARTUP_TIMEOUT
    while time.time() < deadline:
        if _server_alive(timeout=1.5):
            _LOADED_MODEL_PATH = model_key
            try:
                _server_model_id.cache_clear()  # type: ignore[attr-defined]
            except Exception:
                pass
            print(
                f"[BSAI-FLUX3-Enhancer] ninfer engine ready "
                f"({time.perf_counter() - started:.1f}s), model={model.name}"
            )
            return
        if _OWNED_PROCESS.poll() is not None:
            detail = _startup_log_tail()
            raise RuntimeError(
                f"内置 NInfer 启动后立即退出。引擎日志：\n{detail}"
            )
        time.sleep(0.25)

    detail = _startup_log_tail()
    raise RuntimeError(
        f"内置 NInfer 启动超时（{NINFER_STARTUP_TIMEOUT}s）。引擎日志：\n{detail}"
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
_THINK_RE = re.compile(
    r"<(?:think|thinking|analysis|reasoning)>.*?</(?:think|thinking|analysis|reasoning)>\s*",
    flags=re.IGNORECASE | re.DOTALL,
)


def _clean_answer(text: str) -> str:
    """Strip <think>...</think> blocks and common wrapper fences."""
    out = (text or "").strip()
    out = _THINK_RE.sub("", out).strip()
    out = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", out, flags=re.IGNORECASE).strip()
    return out


def ninfer_chat(messages: list[dict], max_tokens: int = 512,
                temperature: float = 0.7, timeout: float | None = None,
                model_name: str | None = None) -> str:
    """One-shot chat completion against the bundled ninfer-serve.exe.

    Parameters mirror ``strata_client.strata_chat`` so the enhancer can
    swap them by name. ``model_name`` selects which .ninfer artifact to
    load (basename under models/LLM); defaults to PREFERRED_NINFER_MODEL.
    """
    ensure_ninfer(model_name=model_name)

    body = json.dumps({
        "model": _server_model_id(),
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "stream": False,
    }).encode("utf-8")

    status, raw = _blocking_post(
        "/v1/chat/completions", body,
        timeout=timeout or NINFER_CHAT_TIMEOUT,
    )
    if status >= 400:
        raise RuntimeError(f"NInfer HTTP {status}: {raw[:300]}")

    data = json.loads(raw)
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    answer = _clean_answer(str(content))
    if not answer:
        raise RuntimeError("NInfer 返回空内容。")
    return answer


def ninfer_health(timeout: float = 2.0) -> bool:
    """True when the bundled ninfer engine is reachable on 8082."""
    return _server_alive(timeout=timeout)


@__import__("functools").lru_cache(maxsize=1)
def _server_model_id() -> str:
    """Ask the running engine which model artifact it has loaded.

    The engine exposes its own id (e.g. ``qwen3.8-27b``) via /v1/models;
    sending any other string yields a 404 model_not_found.
    """
    try:
        status, body = _blocking_get("/v1/models", timeout=3.0)
        if status < 400:
            data = json.loads(body)
            return str(data["data"][0]["id"])
    except Exception:
        pass
    return "qwen3.8-27b"  # fallback for Ternary-Bonsai-2-27B.ninfer
