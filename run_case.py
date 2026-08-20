# -*- coding: utf-8 -*-
"""单个用例执行：启动 CI -> 跑 SecAgent CLI -> 收集过程 -> 停止 CI。"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from ci_harness import is_service_ready, start_ci, stop_ci
from eval_config import (
    CASE_TIMEOUT_SEC,
    CI_PORT,
    CW_PORT,
    CW_RESULTS_DIR,
    CW_SERVICE_URL,
    CW_BRIDGE_TOKEN,
    REPO_ROOT,
    RESULTS_DIR,
    SECAGENT_MODEL_ID,
    SECAGENT_ROOT,
    SECAGENT_WORKSPACE,
)


class CaseResult:
    def __init__(self, case_id: str, results_dir: Path | None = None):
        self.case_id = case_id
        self.dir = (results_dir or RESULTS_DIR) / case_id
        self.dir.mkdir(parents=True, exist_ok=True)
        # 清理上一轮残留结果文件，避免 judge 混用旧 summary 与本次过程文件
        for old_file in self.dir.iterdir():
            if old_file.is_file():
                old_file.unlink(missing_ok=True)
        self.run_id = uuid.uuid4().hex[:12]
        self.timed_out = False
        self.exit_code = None
        self.stdout = ""
        self.error = ""
        self.session_id = None
        self.duration = 0.0
        self.tool_calls = []
        self.model_thought = ""
        # 记录实际使用的被测模型（环境变量可覆盖默认值）
        self.model_id = SECAGENT_MODEL_ID

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "timed_out": self.timed_out,
            "exit_code": self.exit_code,
            "duration": round(self.duration, 2),
            "session_id": self.session_id,
            "has_tool_calls": bool(self.tool_calls),
            "model": self.model_id,
            "error": self.error,
        }


def run_cli(case_text: str, timeout: float, extra_env: dict[str, str] | None = None) -> tuple[str, int | None, bool]:
    """运行 SecAgent CLI：node dist/index.js run <text> --workspace W --model M。"""
    cmd = [
        "node",
        str(SECAGENT_ROOT / "dist" / "index.js"),
        "run",
        case_text,
        "--workspace", str(SECAGENT_WORKSPACE),
        "--model", SECAGENT_MODEL_ID,
    ]
    env = dict(os.environ)
    env["CLASSISLAND_CONNECTOR_URL"] = f"http://127.0.0.1:{CI_PORT}"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        cmd,
        cwd=str(SECAGENT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    start = time.time()
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        out, _ = proc.communicate()
    return out, proc.returncode, timed_out


def _latest_session_dir() -> Path | None:
    """工作区 sessions 下最新修改的会话目录。"""
    sessions = SECAGENT_WORKSPACE / "sessions"
    if not sessions.exists():
        return None
    candidates = [p for p in sessions.iterdir() if p.is_dir() and p.name != "index.json"]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def collect_session(result: CaseResult, before_ts: float):
    """把本次 run 产生的会话（session.json + runtime.jsonl）复制到结果目录。"""
    latest = _latest_session_dir()
    if latest is None:
        return
    # 只收集在本次 run 之后创建的会话
    if latest.stat().st_mtime < before_ts - 1:
        return
    for name in ("session.json", "runtime.jsonl"):
        src = latest / name
        if src.exists():
            shutil.copy2(src, result.dir / name)
    result.session_id = latest.name
    # 解析工具调用与模型思考
    runtime = latest / "runtime.jsonl"
    if runtime.exists():
        for line in runtime.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                evt = json.loads(line)
            except Exception:
                continue
            stage = evt.get("stage", "")
            if stage in ("mcp.tools/call", "tool.call", "agent.tool.call"):
                result.tool_calls.append(evt.get("data") or evt)
            elif stage == "model.thought" or "thought" in stage:
                result.model_thought += str(evt.get("data", "")) + "\n"


def _is_network_flake(out: str, code: int | None) -> bool:
    """模型端点网络波动（fetch failed）或服务端临时故障（500）时重试。"""
    return code != 0 and (
        "fetch failed" in out
        or "无法连接模型端点" in out
        or "模型请求失败（500）" in out
    )


def run_case(case: dict, log_dir: Path | None = None, max_attempts: int = 3, product: str = "classisland") -> CaseResult:
    """执行一个用例并返回结果（被测实例由调用方负责释放）。"""
    results_dir = CW_RESULTS_DIR if product == "classwidget" else RESULTS_DIR
    result = CaseResult(case["id"], results_dir=results_dir)
    log_dir = log_dir or (REPO_ROOT / "work" / result.run_id)
    before_ts = time.time()
    if product == "classwidget":
        from cw_harness import is_service_ready as ready_fn, start_cw as start_fn, stop_cw as stop_fn
        extra_env = {
            "CLASS_WIDGETS_CONNECTOR_URL": CW_SERVICE_URL,
            "CLASSWIDGETS_CONNECTOR_URL": CW_SERVICE_URL,
            "CLASSWIDGETS_BRIDGE_PORT": str(CW_PORT),
            "CLASSWIDGETS_BRIDGE_TOKEN": CW_BRIDGE_TOKEN,
        }
        not_ready_msg = "Class Widget 联动服务未就绪"
    else:
        ready_fn = is_service_ready
        start_fn = start_ci
        stop_fn = stop_ci
        extra_env = None
        not_ready_msg = "ClassIsland 联动服务未就绪"
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        ci_proc = None
        try:
            ci_proc = start_fn(result.run_id, log_dir)
            if not ready_fn(timeout=15):
                result.error = not_ready_msg
                return result
            time.sleep(5)
            started = time.time()
            out, code, timed_out = run_cli(case["text"], timeout=CASE_TIMEOUT_SEC, extra_env=extra_env)
            result.duration = time.time() - started
            result.timed_out = timed_out
            result.exit_code = code
            result.stdout = out
            (result.dir / "cli_stdout.txt").write_text(out or "", encoding="utf-8")
            collect_session(result, before_ts)
            if not result.timed_out and _is_network_flake(out, code) and attempt < max_attempts:
                print(f"  [{case['id']}] 模型端点网络波动，重试 {attempt}/{max_attempts}")
                continue
            return result
        except Exception as exc:  # noqa: BLE001
            result.error = f"{type(exc).__name__}: {exc}"
            (result.dir / "error.txt").write_text(result.error, encoding="utf-8")
            if attempt < max_attempts:
                continue
            return result
        finally:
            if ci_proc is not None:
                stop_fn(ci_proc)
    return result
