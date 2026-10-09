#!/usr/bin/env python3
"""Run on a trusted GitHub tag after tests; publish assets before update metadata."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from build import validate_repository, VERSION


def gh(repo, *args, check=True):
    return subprocess.run(["gh", "release", *args, "--repo", repo],
                          capture_output=True, text=True, check=check)


def publish(repo, dist, target="main"):
    validate_repository(repo)
    updates = json.loads((dist / "updates.json").read_text())
    addon, = updates["addons"]
    entry, = updates["addons"][addon]["updates"]
    version = entry["version"]
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid stable version")
    tag = "v" + version
    xpi = dist / f"zotero-babeldoc-{version}.xpi"
    expected_link = f"https://github.com/{repo}/releases/download/{tag}/{xpi.name}"
    if entry["update_link"] != expected_link or entry["update_hash"] != "sha256:" + hashlib.sha256(xpi.read_bytes()).hexdigest():
        raise ValueError("Update metadata does not match release artifact")
    # Fetch existing updates first; do not mistake an API/network/auth failure for absence.
    listing = gh(repo, "list", "--limit", "1000", "--json", "tagName,isDraft,isImmutable")
    releases = {r["tagName"]: r for r in json.loads(listing.stdout)}
    if releases.get("release", {}).get("isImmutable"):
        raise ValueError("The fixed update Release is immutable; migrate the update endpoint before publishing.")
    with tempfile.TemporaryDirectory() as temporary:
        old_dir = Path(temporary)
        if "release" in releases:
            gh(repo, "download", "release", "--pattern", "updates.json", "--dir", str(old_dir))
            previous = json.loads((old_dir / "updates.json").read_text())["addons"][addon]["updates"][0]
            old_version = tuple(map(int, previous["version"].split(".")))
            new_version = tuple(map(int, version.split(".")))
            if old_version > new_version:
                raise ValueError("Refusing to roll the stable update channel backward")
            if old_version == new_version and previous != entry:
                raise ValueError("A published version cannot be rebuilt with different metadata")
        assets = [xpi, dist / f"zotero-babeldoc-{version}-source.zip", dist / "SHA256SUMS.txt", dist / "updates.json"]
        if tag not in releases:
            gh(repo, "create", tag, "--verify-tag", "--draft", "--title", f"BabelDOC for Zotero {version}", "--notes-file", str(dist / "release-notes.md"))
            releases[tag] = {"isDraft": True}
        if releases[tag]["isDraft"]:
            gh(repo, "upload", tag, *(str(p) for p in assets), "--clobber")
            gh(repo, "edit", tag, "--draft=false", "--latest=true")
        else:
            existing = old_dir / "assets"
            existing.mkdir()
            gh(repo, "download", tag, "--dir", str(existing))
            for asset in assets:
                if not (existing / asset.name).is_file() or (existing / asset.name).read_bytes() != asset.read_bytes():
                    raise ValueError("Published artifacts differ. Bump the version instead of replacing them.")
        # Fixed URL used by Zotero; explicitly exclude this channel from /releases/latest.
        if "release" not in releases:
            gh(repo, "create", "release", "--target", target, "--prerelease", "--latest=false", "--title", "Zotero stable update channel", "--notes", "Machine-readable update manifest. Install the numbered version release.", str(dist / "updates.json"))
        else:
            gh(repo, "upload", "release", str(dist / "updates.json"), "--clobber")
    print(f"Published {repo} {tag}; stable update manifest refreshed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    publish(args.repository, args.dist, os.environ.get("GITHUB_SHA", "main"))
