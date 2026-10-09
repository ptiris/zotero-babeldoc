#!/bin/sh
cd "$(dirname "$0")" || exit 1
installer_python=""
for candidate in python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then installer_python="$candidate"; break; fi
done
if [ -z "$installer_python" ]; then
  printf '%s\n' '未找到 Python。请安装 Python 3 或 uv 后重试。'
  exit 1
fi
"$installer_python" scripts/install-engine.py
install_status=$?
printf '\n按回车关闭此窗口。'
read -r install_response
exit "$install_status"
