#!/usr/bin/env python3
"""Deterministic release artifacts; no engine, user files, or credentials bundled."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+\Z")
EXCLUDED = {"__pycache__", "engine-home", ".DS_Store"}


def validate_repository(value):
    if not REPOSITORY.fullmatch(value or "") or value.split("/")[1] in {".", ".."}:
        raise ValueError("repository must be owner/repo")
    return value


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def archive(path, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data, executable in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if executable else 0o100644) << 16
            z.writestr(info, data)


def build(root=ROOT, output=None, repository=None, tag=None):
    root = Path(root)
    output = Path(output or root / "dist")
    manifest = json.loads((root / "addon/manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if not VERSION.fullmatch(version):
        raise ValueError("Only stable x.y.z versions are supported")
    settings = manifest.get("applications", {}).get("zotero", {})
    for key in ("id", "update_url", "strict_min_version", "strict_max_version"):
        if not settings.get(key):
            raise ValueError("Required Zotero manifest field missing: " + key)
    if tag and tag != "v" + version:
        raise ValueError("Tag must match addon/manifest.json version")
    if json.loads((root / "package.json").read_text())["version"] != version:
        raise ValueError("package.json and addon/manifest.json versions differ")
    if repository:
        repository = validate_repository(repository)
        manifest["homepage_url"] = "https://github.com/" + repository
        settings["update_url"] = f"https://github.com/{repository}/releases/download/release/updates.json"
    elif tag:
        raise ValueError("A release build requires --repository")
    output.mkdir(parents=True, exist_ok=True)
    name = f"zotero-babeldoc-{version}"
    entries = []
    for p in (root / "addon").rglob("*"):
        if p.is_file() and not EXCLUDED.intersection(p.relative_to(root).parts):
            relative = p.relative_to(root / "addon").as_posix()
            entries.append((relative, json_bytes(manifest) if relative == "manifest.json" else p.read_bytes(), False))
    xpi = output / (name + ".xpi")
    archive(xpi, entries)
    artifacts = [xpi]
    # Source and engine installer: explicit tracked-file list excludes all local caches.
    tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             check=True, capture_output=True).stdout.decode().split("\0")
    source = []
    for relative in filter(None, tracked):
        p = root / relative
        if not p.is_file() or p.is_symlink():
            raise ValueError("Invalid tracked source file: " + relative)
        if EXCLUDED.intersection(Path(relative).parts) or relative.startswith(("dist/", "engine/", ".engine-install-cache/")):
            raise ValueError("Cache or artifact must not be tracked: " + relative)
        source.append((name + "/" + relative, p.read_bytes(), relative == "install-macos.command"))
    source_zip = output / (name + "-source.zip")
    archive(source_zip, source)
    artifacts.append(source_zip)
    if repository:
        updates = {"addons": {settings["id"]: {"updates": [{
            "version": version,
            "update_link": f"https://github.com/{repository}/releases/download/v{version}/{xpi.name}",
            "update_hash": "sha256:" + hashlib.sha256(xpi.read_bytes()).hexdigest(),
            "applications": {"zotero": {k: settings[k] for k in ("strict_min_version", "strict_max_version")}}
        }]}}}
        update_path = output / "updates.json"
        update_path.write_bytes(json_bytes(updates))
        artifacts.append(update_path)
    sums = output / "SHA256SUMS.txt"
    sums.write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in artifacts), encoding="utf-8")
    return artifacts + [sums]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--tag", help="Require a matching stable version tag, e.g. v0.1.2")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for path in build(output=args.output, repository=args.repository, tag=args.tag):
        print(path)


if __name__ == "__main__":
    main()
