#!/usr/bin/env python3
"""Update metadata only; never commit, tag, push, or publish automatically."""
import argparse
import json
from pathlib import Path
from build import VERSION

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("version")
args = parser.parse_args()
if not VERSION.fullmatch(args.version):
    parser.error("expected stable x.y.z")
for name in ("addon/manifest.json", "package.json"):
    path = root / name
    content = json.loads(path.read_text(encoding="utf-8"))
    content["version"] = args.version
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Version updated. Add CHANGELOG entry, run tests, commit, then push the version tag.")
