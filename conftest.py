# -*- coding: utf-8 -*-
"""pytest fixtures：为每个用例提供独立的 ClassIsland 测试实例。"""
import subprocess
import sys as _sys
import time

import pytest

from ci_harness import cleanup_leftover_temp_dirs
from eval_config import REPO_ROOT
from eval_cases import CASES
from run_case import run_case


@pytest.fixture(scope="session", autouse=True)
def _setup_and_cleanup():
    """会话开始前构建独立测试 workspace，结束后清理临时目录。"""
    t0 = time.time()
    subprocess.run([_sys.executable, str(REPO_ROOT / "setup.py")], check=True)
    yield
    cleanup_leftover_temp_dirs(t0)


@pytest.fixture(params=CASES, ids=[c["id"] for c in CASES])
def case(request):
    return request.param


def pytest_sessionfinish(session, exitstatus):
    """测试结束后自动生成 Markdown 报告。"""
    try:
        from report import generate_report

        out = generate_report()
        print(f"\n[report] 评测报告已生成：{out}")
    except Exception as exc:  # noqa: BLE001
        print(f"[report] 报告生成失败：{exc}")
