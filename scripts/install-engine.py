#!/usr/bin/env python3
"""Install a pinned local BabelDOC engine without touching the system Python."""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="安装 Zotero BabelDOC 本地翻译引擎")
    parser.add_argument("--directory", type=pathlib.Path, default=ROOT / "engine")
    args = parser.parse_args()
    target = args.directory.resolve()
    uv = shutil.which("uv")
    if not uv:
        candidate = pathlib.Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv")
        if candidate.is_file():
            uv = str(candidate)
    env = os.environ.copy()
    cache = ROOT / ".engine-install-cache"
    env["UV_CACHE_DIR"] = str(cache / "uv")
    env["UV_PYTHON_INSTALL_DIR"] = str(cache / "python")
    env["PIP_CACHE_DIR"] = str(cache / "pip")
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        if uv:
            subprocess.run([uv, "venv", "--python", "3.12", str(target)], env=env, check=True)
        elif (3, 10) <= sys.version_info[:2] < (3, 14):
            subprocess.run([sys.executable, "-m", "venv", str(target)], env=env, check=True)
        else:
            raise RuntimeError("请先安装 uv（https://docs.astral.sh/uv/getting-started/installation/），\n或使用 Python 3.10–3.13 运行此脚本；推荐 Python 3.12。")
    if uv:
        command = [uv, "pip", "install", "--python", str(python), "-r", str(ROOT / "requirements.txt")]
    else:
        command = [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    subprocess.run(command, env=env, check=True)
    result = subprocess.run([str(python), str(ROOT / "addon" / "bridge" / "runner.py")],
                            input=json.dumps({"action": "probe"}) + "\n", text=True, capture_output=True, env=env)
    events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    if result.returncode or not events or events[-1].get("type") != "probe":
        raise RuntimeError(events[-1].get("message", "环境检查失败") if events else "Python 环境检查失败。")
    print("\n安装完成。请将以下完整路径填入 Zotero → BabelDOC 翻译窗口 → Python 路径：\n")
    print(str(python))
    print("\n首次翻译仍需下载 BabelDOC 版面模型和字体。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
        print("\n安装失败：" + str(error), file=sys.stderr)
        raise SystemExit(1)
