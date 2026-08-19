# -*- coding: utf-8 -*-
"""一键运行评测：pytest 执行用例，生成报告；若设置了 JUDGE_API_KEY 则调用裁判。"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from eval_config import CW_RESULTS_DIR, JUDGE_API_KEY, RESULTS_DIR


def _python(root: Path) -> str:
    for candidate in (root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product",
        choices=["classisland", "classwidget"],
        default=os.environ.get("EVAL_PRODUCT", "classisland"),
    )
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    python = _python(root)
    test_file = "test_eval_cw.py" if args.product == "classwidget" else "test_eval.py"
    results_dir = CW_RESULTS_DIR if args.product == "classwidget" else RESULTS_DIR
    cmd = [python, "-m", "pytest", str(root / test_file), "-v", "--tb=short"]
    result = subprocess.run(cmd, cwd=str(root))

    print("\n===== 结果摘要 =====")
    if results_dir.exists():
        for case_dir in sorted(results_dir.iterdir()):
            summary_file = case_dir / "summary.json"
            if not summary_file.exists():
                continue
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            status = "超时" if summary.get("timed_out") else ("CLI失败" if summary.get("exit_code") != 0 else "完成")
            print(f"  {summary['case_id']:<20} {status:<8} 耗时 {summary.get('duration')}s 会话 {summary.get('session_id')}")

    from report import generate_report

    report_path = generate_report(results_dir)
    print(f"\n过程文件位于 {results_dir}")
    print(f"评测报告：{report_path}")

    if not args.skip_judge and JUDGE_API_KEY:
        print("\n===== 裁判评分 =====")
        judge_cmd = [
            python, str(root / "judge.py"),
            "--product", args.product,
            "--results-dir", str(results_dir),
        ]
        judge_result = subprocess.run(judge_cmd, cwd=str(root))
        generate_report(results_dir)
        if judge_result.returncode != 0 and result.returncode == 0:
            return judge_result.returncode
    else:
        print("裁判：python judge.py --product classwidget（需先设置 JUDGE_API_KEY）")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
