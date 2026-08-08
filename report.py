# -*- coding: utf-8 -*-
"""生成 Markdown 评测报告。

读取 results/ 下各用例的 summary.json / runtime.jsonl / cli_stdout.txt 与
可选的 judge_report.json，汇总为 results/report.md。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from eval_config import (
    CASE_TIMEOUT_SEC,
    RESULTS_DIR,
    SECAGENT_MODEL_ID,
    SIMULATE_TIME,
)


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _tool_calls(runtime_path: Path) -> list[str]:
    names = []
    if not runtime_path.exists():
        return names
    for line in runtime_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if evt.get("stage") != "mcp.tools/call":
            continue
        data = evt.get("data") or {}
        name = data.get("name") or data.get("tool") or "?"
        if name not in names:
            names.append(name)
    return names


def _final_answer(stdout_path: Path) -> str:
    if not stdout_path.exists():
        return ""
    lines = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    finals = [ln[7:].strip() for ln in lines if ln.startswith("[final]")]
    return "\n".join(finals)[:800]


def _error_tail(stdout_path: Path) -> str:
    if not stdout_path.exists():
        return ""
    lines = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    errs = [ln for ln in lines if "Execution failed" in ln or "[error]" in ln]
    return "\n".join(errs)[-600:]


def collect_cases(results_dir: Path) -> list[dict]:
    cases = []
    models = set()
    for d in sorted(results_dir.iterdir()):
        if not d.is_dir():
            continue
        summary_file = d / "summary.json"
        summary = _load_json(summary_file) or {}
        if summary.get("model"):
            models.add(summary["model"])
        case_id = summary.get("case_id", d.name)
        if summary.get("timed_out"):
            status = "超时"
        elif summary.get("exit_code") == 0:
            status = "完成"
        else:
            status = f"CLI失败({summary.get('exit_code')})"
        cases.append({
            "id": case_id,
            "status": status,
            "duration": summary.get("duration"),
            "session": (summary.get("session_id") or "")[:8],
            "tools": _tool_calls(d / "runtime.jsonl"),
            "final": _final_answer(d / "cli_stdout.txt"),
            "error": _error_tail(d / "cli_stdout.txt"),
            "text": summary.get("text", ""),
        })
    return cases, models


def collect_judgements(results_dir: Path) -> list[dict]:
    report = _load_json(results_dir / "judge_report.json")
    if not isinstance(report, list):
        return []
    return report


def generate_report(results_dir: Path = RESULTS_DIR) -> Path:
    cases, models = collect_cases(results_dir)
    judgements = collect_judgements(results_dir)
    judge_by_id = {j.get("case_id"): j for j in judgements}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    done = sum(1 for c in cases if c["status"] == "完成")
    lines = []
    lines.append(f"# SecAgent E2E 评测报告\n")
    lines.append(f"- **生成时间**：{now}")
    model_label = ", ".join(sorted(models)) if models else SECAGENT_MODEL_ID
    lines.append(f"- **被测模型**：`{model_label}`")
    lines.append(f"- **模拟时间**：`{SIMULATE_TIME}`（第 3 节上课中）")
    lines.append(f"- **用例超时**：{CASE_TIMEOUT_SEC}s")
    lines.append(f"- **链路结果**：{done}/{len(cases)} 完成")
    if judgements:
        passed = sum(1 for j in judgements if j.get("pass") == "pass")
        lines.append(f"- **裁判结果**：{passed}/{len(judgements)} pass")
    lines.append("")

    # 汇总表
    lines.append("## 结果汇总\n")
    lines.append("| 用例 | 链路 | 裁判 | 耗时(s) | 工具调用 | 会话 |")
    lines.append("|---|---|---|---|---|---|")
    for c in cases:
        j = judge_by_id.get(c["id"])
        verdict = j.get("pass", "-") if j else "-"
        lines.append(
            f"| {c['id']} | {c['status']} | {verdict} | {c['duration'] or '-'} "
            f"| {', '.join(t.split('__')[-1] for t in c['tools']) or '-'} | {c['session']} |"
        )
    lines.append("")

    # 裁判详情
    if judgements:
        lines.append("## 裁判详情\n")
        for j in judgements:
            lines.append(f"### {j.get('case_id')}: **{j.get('pass')}**")
            lines.append(f"- 结果正确：{j.get('result_correct')} | 过程正确：{j.get('process_correct')}")
            lines.append(f"- 理由：{j.get('reason', '')}")
            lines.append("")

    # 各用例详情
    lines.append("## 用例详情\n")
    for c in cases:
        lines.append(f"### {c['id']}（{c['status']}，{c['duration'] or '-'}s）")
        if c["text"]:
            lines.append(f"\n**任务**：{c['text']}")
        if c["tools"]:
            lines.append(f"\n**工具调用**：{', '.join(t.split('__')[-1] for t in c['tools'])}")
        if c["final"]:
            lines.append(f"\n**最终回答**：\n\n```\n{c['final']}\n```")
        if c["error"]:
            lines.append(f"\n**错误**：\n\n```\n{c['error']}\n```")
        lines.append("")

    out = results_dir / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    out = generate_report()
    print(f"报告已生成：{out}")
