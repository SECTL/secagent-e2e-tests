# -*- coding: utf-8 -*-
"""SecAgent × Class Widget 端到端评测用例。

每个用例：独立 ClassWidget-ForTest 实例（--dataPath + --simulateTime）→ 跑 SecAgent CLI。
pytest 只保证执行链路；对错由 judge.py --product classwidget 判定。
"""
import json
import subprocess
import sys
import time

import pytest

from eval_cases_cw import CASES
from eval_config import CASE_TIMEOUT_SEC, CW_RESULTS_DIR, REPO_ROOT
from run_case import run_case


@pytest.fixture(scope="module", autouse=True)
def _setup_workspace():
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "setup.py"), "--product", "classwidget"],
        check=True,
    )


@pytest.fixture(params=CASES, ids=[c["id"] for c in CASES])
def case(request):
    return request.param


def test_secagent_classwidget_case(case):
    started = time.time()
    result = run_case(case, product="classwidget")
    elapsed = time.time() - started

    assert not result.timed_out, f"用例在 {CASE_TIMEOUT_SEC}s 内未完成，已杀掉"
    assert result.exit_code == 0, f"SecAgent CLI 退出码 {result.exit_code}\n{(result.stdout or '')[-2000:]}"
    assert (result.dir / "runtime.jsonl").exists(), "未找到 runtime.jsonl 过程文件"
    summary = result.to_dict()
    summary["elapsed"] = round(elapsed, 2)
    summary["text"] = case["text"]
    summary["product"] = "classwidget"
    (result.dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    CW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
