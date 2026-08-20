# -*- coding: utf-8 -*-
"""pytest fixtures：会话结束清理临时目录；各产品测试模块自行 setup workspace。"""
import time

import pytest

from ci_harness import cleanup_leftover_temp_dirs
from cw_harness import cleanup_leftover_temp_dirs as cleanup_cw_temp_dirs
from eval_config import CW_RESULTS_DIR, RESULTS_DIR


@pytest.fixture(scope="session", autouse=True)
def _cleanup_temp_dirs():
    t0 = time.time()
    yield
    cleanup_leftover_temp_dirs(t0)
    cleanup_cw_temp_dirs(t0)


def pytest_sessionfinish(session, exitstatus):
    """测试结束后自动生成 Markdown 报告。"""
    try:
        from report import generate_report

        if RESULTS_DIR.exists() and any(RESULTS_DIR.iterdir()):
            out = generate_report(RESULTS_DIR)
            print(f"\n[report] ClassIsland 评测报告：{out}")
        if CW_RESULTS_DIR.exists() and any(CW_RESULTS_DIR.iterdir()):
            out = generate_report(CW_RESULTS_DIR)
            print(f"\n[report] Class Widget 评测报告：{out}")
    except Exception as exc:  # noqa: BLE001
        print(f"[report] 报告生成失败：{exc}")
