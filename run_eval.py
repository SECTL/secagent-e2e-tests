# -*- coding: utf-8 -*-
"""一键运行全部评测：pytest 执行 8 个用例（每例 60s 超时），随后输出摘要。"""
import json
import subprocess
import sys
from pathlib import Path

from eval_config import RESULTS_DIR


def main():
    root = Path(__file__).resolve().parent
    python = root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = sys.executable
    cmd = [str(python), "-m", "pytest", str(root / "test_eval.py"), "-v", "--tb=short"]
    result = subprocess.run(cmd, cwd=str(root))
    print("\n===== 结果摘要 =====")
    for case_dir in sorted(RESULTS_DIR.iterdir()):
        summary_file = case_dir / "summary.json"
        if not summary_file.exists():
            continue
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        status = "超时" if summary.get("timed_out") else ("CLI失败" if summary.get("exit_code") != 0 else "完成")
        print(f"  {summary['case_id']:<20} {status:<8} 耗时 {summary.get('duration')}s 会话 {summary.get('session_id')}")
    from report import generate_report

    report_path = generate_report()
    print(f"\n过程文件位于 {RESULTS_DIR}")
    print(f"评测报告：{report_path}")
    print("裁判：python judge.py（需先设置 JUDGE_API_KEY；裁判后再跑一次会附带裁判结果）")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
