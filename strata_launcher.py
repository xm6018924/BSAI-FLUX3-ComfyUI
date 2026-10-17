"""BSAI FLUX3 Enhancer — auto-start for the local Strata LLM backend.

When engine=strata_local (or auto) is selected and 127.0.0.1:8080 is not
serving models, this module spawns the same Strata launcher the user runs
manually, then polls until the backend becomes healthy (a real /models
response with at least one loaded model — guards against the classic
"process is up but port/model not ready" false success).

Only the standard library is used; safe to import from a ComfyUI node.
"""
import os
import subprocess
import threading
import time

STRATA_HOST = "127.0.0.1"
STRATA_PORT = 8080

_LOCK = threading.Lock()
_LAST_ATTEMPT = {"t": 0.0}          # guards against double-spawn from parallel queue items
_COOLDOWN_S = 20.0                  # if a spawn happened <20s ago, just wait for it
_DEFAULT_TIMEOUT = 180.0            # max seconds to wait for the backend to become healthy
_POLL_INTERVAL = 3.0

_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008


# ---------------------------------------------------------------------------
# Locating the Strata launcher (relative to this plugin's own location)
# ---------------------------------------------------------------------------
def _plugin_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _find_script():
    """Find run-q2_0.bat (or the legacy BSAI_Strata服务.bat) near this install."""
    here = _plugin_dir()                          # .../ComfyUI/custom_nodes/BSAI-FLUX3-Enhancer
    comfyui = os.path.dirname(os.path.dirname(here))  # .../ComfyUI
    root = os.path.dirname(comfyui)               # project root

    direct = os.path.join(root, "ComfyUI", "custom_nodes",
                          "BSAI-LLM-Strata", "Strata", "run-q2_0.bat")
    if os.path.isfile(direct):
        return direct

    # BSAI-LLM-Strata may live under a different ComfyUI/custom_nodes layout
    cn = os.path.join(comfyui, "custom_nodes")
    if os.path.isdir(cn):
        try:
            for entry in os.listdir(cn):
                if entry.lower().startswith("bsai-llm-strata"):
                    p = os.path.join(cn, entry, "Strata", "run-q2_0.bat")
                    if os.path.isfile(p):
                        return p
        except OSError:
            pass

    legacy = os.path.join(root, "BSAI_Strata服务.bat")
    if os.path.isfile(legacy):
        return legacy
    return None


# ---------------------------------------------------------------------------
# Health check + spawn + wait
# ---------------------------------------------------------------------------
def _healthy():
    try:
        from strata_client import strata_health
        return strata_health(timeout=2.0)
    except Exception:
        return False


def _spawn(script):
    """Fire-and-forget start of the .bat in its own directory, no console."""
    cmd = ["cmd.exe", "/c", script]
    return subprocess.Popen(
        cmd,
        cwd=os.path.dirname(script),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS,
        close_fds=True,
    )


def _wait_healthy(timeout, log):
    deadline = time.time() + timeout
    waited = 0.0
    while time.time() < deadline:
        time.sleep(_POLL_INTERVAL)
        waited += _POLL_INTERVAL
        if _healthy():
            log("[BSAI-FLUX3-Enhancer] Strata backend ready after ~%ds" % int(waited))
            return "started"
    log("[BSAI-FLUX3-Enhancer] Strata backend not healthy within %ds; falling back." % int(timeout))
    return "timeout"


def _port_open(timeout=2.0):
    """True when something is already listening on the Strata port (8080).

    A listening port means a Strata server is up — even if the model is still
    loading and /models is not ready yet. Never spawn a second instance then.
    """
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        r = s.connect_ex((STRATA_HOST, STRATA_PORT))
        s.close()
        return r == 0
    except Exception:
        return False


def _engine_process_running():
    """True when a Strata engine binary (strata.exe / strata-vision.exe) is alive.

    Covers the brief window where the model manager has started the engine but
    the HTTP server has not bound the port yet.
    """
    try:
        out = subprocess.run(
            ["tasklist", "/NH", "/FO", "CSV"], capture_output=True, text=True, timeout=10
        ).stdout or ""
        return ("strata.exe" in out) or ("strata-vision.exe" in out)
    except Exception:
        return False


def _manager_running():
    """True when the new-arch Strata Manager (8081) is up."""
    try:
        from strata_client import manager_running as _mr
        return _mr(timeout=2.0)
    except Exception:
        return False


# Guards against a parallel execution re-triggering a model load (each switch
# restarts the engine, which would interrupt an in-progress load).
_LAST_SWITCH = {"t": 0.0}
_SWITCH_COOLDOWN_S = 60.0


def _trigger_model_load(log):
    """Ask the already-running Manager to load the model (new arch, port 8081).

    Idempotent-ish: skips when the engine is already healthy, when the Manager
    reports the target model as current (still loading — do not interrupt), or
    when a switch was issued less than _SWITCH_COOLDOWN_S ago.
    """
    try:
        if _healthy():
            return
        from strata_client import (manager_current_model, manager_switch_model,
                                   MANAGER_QUANT)
    except Exception:
        return
    if not _manager_running():
        return
    now = time.time()
    if now - _LAST_SWITCH["t"] < _SWITCH_COOLDOWN_S:
        return
    current = manager_current_model()
    if current == MANAGER_QUANT:
        log("[BSAI-FLUX3-Enhancer] Strata manager: %s already loading; waiting (no re-switch)."
            % current)
        return
    try:
        status, body = manager_switch_model(MANAGER_QUANT)
        if status < 400:
            _LAST_SWITCH["t"] = now
            log("[BSAI-FLUX3-Enhancer] Strata manager: model load triggered (%s)."
                % MANAGER_QUANT)
        else:
            log("[BSAI-FLUX3-Enhancer] Strata manager switch failed: HTTP %s %s"
                % (status, body[:120]))
    except Exception as e:
        log("[BSAI-FLUX3-Enhancer] Strata manager switch error: %s" % e)


def _wait_manager(timeout=30.0, log=print):
    """Wait until the new-arch Manager (8081) is reachable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _manager_running():
            return True
        time.sleep(1.0)
    log("[BSAI-FLUX3-Enhancer] Strata manager not reachable within %ds." % int(timeout))
    return False


def ensure_strata(timeout=_DEFAULT_TIMEOUT, log=print):
    """Ensure the local Strata backend is running and healthy.

    Returns one of: "already_running" | "started" | "timeout" |
                    "no_script" | "spawn_error".

    Reuse-first (new arch): if any Strata instance is already present —
    engine healthy (/models has a model), new-arch Manager up (8081), port
    8080 listening, or engine process running — we never spawn a second one;
    we only trigger a model load when needed and wait for readiness.
    """
    if _healthy():
        return "already_running"

    with _LOCK:
        if _healthy():
            return "already_running"

        now = time.time()
        if now - _LAST_ATTEMPT["t"] < _COOLDOWN_S:
            # A spawn was just issued by a parallel execution; wait for it.
            return _wait_healthy(timeout, log)

        # A Strata instance is already starting/loading: never spawn a duplicate.
        if _manager_running() or _port_open() or _engine_process_running():
            log("[BSAI-FLUX3-Enhancer] Strata already starting/loading; waiting for it (no second instance).")
            _trigger_model_load(log)
            return _wait_healthy(timeout, log)

        script = _find_script()
        if not script:
            log("[BSAI-FLUX3-Enhancer] Strata launcher not found; keeping rule-engine fallback.")
            return "no_script"

        _LAST_ATTEMPT["t"] = now
        try:
            _spawn(script)
        except Exception as e:  # pragma: no cover - defensive
            log("[BSAI-FLUX3-Enhancer] Strata auto-start spawn failed: %s" % e)
            return "spawn_error"
        log("[BSAI-FLUX3-Enhancer] Strata auto-start: launched %s" % script)

    _wait_manager(log=log)
    _trigger_model_load(log)
    return _wait_healthy(timeout, log)


# ---------------------------------------------------------------------------
# Standalone smoke test (optional): python strata_launcher.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("script found:", _find_script())
    print("ensure_strata ->", ensure_strata(timeout=60))
