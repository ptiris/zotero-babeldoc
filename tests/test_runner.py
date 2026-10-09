"""Bridge validation tests. Run with the installed engine Python."""
import importlib.util
import io
import json
import pathlib
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "addon/bridge/runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.input = self.root / "论文 with spaces.pdf"
        self.input.write_bytes(b"%PDF-1.7\nfixture")
        self.output = self.root / "output"
        self.output.mkdir()
        self.request = dict(input_file=str(self.input), output_dir=str(self.output),
                            base_url="http://127.0.0.1:9988/v1", api_key="test-secret-xyz",
                            model="test", lang_in="en", lang_out="zh", qps=2, pages="1,3-5")

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_local_path_and_page_ranges(self):
        self.assertEqual(runner.validate(self.request)[2:], ("1,3-5", 2, "both"))

    def test_reject_invalid_pages(self):
        for pages in ("0", "5-3", "1;rm", "-1", "1,", "foo"):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                runner.validate(dict(self.request, pages=pages))

    def test_reject_fake_pdf(self):
        self.input.write_bytes(b"hello")
        with self.assertRaises(ValueError):
            runner.validate(self.request)

    def test_reject_bad_endpoint(self):
        for url in ("file:///tmp/api", "https://user:key@example.com/v1", "localhost:9988"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                runner.validate(dict(self.request, base_url=url))

    def test_reject_out_of_range_qps(self):
        for qps in (0, 21, -2):
            with self.subTest(qps=qps), self.assertRaises(ValueError):
                runner.validate(dict(self.request, qps=qps))

    def test_result_requires_existing_pdf_inside_job(self):
        outside = types.SimpleNamespace(mono_pdf_path=self.input)
        with self.assertRaises(ValueError):
            runner.collect_outputs(outside, self.output)
        with self.assertRaises(ValueError):
            runner.collect_outputs(types.SimpleNamespace(), self.output)

    def test_results_preserve_mode_and_paths_with_unicode(self):
        mono = self.output / "论文.zh.mono.pdf"
        dual = self.output / "论文.zh.dual.pdf"
        for path in (mono, dual):
            path.write_bytes(b"%PDF-1.7\nfixture")
        result = types.SimpleNamespace(no_watermark_mono_pdf_path=mono, no_watermark_dual_pdf_path=dual)
        self.assertEqual([o["kind"] for o in runner.collect_outputs(result, self.output)], ["mono", "dual"])

    def test_secrets_redacted(self):
        runner.SECRET = self.request["api_key"]
        self.assertNotIn(runner.SECRET, runner.clean("failed with " + runner.SECRET))
        self.assertNotIn("abcd", runner.clean("Authorization: Bearer abcd"))
        runner.SECRET = ""

    def test_protocol_json_unicode(self):
        previous = runner.PROTOCOL
        try:
            runner.PROTOCOL = io.StringIO()
            runner.emit({"type": "progress", "stage": "翻译中", "progress": 25})
            self.assertEqual(json.loads(runner.PROTOCOL.getvalue())["stage"], "翻译中")
        finally:
            runner.PROTOCOL = previous

    def test_actual_babeldoc_config_signature(self):
        runner.probe()
        from babeldoc.format.pdf.translation_config import TranslationConfig
        for mode in ("both", "mono", "dual"):
            request = dict(self.request, output_mode=mode)
            kwargs = runner.config_kwargs(request, object(), object())
            import inspect
            inspect.signature(TranslationConfig).bind(**kwargs)
            self.assertEqual(kwargs["no_mono"], mode == "dual")
            self.assertEqual(kwargs["no_dual"], mode == "mono")


if __name__ == "__main__":
    unittest.main(verbosity=2)
