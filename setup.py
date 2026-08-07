# -*- coding: utf-8 -*-
"""测试前置：构建独立测试 workspace（登录态 + 新版 connector + 更新 skill）。

原因：正在运行的 SecAgent 桌面端共享 ~/SecAgentWorkspace，会把插件还原为
它缓存的旧版。测试使用独立副本，互不干扰。
"""
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(__file__).resolve().parent
SRC_WS = pathlib.Path.home() / "SecAgentWorkspace"
TEST_WS = REPO / "work" / "test_workspace"
CONNECTOR_SRC = pathlib.Path(
    __import__("os").environ.get(
        "CONNECTOR_SRC",
        r"D:\Code\SecAgentAll\ClassIsland-SecAgent-Connector",  # 本场开发默认，可用环境变量覆盖
    )
)

# 1. 重建测试 workspace
if TEST_WS.exists():
    shutil.rmtree(TEST_WS, ignore_errors=True)
TEST_WS.mkdir(parents=True, exist_ok=True)

# 2. 复制登录态与配置
for name in ("secagent.yaml", ".env"):
    src = SRC_WS / name
    if src.exists():
        shutil.copy2(src, TEST_WS / name)

# 3. 工作区 skills
if (SRC_WS / "skills").exists():
    shutil.copytree(SRC_WS / "skills", TEST_WS / "skills")

# 4. 插件：复制 installed（含 connector），并把 main.mjs 换为新版、skills 换为更新版
src_plugins = SRC_WS / "plugins"
if src_plugins.exists():
    shutil.copytree(src_plugins, TEST_WS / "plugins")
conn_installed = TEST_WS / "plugins/installed/classisland-connector/1.0.1"
if conn_installed.exists():
    src_main = CONNECTOR_SRC / "main.mjs"
    if src_main.exists():
        shutil.copy2(src_main, conn_installed / "main.mjs")
    src_skills = CONNECTOR_SRC / "skills"
    if src_skills.exists():
        shutil.rmtree(conn_installed / "skills", ignore_errors=True)
        shutil.copytree(src_skills, conn_installed / "skills")

# 5. 空 sessions（每次 run 的会话从这里读取）
(TEST_WS / "sessions").mkdir(exist_ok=True)

# 6. secagent.yaml 的 workspace 字段指向测试目录
yaml_path = TEST_WS / "secagent.yaml"
if yaml_path.exists():
    text = yaml_path.read_text(encoding="utf-8")
    text = text.replace(str(SRC_WS).replace("\\", "\\\\"), str(TEST_WS).replace("\\", "\\\\"))
    text = text.replace(str(SRC_WS), str(TEST_WS))
    yaml_path.write_text(text, encoding="utf-8")

# 7. 校验
main_file = conn_installed / "main.mjs"
content = main_file.read_text(encoding="utf-8-sig")
if "process.env.CLASSISLAND_CONNECTOR_URL" not in content:
    print("[setup] 错误：connector 不支持环境变量端口！")
    sys.exit(1)
print(f"[setup] 测试 workspace 就绪：{TEST_WS}")
print(f"[setup] connector main.mjs: {content.splitlines()[0][:80]}")
