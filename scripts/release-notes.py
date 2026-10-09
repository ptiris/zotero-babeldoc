#!/usr/bin/env python3
import json
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
version = json.loads((root / "addon/manifest.json").read_text())["version"]
changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
match = re.search(r"^## \[" + re.escape(version) + r"\].*\n(.*?)(?=^## |\Z)", changelog, flags=re.M | re.S)
if not match:
    raise SystemExit("Missing CHANGELOG entry for " + version)
(root / "dist/release-notes.md").write_text(match.group(1).strip() + "\n\n安装插件请下载 `.xpi`；安装引擎请下载 `-source.zip`。\n\n[安装指南](https://github.com/" + __import__('os').environ['GITHUB_REPOSITORY'] + "/blob/" + 'v'+version + "/docs/installation.md)\n", encoding="utf-8")
