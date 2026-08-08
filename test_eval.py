# -*- coding: utf-8 -*-
"""SecAgent × ClassIsland 端到端评测用例。

每个用例：独立 ClassIsland 实例（--backupZip + --simulateTime）→ 跑 SecAgent CLI。
pytest 只保证执行链路（60 秒内完成、过程已落盘）；
模型是否调用工具、结果对错由 judge.py 调用 deepseek 裁判判定
（课表上下文提示词可能直接给出答案，未调用工具不视为链路失败）。
"""
import time

from eval_config import CASE_TIMEOUT_SEC
from run_case import run_case


def test_secagent_case(case):
    started = time.time()
    result = run_case(case)
    elapsed = time.time() - started

    # 1. 60 秒内必须完成（CLI 自身超时即失败）
    assert not result.timed_out, f"用例在 {CASE_TIMEOUT_SEC}s 内未完成，已杀掉"
    # 2. CLI 正常退出
    assert result.exit_code == 0, f"SecAgent CLI 退出码 {result.exit_code}\n{result.stdout[-2000:]}"
    # 3. 必须产生会话过程文件
    assert (result.dir / "runtime.jsonl").exists(), "未找到 runtime.jsonl 过程文件"
    # 4. 记录摘要供裁判使用（工具调用数一并记录，供裁判参考；未调用不判失败）
    summary = result.to_dict()
    summary["elapsed"] = round(elapsed, 2)
    summary["text"] = case["text"]
    (result.dir / "summary.json").write_text(
        __import__("json").dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
