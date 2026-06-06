"""Start the MCP bridge subprocess when Studio backend runs workflows (Studio-only UX)."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
from runtime_env import ensure_env_loaded

logger = logging.getLogger(__name__)

_BACKEND = Path(__file__).resolve().parent.parent
_BRIDGE_PROC: Optional[subprocess.Popen] = None


def bridge_url() -> str:
    return os.getenv("MCP_SERVER_URL", os.getenv("MCP_BRIDGE_URL", "http://127.0.0.1:8765")).rstrip("/")


def _healthy(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=1.0).json().get("status") == "ok"
    except httpx.HTTPError:
        return False


def ensure_mcp_bridge() -> Optional[subprocess.Popen]:
    """
    If MCP_BRIDGE_AUTOSTART is not ``0``, ensure ``mcp_bridge.server`` is listening.
    Returns the subprocess handle when this call started it, else None.
    """
    global _BRIDGE_PROC
    ensure_env_loaded()
    if os.getenv("MCP_BRIDGE_AUTOSTART", "1").strip() == "0":
        return None
    url = bridge_url()
    if _healthy(url):
        return None
    if _BRIDGE_PROC and _BRIDGE_PROC.poll() is None:
        for _ in range(20):
            if _healthy(url):
                return None
            time.sleep(0.2)

    env = {
        **os.environ,
        "MCP_BRIDGE_MODE": os.getenv("MCP_BRIDGE_MODE", "demo"),
        "MCP_BRIDGE_PORT": url.rsplit(":", 1)[-1] if ":" in url else "8765",
    }
    logger.info("Starting MCP bridge at %s (mode=%s)", url, env["MCP_BRIDGE_MODE"])
    _BRIDGE_PROC = subprocess.Popen(
        [sys.executable, "-m", "mcp_bridge.server"],
        cwd=str(_BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if _healthy(url):
            return _BRIDGE_PROC
        time.sleep(0.25)
    _BRIDGE_PROC.kill()
    _BRIDGE_PROC = None
    logger.warning("MCP bridge did not become healthy at %s", url)
    return None


def stop_mcp_bridge() -> None:
    global _BRIDGE_PROC
    if _BRIDGE_PROC and _BRIDGE_PROC.poll() is None:
        _BRIDGE_PROC.terminate()
        try:
            _BRIDGE_PROC.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _BRIDGE_PROC.kill()
    _BRIDGE_PROC = None
