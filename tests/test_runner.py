"""Bridge validation tests. Run with the installed engine Python."""
import importlib.util
import io
import json
import pathlib
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

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

    def test_reject_invalid_response_settings(self):
        for change in ({"thinking": "unknown"}, {"max_output_tokens": 511},
                       {"max_output_tokens": 131073}, {"max_output_tokens": True},
                       {"max_output_tokens": 8192.5}, {"ignore_cache": "false"}, {"debug": "true"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                runner.validate(dict(self.request, **change))

    def test_debug_passed_to_engine(self):
        runner.probe()
        kwargs = runner.config_kwargs(dict(self.request, debug=True), object(), object())
        self.assertTrue(kwargs["debug"])

    @staticmethod
    def completion(content="有效译文", finish="stop"):
        return types.SimpleNamespace(usage=None, choices=[types.SimpleNamespace(
            finish_reason=finish, message=types.SimpleNamespace(content=content))])

    def protected_translator(self, **options):
        runner.probe()
        from babeldoc.translator.translator import set_translate_rate_limiter
        set_translate_rate_limiter(1000)
        request = dict(self.request, **options)
        guard = runner.ResponseGuard(request, self.output)
        return runner.make_translator(request, guard), guard

    def test_empty_response_retried_and_valid_response_cached(self):
        with patch("openai.resources.chat.completions.Completions.create",
                   side_effect=[self.completion(""), self.completion()]) as create:
            translator, guard = self.protected_translator()
            prompt = str(self.root)
            self.assertEqual(translator.llm_translate(prompt), "有效译文")
            self.assertEqual(translator.llm_translate(prompt), "有效译文")
            self.assertEqual(create.call_count, 2)
            self.assertEqual(create.call_args.kwargs["max_tokens"], 8192)
            self.assertEqual(create.call_args.kwargs["extra_body"]["thinking"], {"type": "disabled"})
            guard.check()

    def test_persistent_empty_or_truncated_response_never_cached(self):
        for content, finish in ((" ", "stop"), (None, "stop"), ("半截译文", "length")):
            with self.subTest(content=content, finish=finish):
                with patch("openai.resources.chat.completions.Completions.create",
                           return_value=self.completion(content, finish)) as create:
                    translator, guard = self.protected_translator(debug=True)
                    prompt = str(self.root) + str(content) + finish
                    with self.assertRaises(runner.TranslationQualityError):
                        translator.llm_translate(prompt)
                    self.assertEqual(create.call_count, 3)
                    self.assertIsNone(translator.cache.get(prompt))
                    with self.assertRaises(runner.TranslationQualityError):
                        guard.check()
        diagnostics = (self.output / "diagnostics.jsonl").read_text()
        self.assertNotIn(self.request["api_key"], diagnostics)
        self.assertNotIn("半截译文", diagnostics)

    def test_ignore_cache_auto_thinking_and_custom_token_limit(self):
        with patch("openai.resources.chat.completions.Completions.create",
                   return_value=self.completion()) as create:
            translator, guard = self.protected_translator(thinking="auto", ignore_cache=True,
                                                          max_output_tokens=16384)
            for _ in range(2):
                translator.llm_translate(str(self.root))
            self.assertEqual(create.call_count, 2)
            self.assertNotIn("thinking", create.call_args.kwargs["extra_body"])
            self.assertEqual(create.call_args.kwargs["max_tokens"], 16384)
            guard.check()

    def test_service_error_marks_job_unsafe_even_if_engine_swallows_it(self):
        with patch("openai.resources.chat.completions.Completions.create",
                   side_effect=RuntimeError("unsupported thinking parameter")):
            translator, guard = self.protected_translator()
            with self.assertRaises(RuntimeError):
                translator.llm_translate(str(self.root))
            with self.assertRaises(runner.TranslationQualityError):
                guard.check()

    def test_empty_cache_is_ignored_without_deleting_it(self):
        original = Mock()
        cache = runner.NonEmptyCache(original)
        for value in (None, "", " \n"):
            original.get.return_value = value
            self.assertIsNone(cache.get("source"))
            cache.set("source", value)
        original.set.assert_not_called()
        original.get.return_value = "译文"
        self.assertEqual(cache.get("source"), "译文")
        cache.set("source", "译文")
        original.set.assert_called_once_with("source", "译文")

    def test_empty_paragraph_preserves_original_and_guard_restores_method(self):
        runner.probe()
        from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator, ParagraphTranslateTracker
        from babeldoc.format.pdf.document_il import PdfParagraph, PdfStyle, PdfParagraphComposition, PdfSameStyleUnicodeCharacters
        style = PdfStyle(font_id="base", font_size=10)
        paragraph = PdfParagraph(unicode="Original text", pdf_style=style,
            pdf_paragraph_composition=[PdfParagraphComposition(
                pdf_same_style_unicode_characters=PdfSameStyleUnicodeCharacters(unicode="Original text", pdf_style=style))])
        previous = ILTranslator.post_translate_paragraph
        guard = runner.ResponseGuard(self.request, self.output)
        il = object.__new__(ILTranslator)
        tracker = ParagraphTranslateTracker()
        translate_input = ILTranslator.TranslateInput("Original text", [], style)
        with runner.protect_paragraphs(guard):
            with self.assertRaises(runner.TranslationQualityError):
                il.post_translate_paragraph(paragraph, tracker, translate_input, "")
        self.assertEqual(paragraph.unicode, "Original text")
        self.assertEqual(len(paragraph.pdf_paragraph_composition), 1)
        self.assertIs(ILTranslator.post_translate_paragraph, previous)
        with self.assertRaises(runner.TranslationQualityError):
            guard.check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
