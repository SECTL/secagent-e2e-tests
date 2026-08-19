# -*- coding: utf-8 -*-
"""SecAgent × ClassIsland / Class Widget 自动化评测：配置。

所有路径都可通过环境变量覆盖，方便 CI 与本地切换。
"""
import os
import sys
from pathlib import Path

# 仓库根目录
REPO_ROOT = Path(__file__).resolve().parent
_HOME = Path.home()


def _path_from_env(name: str, *candidates: Path) -> Path:
    env = os.environ.get(name)
    if env:
        return Path(env)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


# SecAgent CLI 仓库（含 dist/index.js）
SECAGENT_ROOT = _path_from_env(
    "SECAGENT_ROOT",
    _HOME / "CodeSpace" / "SecAgent",
    Path(r"D:\Code\SecAgentAll\SecAgent"),
)

# ClassIsland 侧 SecAgent 联动插件目录（dotnet build -o bin/TestBuild 的新版，含环境变量端口支持）
PLUGIN_DIR = Path(os.environ.get(
    "PLUGIN_DIR",
    r"D:\Code\SecAgentAll\ClassIsland-SecAgent-Plugin\bin\TestBuild",
))

# 测试实例的联动服务端口（避免与正式版 18789 冲突）
CI_PORT = int(os.environ.get("CI_PORT", "18799"))

# 测试数据备份 zip（档案：课程表.json，含周一~周五课表）
BACKUP_ZIP = Path(os.environ.get("BACKUP_ZIP", r"D:\Dowenlod下载\Backup_ForTest1.zip"))

# 测试专用 ClassIsland 可执行文件（必须支持 --backupZip/--dataPath/--simulateTime）
CLASSISLAND_EXE = Path(os.environ.get(
    "CLASSISLAND_EXE",
    r"D:\Code\SecAgentAll\ClassIsland-ForTest\ClassIsland.Desktop\bin\Debug\net8.0-windows10.0.19041.0\ClassIsland.Desktop.exe",
))

# SecAgent 工作区（本机客户端登录态：.env 中的密钥 + secagent.yaml 中的模型配置）
SECAGENT_WORKSPACE = Path(os.environ.get(
    "SECAGENT_WORKSPACE", str(REPO_ROOT / "work" / "test_workspace"),
))

# 被测模型：默认走工作区 secagent.yaml 里的 gpt-5.6-terra（OpenAI Responses）
SECAGENT_MODEL_ID = os.environ.get("SECAGENT_MODEL_ID", "terra:gpt-5.6-terra")

# 模拟启动时间：2026-08-05（周三）10:30，第 3 节（10:10-10:55）上课中
SIMULATE_TIME = os.environ.get("SIMULATE_TIME", "2026-08-05T10:30:00")

# 每个用例的最长执行时间（秒），超时即判失败并杀掉
# 真实 Responses 模型（含 reasoning）通常需要超过 60s
CASE_TIMEOUT_SEC = int(os.environ.get("CASE_TIMEOUT_SEC", "180"))

# ClassIsland 联动插件 HTTP 服务地址（与 CI_PORT 一致）
CI_SERVICE_URL = os.environ.get("CI_SERVICE_URL", f"http://127.0.0.1:{CI_PORT}")

# 结果输出目录
RESULTS_DIR = REPO_ROOT / "results"

# ---------------------------------------------------------------------------
# Class Widget（ClassWidget-ForTest）评测
# ---------------------------------------------------------------------------
CLASSWIDGET_ROOT = Path(os.environ.get(
    "CLASSWIDGET_ROOT",
    str(_HOME / "CodeSpace" / "ClassWidget-ForTest"),
))
CLASSWIDGET_APP = Path(os.environ.get(
    "CLASSWIDGET_APP",
    str(CLASSWIDGET_ROOT / "src" / "app.py"),
))
CW_PLUGIN_DIR = Path(os.environ.get(
    "CW_PLUGIN_DIR",
    str(CLASSWIDGET_ROOT / "plugins-src" / "com.sectl.secagent-bridge"),
))
CW_CONNECTOR_SRC = Path(os.environ.get(
    "CW_CONNECTOR_SRC",
    str(CLASSWIDGET_ROOT / "secagent-connector"),
))
CW_TESTDATA = Path(os.environ.get(
    "CW_TESTDATA",
    str(CLASSWIDGET_ROOT / "testdata"),
))
# 测试实例 HTTP 端口（避开正式版 18765 与 ClassIsland 测试 18799）
CW_PORT = int(os.environ.get("CW_PORT", "18766"))
CW_SERVICE_URL = os.environ.get("CW_SERVICE_URL", f"http://127.0.0.1:{CW_PORT}")
CW_BRIDGE_TOKEN = os.environ.get("CW_BRIDGE_TOKEN", "secagent-e2e-cw-token")
CW_RESULTS_DIR = Path(os.environ.get("CW_RESULTS_DIR", str(REPO_ROOT / "results" / "classwidget")))
CW_PYTHON = _path_from_env(
    "CW_PYTHON",
    CLASSWIDGET_ROOT / ".venv" / "bin" / "python",
    CLASSWIDGET_ROOT / ".venv" / "Scripts" / "python.exe",
    Path(sys.executable),
)

# 裁判：默认与被测模型同一 Responses 端点（密钥请用环境变量 JUDGE_API_KEY）
JUDGE_API_KEY = os.environ.get("JUDGE_API_KEY", "")
JUDGE_BASE_URL = os.environ.get("JUDGE_BASE_URL", "http://156.238.224.90:8080/v1")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-5.6-terra")

# 裁判请求端点（OpenAI Responses 协议）与推理强度
JUDGE_URL = os.environ.get(
    "JUDGE_URL",
    "http://156.238.224.90:8080/v1/responses",
)
JUDGE_REASONING = os.environ.get("JUDGE_REASONING", "high")
