"""BSAI FLUX3 Enhancer — minimal local Strata client (blocking sockets).

Reuses the same HTTP contract as BSAI-LLM-Strata (127.0.0.1:8080/v1).
Blocking-socket implementation avoids WinError 10035 under Python 3.14 asyncio.
"""
import json
import socket
import http.client
from urllib.parse import urlparse

STRATA_HOST = "127.0.0.1"
STRATA_PORT = 8080
STRATA_BASE_URL = f"http://{STRATA_HOST}:{STRATA_PORT}/v1"
STRATA_MODEL = "qwen3.8-flash-next"


def _open_sock(host, port, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.setblocking(True)
    s.connect((host, port))
    return s


def _blocking_get_json(path, timeout=3.0, headers=None):
    p = urlparse(STRATA_BASE_URL + path)
    host, port = p.hostname, p.port or 80
    s = _open_sock(host, port, timeout)
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.sock = s
        h = {"Accept": "application/json"}
        if headers:
            h.update(headers)
        conn.request("GET", p.path or "/", headers=h)
        r = conn.getresponse()
        body = r.read().decode("utf-8", "replace")
        return r.status, body
    finally:
        try:
            s.close()
        except Exception:
            pass


def _blocking_post_json(path, body_bytes, timeout=120.0, headers=None):
    p = urlparse(STRATA_BASE_URL + path)
    host, port = p.hostname, p.port or 80
    s = _open_sock(host, port, timeout)
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.sock = s
        h = {"Content-Type": "application/json", "Content-Length": str(len(body_bytes))}
        if headers:
            h.update(headers)
        conn.request("POST", p.path or "/", body=body_bytes, headers=h)
        r = conn.getresponse()
        body = r.read().decode("utf-8", "replace")
        return r.status, body
    finally:
        try:
            s.close()
        except Exception:
            pass


def strata_health(timeout=2.0):
    """Return True when Strata is up AND has at least one model loaded.

    A running-but-empty model list means the engine is still loading (or
    failed to load), so chat would fail — treat that as unhealthy.
    """
    try:
        status, body = _blocking_get_json(
            "/models", timeout=timeout,
            headers={"Authorization": "Bearer strata"},
        )
        if status >= 400:
            return False
        try:
            data = json.loads(body)
        except Exception:
            return False
        models = data.get("data") or []
        return len(models) > 0
    except Exception:
        return False


def strata_chat(messages, max_tokens=512, temperature=0.7, timeout=180.0):
    """One-shot chat completion via local Strata. Returns the text content."""
    body = json.dumps({
        "model": STRATA_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode("utf-8")
    status, raw = _blocking_post_json(
        "/chat/completions", body, timeout=timeout,
        headers={"Authorization": "Bearer strata"},
    )
    if status >= 400:
        raise RuntimeError(f"Strata HTTP {status}: {raw[:300]}")
    data = json.loads(raw)
    return data["choices"][0]["message"]["content"].strip()
