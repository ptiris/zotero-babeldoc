"""Verify release integrity, upgrade identity, reproducibility and source boundaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / "addon", self.root / "addon", ignore=shutil.ignore_patterns("engine-home", "__pycache__"))
        shutil.copy2(ROOT / "package.json", self.root / "package.json")
        (self.root / "README.md").write_text("fixture")
        (self.root / "install-macos.command").write_text("#!/bin/sh\n")
        for args in (["init", "--quiet"], ["add", "."]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        # Untracked local files must never enter source distribution.
        for folder in ("engine", "addon/bridge/engine-home", "addon/bridge/__pycache__"):
            p = self.root / folder
            p.mkdir(parents=True, exist_ok=True)
            (p / "private.txt").write_text("must-not-ship")
        self.version = json.loads((self.root / "addon/manifest.json").read_text())["version"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_integrity_urls_upgrade_identity_and_clean_source(self):
        output = self.root / "dist"
        assets = build.build(self.root, output, "example/zotero-babeldoc", "v" + self.version)
        with zipfile.ZipFile(assets[0]) as z:
            manifest = json.loads(z.read("manifest.json"))
            settings = manifest["applications"]["zotero"]
            self.assertEqual(settings["id"], "babeldoc@local.zotero")
            self.assertEqual(settings["update_url"], "https://github.com/example/zotero-babeldoc/releases/download/release/updates.json")
            self.assertFalse(any("private" in n or "engine-home" in n for n in z.namelist()))
            self.assertIn("bootstrap.js", z.namelist())
        updates = json.loads(assets[2].read_text())["addons"][settings["id"]]["updates"][0]
        self.assertEqual(updates["update_hash"], "sha256:" + hashlib.sha256(assets[0].read_bytes()).hexdigest())
        self.assertEqual(updates["update_link"], f"https://github.com/example/zotero-babeldoc/releases/download/v{self.version}/{assets[0].name}")
        self.assertEqual(updates["applications"]["zotero"]["strict_max_version"], settings["strict_max_version"])
        with zipfile.ZipFile(assets[1]) as z:
            self.assertFalse(any("private" in n or "engine-home" in n for n in z.namelist()))
            command, = [i for i in z.infolist() if i.filename.endswith("install-macos.command")]
            self.assertEqual((command.external_attr >> 16) & 0o777, 0o755)
        for asset in assets[:-1]:
            self.assertIn(hashlib.sha256(asset.read_bytes()).hexdigest() + "  " + asset.name, assets[-1].read_text())

    def test_repeated_build_is_identical(self):
        one = build.build(self.root, self.root / "one", "example/repo")
        two = build.build(self.root, self.root / "two", "example/repo")
        self.assertEqual([p.read_bytes() for p in one], [p.read_bytes() for p in two])

    def test_reject_tag_and_metadata_mismatch(self):
        with self.assertRaises(ValueError):
            build.build(self.root, repository="example/repo", tag="v999.0.0")
        pkg = json.loads((self.root / "package.json").read_text())
        pkg["version"] = "999.0.0"
        (self.root / "package.json").write_text(json.dumps(pkg))
        with self.assertRaises(ValueError):
            build.build(self.root)

    def test_reject_missing_required_update_url(self):
        path = self.root / "addon/manifest.json"
        manifest = json.loads(path.read_text())
        del manifest["applications"]["zotero"]["update_url"]
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            build.build(self.root)

    def test_reject_unsafe_repository_and_prerelease_version(self):
        for repository in ("example/../repo", "example/repo?key=secret", "bad;cmd/repo", "example/.."):
            with self.assertRaises(ValueError):
                build.build(self.root, repository=repository)
        path = self.root / "addon/manifest.json"
        manifest = json.loads(path.read_text()); manifest["version"] = "0.2.0-beta.1"
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            build.build(self.root)


if __name__ == "__main__":
    unittest.main()
