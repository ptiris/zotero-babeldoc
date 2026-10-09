#!/usr/bin/env python3
"""Check Python syntax, version consistency, addon shape and local Markdown links."""
import ast
import json
from pathlib import Path
import re
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
for folder in ("addon", "scripts", "tests"):
    for path in (root / folder).rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
manifest = json.loads((root / "addon/manifest.json").read_text(encoding="utf-8"))
assert manifest["version"] == json.loads((root / "package.json").read_text())["version"]
settings = manifest["applications"]["zotero"]
for key in ("id", "update_url", "strict_min_version", "strict_max_version"):
    assert settings.get(key), key
assert settings["update_url"].startswith("https://") and ".invalid" not in settings["update_url"]
for name in ("bootstrap.js", "bridge/runner.py", "content/core.js", "content/console.xhtml", "content/preferences.xhtml"):
    assert (root / "addon" / name).is_file(), name
for path in [root / "README.md", root / "README.en.md", *(root / "docs").rglob("*.md"), *root.glob("*.md")]:
    for target in re.findall(r"\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
        if re.match(r"[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
            continue
        dest = (path.parent / unquote(target.split("#")[0])).resolve()
        assert dest.is_relative_to(root), f"link outside repo: {path}: {target}"
        assert dest.exists(), f"missing local link: {path}: {target}"
print("Python syntax, manifests, addon files and local documentation links OK")
