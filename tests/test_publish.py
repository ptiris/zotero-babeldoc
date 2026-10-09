"""Test publish ordering and rollback/immutable-release protection without GitHub."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("publish", ROOT / "scripts/publish.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self.tmp.name)
        self.repo = "example/repo"
        self.version = "0.1.2"
        self.xpi = self.dist / "zotero-babeldoc-0.1.2.xpi"
        self.xpi.write_bytes(b"fixture-xpi")
        self.entry = {"version": self.version, "update_link": "https://github.com/example/repo/releases/download/v0.1.2/" + self.xpi.name,
                      "update_hash": "sha256:" + hashlib.sha256(self.xpi.read_bytes()).hexdigest()}
        self.updates = {"addons": {"fixture": {"updates": [self.entry]}}}
        (self.dist / "updates.json").write_text(json.dumps(self.updates))
        for name in ("zotero-babeldoc-0.1.2-source.zip", "SHA256SUMS.txt", "release-notes.md"):
            (self.dist / name).write_text("fixture")

    def tearDown(self):
        self.tmp.cleanup()

    def test_publish_assets_before_update_channel(self):
        commands = []
        def fake(repo, *args, **kwargs):
            commands.append(args)
            return types.SimpleNamespace(stdout="[]" if args[0] == "list" else "")
        with patch.object(publish, "gh", side_effect=fake):
            publish.publish(self.repo, self.dist)
        names = [(a[0], a[1]) for a in commands]
        self.assertLess(names.index(("upload", "v0.1.2")), names.index(("edit", "v0.1.2")))
        self.assertLess(names.index(("edit", "v0.1.2")), names.index(("create", "release")))
        channel = commands[-1]
        self.assertIn("--latest=false", channel)

    def test_refuse_immutable_update_channel_before_mutations(self):
        with patch.object(publish, "gh", return_value=types.SimpleNamespace(stdout=json.dumps([
                {"tagName": "release", "isDraft": False, "isImmutable": True}])) ) as mock:
            with self.assertRaises(ValueError):
                publish.publish(self.repo, self.dist)
            self.assertEqual(mock.call_count, 1)

    def test_refuse_channel_rollback_before_mutations(self):
        commands = []
        newer = json.loads(json.dumps(self.updates)); newer["addons"]["fixture"]["updates"][0]["version"] = "0.2.0"
        def fake(repo, *args, **kwargs):
            commands.append(args)
            if args[0] == "download":
                destination = Path(args[args.index("--dir") + 1])
                (destination / "updates.json").write_text(json.dumps(newer))
            return types.SimpleNamespace(stdout=json.dumps([{"tagName": "release", "isDraft": False}]) if args[0] == "list" else "")
        with patch.object(publish, "gh", side_effect=fake), self.assertRaises(ValueError):
            publish.publish(self.repo, self.dist)
        self.assertEqual([c[0] for c in commands], ["list", "download"])

    def test_refuse_modified_published_assets(self):
        commands = []
        def fake(repo, *args, **kwargs):
            commands.append(args)
            return types.SimpleNamespace(stdout=json.dumps([{"tagName": "v0.1.2", "isDraft": False}]) if args[0] == "list" else "")
        with patch.object(publish, "gh", side_effect=fake), self.assertRaises(ValueError):
            publish.publish(self.repo, self.dist)
        self.assertFalse(any(c[0] in ("upload", "create", "edit") for c in commands))


if __name__ == "__main__":
    unittest.main()
