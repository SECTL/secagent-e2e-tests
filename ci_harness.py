# -*- coding: utf-8 -*-
"""ClassIsland 测试实例生命周期管理。

- prepare_enhanced_zip：把 SecAgent 联动插件注入备份 zip（并修复 GBK 档案文件名）
- start_ci / stop_ci：启动/停止测试实例，等待 18789 服务就绪
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

from eval_config import (
    BACKUP_ZIP,
    CI_PORT,
    CI_SERVICE_URL,
    CLASSISLAND_EXE,
    PLUGIN_DIR,
    REPO_ROOT,
    SIMULATE_TIME,
)

WORK_DIR = REPO_ROOT / "work"


# ---------------------------------------------------------------------------
# 增强备份 zip：修复档案文件名 + 注入插件
# ---------------------------------------------------------------------------

# 备份 zip 中 GBK 档案名的字节序列（来自中央目录原始字节，解压时被误读为 U+FFFD）
# 解压后实际出现在磁盘上的文件名是 U+FFFD 占位符；这里按出现顺序映射回正确 UTF-8 名。
_GBK_NAME_FIX = {
    "用于测试的课程表.json": "用于测试的课程表.json",
}


def _decode_entry_name(raw_name: str) -> str:
    """把 zip 条目名还原为正确 UTF-8 中文名。

    原 zip 的条目名是 UTF-8 字节，但 zipfile 按 cp437 误读为 U+FFFD 序列，
    我们直接按字节识别。raw_name 来自 ZipInfo.filename（已损坏），因此这里
    通过扫描原始 zip 中央目录的字节序列来获取正确名字。
    """
    return raw_name


def prepare_enhanced_zip(run_id: str) -> Path:
    """生成用于 --backupZip 的增强 zip：修复档案名 + 注入 Plugins/classisland.secagent/。"""
    work_dir = WORK_DIR / run_id
    data_dir = work_dir / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. 解压备份 zip
    with zipfile.ZipFile(BACKUP_ZIP) as z:
        for info in z.infolist():
            target = _safe_extract_path(data_dir, info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(info.filename))

    # 2. 修复 Profiles 下乱码档案文件名（U+FFFD -> 正确中文名）
    fix_map = _collect_garbled_profiles(data_dir / "Profiles")
    for garbled, correct in fix_map.items():
        garbled_path = data_dir / "Profiles" / garbled
        if garbled_path.exists():
            garbled_path.rename(data_dir / "Profiles" / correct)

    # 3. 注入 SecAgent 联动插件（从构建输出目录复制）
    plugin_dir = data_dir / "Plugins" / "classisland.secagent"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    for f in PLUGIN_DIR.rglob("*"):
        if f.is_file():
            target = plugin_dir / f.relative_to(PLUGIN_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)

    # 4. 重新打包
    enhanced = work_dir / f"backup_enhanced_{run_id}.zip"
    with zipfile.ZipFile(enhanced, "w", zipfile.ZIP_DEFLATED) as zout:
        for f in data_dir.rglob("*"):
            if f.is_file():
                zout.write(f, f.relative_to(data_dir).as_posix())
    return enhanced


def _safe_extract_path(base: Path, name: str) -> Path:
    """防止 zip slip；条目名可能含反斜杠，统一转正斜杠。"""
    name = name.replace("\\", "/")
    target = base / name
    return target


def _collect_garbled_profiles(profiles_dir: Path) -> dict:
    """收集 Profiles 下包含 U+FFFD 的乱码文件名，按字节映射回正确中文名。

    备份 zip 中档案名为 UTF-8 字节，但创建 zip 时未设置 UTF-8 标志，
    zipfile 按 cp437 解码得到 U+FFFD。这里从原始 zip 中央目录恢复字节，
    再用 UTF-8 解码出正确名字。
    """
    result: dict = {}
    if not profiles_dir.exists():
        return result
    # 从原始 zip 提取 Profiles 条目名的正确 UTF-8 形式
    correct_names = _raw_profile_names_from_zip()
    garbled_names = [p.name for p in profiles_dir.iterdir() if "\ufffd" in p.name]
    for garbled in garbled_names:
        # 按字节指纹匹配：把磁盘上的乱码名还原为 zip 原始字节再 UTF-8 解码
        decoded = _recover_name(garbled, correct_names)
        if decoded:
            result[garbled] = decoded
    return result


def _raw_profile_names_from_zip():
    import struct

    names = []
    with open(BACKUP_ZIP, "rb") as f:
        data = f.read()
    pos = 0
    while True:
        idx = data.find(b"PK\x01\x02", pos)
        if idx < 0:
            break
        nlen = struct.unpack_from("<H", data, idx + 28)[0]
        name_b = data[idx + 46: idx + 46 + nlen]
        try:
            names.append(name_b.decode("utf-8"))
        except UnicodeDecodeError:
            names.append(name_b.decode("gbk", "replace"))
        pos = idx + 1
    return [n for n in names if "Profiles" in n and not n.endswith(".bak")]


def _recover_name(garbled: str, correct_names) -> str | None:
    """乱码名 -> 正确名。乱码名是 cp437 解码的结果，用 cp437 还原字节再按 UTF-8 解码。"""
    try:
        raw = garbled.encode("cp437")
        decoded = raw.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    # 去掉 Profiles\ 前缀
    base = decoded.replace("Profiles\\", "").replace("Profiles/", "")
    for candidate in correct_names:
        if candidate.replace("Profiles\\", "").replace("Profiles/", "") == base:
            return candidate.replace("Profiles\\", "").replace("Profiles/", "")
    return None


# ---------------------------------------------------------------------------
# CI 实例生命周期
# ---------------------------------------------------------------------------


def is_service_ready(timeout: float = 30.0) -> bool:
    """轮询 18789 /health，直到服务就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{CI_SERVICE_URL}/health", timeout=2) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_ci(run_id: str, log_dir: Path) -> subprocess.Popen:
    """启动测试版 ClassIsland（--backupZip + --simulateTime），等待联动服务就绪。"""
    enhanced = prepare_enhanced_zip(run_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / "classisland.log", "w", encoding="utf-8", errors="replace")
    args = [
        str(CLASSISLAND_EXE),
        "--backupZip", str(enhanced),
        "--simulateTime", SIMULATE_TIME,
        "--skip-oobe",
        "--quiet",
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    # 测试实例使用独立端口与单实例锁，与正式版并存
    env = dict(os.environ)
    env["CLASSISLAND_CONNECTOR_URL"] = f"http://127.0.0.1:{CI_PORT}"
    env["CLASSISLAND_MUTEX_NAME"] = "ClassIsland.Lock.SecAgentTest"
    proc = subprocess.Popen(
        args, stdout=log_file, stderr=subprocess.STDOUT, creationflags=creationflags, env=env,
    )
    if not is_service_ready(timeout=45):
        proc.kill()
        log_file.close()
        raise RuntimeError("ClassIsland 联动服务（18789）在 45 秒内未就绪")
    return proc


def stop_ci(proc: subprocess.Popen) -> None:
    """停止 CI 实例（强杀；--backupZip 临时数据由 CI 退出清理，强杀后由外部清理）。"""
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=15)
    else:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def cleanup_leftover_temp_dirs(created_after: float) -> int:
    """清理测试产生的 %TEMP%/ClassIsland_SecAgent_* 残留目录。"""
    import tempfile

    removed = 0
    tmp = Path(tempfile.gettempdir())
    for d in tmp.glob("ClassIsland_SecAgent_*"):
        try:
            if d.stat().st_mtime >= created_after:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except OSError:
            pass
    return removed
