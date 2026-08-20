# -*- coding: utf-8 -*-
"""Class Widget 测试实例生命周期管理。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from eval_config import (
    CLASSWIDGET_APP,
    CLASSWIDGET_ROOT,
    CW_BRIDGE_TOKEN,
    CW_PLUGIN_DIR,
    CW_PORT,
    CW_PYTHON,
    CW_SERVICE_URL,
    CW_TESTDATA,
    REPO_ROOT,
    SIMULATE_TIME,
)

WORK_DIR = REPO_ROOT / "work"


def prepare_data_dir(run_id: str) -> Path:
    """Copy testdata into an isolated data root and inject the SecAgent plugin."""
    dest = WORK_DIR / run_id / "data"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    if not CW_TESTDATA.is_dir():
        raise FileNotFoundError(f"找不到 Class Widget testdata：{CW_TESTDATA}")
    shutil.copytree(
        CW_TESTDATA,
        dest,
        ignore=shutil.ignore_patterns("logs", "plugins", "__pycache__"),
    )
    plugin_dest = dest / "plugins" / "com.sectl.secagent-bridge"
    if plugin_dest.exists():
        shutil.rmtree(plugin_dest, ignore_errors=True)
    if not CW_PLUGIN_DIR.is_dir():
        raise FileNotFoundError(f"找不到 Class Widget SecAgent 插件：{CW_PLUGIN_DIR}")
    shutil.copytree(
        CW_PLUGIN_DIR,
        plugin_dest,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
    )
    return dest


def is_service_ready(timeout: float = 30.0, url: str | None = None) -> bool:
    """Poll /health until the Class Widget bridge is up."""
    target = url or CW_SERVICE_URL
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{target}/health", timeout=2) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_cw(run_id: str, log_dir: Path) -> subprocess.Popen:
    """Start ClassWidget-ForTest with isolated data + simulated time."""
    data_dir = prepare_data_dir(run_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / "classwidget.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["CLASSWIDGETS_LOCK_NAME"] = "ClassWidgets2.SecAgentTest.lock"
    env["CLASSWIDGETS_BRIDGE_PORT"] = str(CW_PORT)
    env["CLASSWIDGETS_BRIDGE_TOKEN"] = CW_BRIDGE_TOKEN
    env["CLASSWIDGETS_BRIDGE_FILE"] = str(data_dir / "secagent-bridge.json")
    env["CLASS_WIDGETS_CONNECTOR_URL"] = CW_SERVICE_URL
    env["CLASSWIDGETS_CONNECTOR_URL"] = CW_SERVICE_URL
    env["CLASSWIDGETS_SKIP_OOBE"] = "1"
    env["CLASSWIDGETS_QUIET"] = "1"
    env["PYTHONPATH"] = str(CLASSWIDGET_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    if not env.get("DISPLAY") and sys.platform != "win32":
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

    python = str(CW_PYTHON)
    args = [
        python,
        str(CLASSWIDGET_APP),
        "--dataPath", str(data_dir),
        "--simulateTime", SIMULATE_TIME,
        "--skip-oobe",
        "--quiet",
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    proc = subprocess.Popen(
        args,
        cwd=str(CLASSWIDGET_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        env=env,
    )
    if not is_service_ready(timeout=45):
        proc.kill()
        log_file.close()
        raise RuntimeError(f"Class Widget 联动服务（{CW_SERVICE_URL}）在 45 秒内未就绪")
    return proc


def stop_cw(proc: subprocess.Popen) -> None:
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            timeout=15,
        )
    else:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def cleanup_leftover_temp_dirs(created_after: float) -> int:
    import tempfile

    removed = 0
    tmp = Path(tempfile.gettempdir())
    for d in tmp.glob("ClassWidget_SecAgent_*"):
        try:
            if d.stat().st_mtime >= created_after:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except OSError:
            pass
    return removed
