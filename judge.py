# -*- coding: utf-8 -*-
"""裁判客户端：把测试收集到的执行过程交给 deepseek 裁判评分。

用法：
  python judge.py [--results-dir results] [--output judge_report.json]

需要环境变量（用户提供）：
  JUDGE_API_KEY  deepseek API key
  JUDGE_BASE_URL 端点，默认 https://api.deepseek.com/v1（使用 /chat/completions）
  JUDGE_MODEL    默认 deepseek-reasoner
"""
import argparse
import json
import sys
from pathlib import Path

import requests

from eval_config import (
    JUDGE_API_KEY,
    JUDGE_BASE_URL,
    JUDGE_MODEL,
    RESULTS_DIR,
)
from eval_cases import CASES, CASES_BY_ID
from judge_prompt import build_prompt


def load_trace(case_id: str, results_dir: Path) -> str:
    """从结果目录拼接可读的执行过程记录。"""
    case_dir = results_dir / case_id
    parts = []
    summary_file = case_dir / "summary.json"
    if summary_file.exists():
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        parts.append(
            f"[摘要] 超时={summary.get('timed_out')} 退出码={summary.get('exit_code')} "
            f"耗时={summary.get('duration')}s 工具调用数={summary.get('has_tool_calls')}"
        )
    runtime = case_dir / "runtime.jsonl"
    if runtime.exists():
        lines = []
        for line in runtime.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                evt = json.loads(line)
            except Exception:
                continue
            stage = evt.get("stage", "")
            data = evt.get("data")
            if stage in ("model.output.delta",):
                continue  # 逐字输出太碎，跳过
            if data is not None:
                lines.append(f"[{stage}] {json.dumps(data, ensure_ascii=False)}")
            else:
                lines.append(f"[{stage}] {json.dumps(evt, ensure_ascii=False)}")
        parts.append("\n".join(lines[:300]))
    stdout_file = case_dir / "cli_stdout.txt"
    if stdout_file.exists():
        out = stdout_file.read_text(encoding="utf-8", errors="replace")
        parts.append("[CLI 最终输出]\n" + out[-4000:])
    return "\n".join(parts)


def judge(results_dir: Path) -> list[dict]:
    if not JUDGE_API_KEY:
        print("未设置 JUDGE_API_KEY，跳过裁判。请先设置环境变量（key 和端点由用户提供）。")
        return []
    executions = [{"trace": load_trace(c["id"], results_dir)} for c in CASES]
    prompt = build_prompt(CASES, executions)
    resp = requests.post(
        f"{JUDGE_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {JUDGE_API_KEY}"},
        json={
            "model": JUDGE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 8192,
        },
        timeout=300,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    # 提取 JSON 数组（模型可能包在 markdown 代码块里）
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    start, end = content.find("["), content.rfind("]")
    if start >= 0 and end > start:
        content = content[start:end + 1]
    verdicts = json.loads(content)
    return verdicts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--output", default=str(RESULTS_DIR / "judge_report.json"))
    args = parser.parse_args()
    results_dir = Path(args.results_dir)
    verdicts = judge(results_dir)
    if not verdicts:
        return 1
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdicts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"裁判报告已写入 {out}")
    for v in verdicts:
        print(f"{v.get('case_id')}: {v.get('pass')} — {v.get('reason', '')[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
