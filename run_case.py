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
    REPO_ROOT,
    RESULTS_DIR,
    SECAGENT_MODEL_ID,
    SECAGENT_ROOT,
    SECAGENT_WORKSPACE,
)


class CaseResult:
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.dir = RESULTS_DIR / case_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_id = uuid.uuid4().hex[:12]
        self.timed_out = False
        self.exit_code = None
        self.stdout = ""
        self.error = ""
        self.session_id = None
        self.duration = 0.0
        self.tool_calls = []
        self.model_thought = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "timed_out": self.timed_out,
            "exit_code": self.exit_code,
            "duration": round(self.duration, 2),
            "session_id": self.session_id,
            "has_tool_calls": bool(self.tool_calls),
            "error": self.error,
        }


def run_cli(case_text: str, timeout: float) -> tuple[str, int | None, bool]:
    """运行 SecAgent CLI：node dist/index.js run <text> --workspace W --model M。"""
    cmd = [
        "node",
        str(SECAGENT_ROOT / "dist" / "index.js"),
        "run",
        case_text,
        "--workspace", str(SECAGENT_WORKSPACE),
        "--model", SECAGENT_MODEL_ID,
    ]
    # 传递环境变量，让 connector 连接测试实例的服务端口
    env = dict(os.environ)
    env["CLASSISLAND_CONNECTOR_URL"] = f"http://127.0.0.1:{CI_PORT}"
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
    """模型端点网络波动（fetch failed）时重试。"""
    return code != 0 and ("fetch failed" in out or "无法连接模型端点" in out)


def run_case(case: dict, log_dir: Path | None = None, max_attempts: int = 3) -> CaseResult:
    """执行一个用例并返回结果（CI 实例由调用方负责释放）。"""
    result = CaseResult(case["id"])
    log_dir = log_dir or (REPO_ROOT / "work" / result.run_id)
    before_ts = time.time()
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        ci_proc = None
        try:
            # 1. 启动 CI（含插件、模拟时间）
            ci_proc = start_ci(result.run_id, log_dir)
            # 2. 等联动服务就绪
            if not is_service_ready(timeout=15):
                result.error = "ClassIsland 联动服务未就绪"
                return result
            # 等 connector 完成首轮工具注册（5s 轮询）
            time.sleep(5)
            # 3. 跑 SecAgent CLI
            started = time.time()
            out, code, timed_out = run_cli(case["text"], timeout=CASE_TIMEOUT_SEC)
            result.duration = time.time() - started
            result.timed_out = timed_out
            result.exit_code = code
            result.stdout = out
            (result.dir / "cli_stdout.txt").write_text(out or "", encoding="utf-8")
            # 4. 收集会话过程
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
                stop_ci(ci_proc)
    return result
