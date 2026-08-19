# -*- coding: utf-8 -*-
"""测试前置：构建独立测试 workspace（登录态 + 新版 connector + 更新 skill）。

原因：正在运行的 SecAgent 桌面端共享 ~/SecAgentWorkspace，会把插件还原为
它缓存的旧版。测试使用独立副本，互不干扰。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(__file__).resolve().parent
SRC_WS = pathlib.Path.home() / "SecAgentWorkspace"
TEST_WS = REPO / "work" / "test_workspace"
CONNECTOR_SRC = pathlib.Path(
    os.environ.get(
        "CONNECTOR_SRC",
        r"D:\Code\SecAgentAll\ClassIsland-SecAgent-Connector",
    )
)
CW_CONNECTOR_SRC = pathlib.Path(
    os.environ.get(
        "CW_CONNECTOR_SRC",
        str(pathlib.Path.home() / "CodeSpace" / "ClassWidget-ForTest" / "secagent-connector"),
    )
)


def inject_virtual_fast_model(text: str) -> str:
    """在 sectl-official provider 的 models 数组中加入 virtual-fast 模型。"""
    if "sectl-official:virtual-fast" in text and "sectl-official:virtual-standard" in text:
        return text
    marker = "    - id: sectl-official\n"
    idx = text.find(marker)
    if idx < 0:
        print("[setup] 未找到 sectl-official provider 块，跳过 virtual-fast 注入")
        return text
    models_marker = "      models:\n"
    models_idx = text.find(models_marker, idx)
    if models_idx < 0:
        print("[setup] 未找到 sectl provider 的 models 数组，跳过 virtual-fast 注入")
        return text
    insert_at = models_idx + len(models_marker)
    vf_block = (
        "        - id: virtual-fast\n"
        "          name: Virtual Fast\n"
        "        - id: virtual-standard\n"
        "          name: Virtual Standard\n"
    )
    return text[:insert_at] + vf_block + text[insert_at:]


def _copy_connector(src: pathlib.Path, dest: pathlib.Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    src_main = src / "main.mjs"
    if src_main.exists():
        shutil.copy2(src_main, dest / "main.mjs")
    src_manifest = src / "secagent-plugin.json"
    if src_manifest.exists():
        shutil.copy2(src_manifest, dest / "secagent-plugin.json")
    src_skills = src / "skills"
    if src_skills.exists():
        shutil.rmtree(dest / "skills", ignore_errors=True)
        shutil.copytree(src_skills, dest / "skills")
    for extra in ("README.md", "LICENSE", "icon.png"):
        if (src / extra).exists():
            shutil.copy2(src / extra, dest / extra)


def _latest_installed(plugin_id: str) -> pathlib.Path | None:
    root = TEST_WS / "plugins" / "installed" / plugin_id
    if not root.exists():
        return None
    versions = [p for p in root.iterdir() if p.is_dir()]
    if not versions:
        return None
    return max(versions, key=lambda p: p.name)


def _ensure_plugin_listed(plugin_id: str, version: str) -> None:
    plugins_json = TEST_WS / "plugins" / "plugins.json"
    payload = {"plugins": []}
    if plugins_json.exists():
        try:
            payload = json.loads(plugins_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"plugins": []}
    plugins = payload.setdefault("plugins", [])
    for item in plugins:
        if item.get("id") == plugin_id:
            item["enabled"] = True
            item["version"] = version
            break
    else:
        plugins.append({"id": plugin_id, "version": version, "enabled": True})
    plugins_json.parent.mkdir(parents=True, exist_ok=True)
    plugins_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inject_classisland_connector() -> None:
    conn_installed = _latest_installed("classisland-connector")
    if conn_installed is None:
        print("[setup] 未找到已安装的 classisland-connector，跳过 ClassIsland connector 注入")
        return
    if not CONNECTOR_SRC.exists():
        print(f"[setup] CONNECTOR_SRC 不存在：{CONNECTOR_SRC}，跳过 ClassIsland connector 注入")
        return
    _copy_connector(CONNECTOR_SRC, conn_installed)
    main_file = conn_installed / "main.mjs"
    if not main_file.exists():
        print("[setup] 错误：ClassIsland connector 缺少 main.mjs")
        sys.exit(1)
    content = main_file.read_text(encoding="utf-8-sig")
    if "process.env.CLASSISLAND_CONNECTOR_URL" not in content:
        print("[setup] 错误：ClassIsland connector 不支持环境变量端口！")
        sys.exit(1)
    print(f"[setup] ClassIsland connector: {conn_installed}")


def inject_classwidget_connector() -> None:
    if not CW_CONNECTOR_SRC.exists():
        print(f"[setup] 错误：找不到 Class Widget connector：{CW_CONNECTOR_SRC}")
        sys.exit(1)
    conn_installed = _latest_installed("class-widgets")
    if conn_installed is None:
        conn_installed = TEST_WS / "plugins" / "installed" / "class-widgets" / "1.0.0"
    _copy_connector(CW_CONNECTOR_SRC, conn_installed)
    _ensure_plugin_listed("class-widgets", conn_installed.name)
    main_file = conn_installed / "main.mjs"
    content = main_file.read_text(encoding="utf-8-sig")
    if "process.env.CLASS_WIDGETS_CONNECTOR_URL" not in content:
        print("[setup] 错误：Class Widget connector 不支持 CLASS_WIDGETS_CONNECTOR_URL！")
        sys.exit(1)
    print(f"[setup] Class Widget connector: {conn_installed}")


def setup_workspace(product: str) -> None:
    if TEST_WS.exists():
        shutil.rmtree(TEST_WS, ignore_errors=True)
    TEST_WS.mkdir(parents=True, exist_ok=True)

    for name in ("secagent.yaml", ".env"):
        src = SRC_WS / name
        if src.exists():
            shutil.copy2(src, TEST_WS / name)

    if (SRC_WS / "skills").exists():
        shutil.copytree(SRC_WS / "skills", TEST_WS / "skills")

    src_plugins = SRC_WS / "plugins"
    if src_plugins.exists():
        shutil.copytree(src_plugins, TEST_WS / "plugins")

    (TEST_WS / "sessions").mkdir(exist_ok=True)

    yaml_path = TEST_WS / "secagent.yaml"
    if yaml_path.exists():
        text = yaml_path.read_text(encoding="utf-8")
        text = text.replace(str(SRC_WS).replace("\\", "\\\\"), str(TEST_WS).replace("\\", "\\\\"))
        text = text.replace(str(SRC_WS), str(TEST_WS))
        text = inject_virtual_fast_model(text)
        yaml_path.write_text(text, encoding="utf-8")

    if product in ("classisland", "all"):
        inject_classisland_connector()
    if product in ("classwidget", "all"):
        inject_classwidget_connector()

    print(f"[setup] 测试 workspace 就绪：{TEST_WS}（product={product}）")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product",
        choices=["classisland", "classwidget", "all"],
        default=os.environ.get("EVAL_PRODUCT", "classisland"),
    )
    args = parser.parse_args()
    setup_workspace(args.product)
    return 0


if __name__ == "__main__":
    sys.exit(main())
