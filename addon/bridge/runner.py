#!/usr/bin/env python3
"""One request over stdin, JSONL events over stdout. No shell or listening port.
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import asyncio
import importlib.metadata
import json
import logging
import math
import re
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

PINNED_VERSION = "0.6.4"
PROTOCOL = sys.stdout
SECRET = ""


class TranslationQualityError(RuntimeError):
    """A response cannot safely replace the source paragraph."""


class ResponseGuard:
    def __init__(self, request, output_dir):
        self.max_tokens = request.get("max_output_tokens", 8192)
        self.diagnostic_path = output_dir / "diagnostics.jsonl" if request.get("debug", False) else None
        self.failures = 0
        self.lock = threading.Lock()

    def record(self, event, **details):
        if self.diagnostic_path:
            with self.lock:
                with self.diagnostic_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"event": event, **details}, ensure_ascii=False) + "\n")

    def fail(self, reason):
        with self.lock:
            self.failures += 1
        self.record("response_rejected", reason=reason)

    def wrap_completion(self, create):
        def guarded_create(**kwargs):
            # Also covers BabelDOC's single-paragraph fallback. Invalid responses
            # raise before BaseTranslator can cache or apply them.
            kwargs["max_tokens"] = self.max_tokens
            for attempt in range(1, 4):
                if attempt > 1:
                    from babeldoc.translator.translator import _translate_rate_limiter
                    _translate_rate_limiter.wait()
                response = create(**kwargs)
                choices = getattr(response, "choices", None) or []
                choice = choices[0] if choices else None
                content = getattr(getattr(choice, "message", None), "content", None)
                finish = getattr(choice, "finish_reason", None)
                usage = getattr(response, "usage", None)
                self.record("completion", attempt=attempt, finish_reason=finish,
                            output_characters=len(content) if isinstance(content, str) else 0,
                            completion_tokens=getattr(usage, "completion_tokens", None))
                if finish in (None, "stop") and isinstance(content, str) and content.strip():
                    return response
                reason = "输出达到 token 上限" if finish == "length" else "模型未返回有效译文"
                if finish not in (None, "stop", "length"):
                    break
            self.fail(reason)
            raise TranslationQualityError(reason + "；已停止导入，请关闭思考模式或提高输出 token 上限后重试。")
        return guarded_create

    def check(self):
        if self.failures:
            raise TranslationQualityError(
                f"检测到 {self.failures} 次持续无效的翻译响应，未导入可能缺字的 PDF。"
                "请关闭思考模式、勾选忽略翻译缓存，或提高输出 token 上限后重试。")


class NonEmptyCache:
    """Filter historical empty values without deleting the user's cache."""
    def __init__(self, cache):
        self.cache = cache

    def __getattr__(self, name):
        return getattr(self.cache, name)

    def get(self, text):
        result = self.cache.get(text)
        return result if isinstance(result, str) and result.strip() else None

    def set(self, text, translation):
        if isinstance(translation, str) and translation.strip():
            self.cache.set(text, translation)


def make_translator(request, guard):
    from babeldoc.translator.translator import OpenAITranslator

    class GuardedOpenAITranslator(OpenAITranslator):
        def do_llm_translate(self, text, rate_limit_params=None):
            try:
                return super().do_llm_translate(text, rate_limit_params)
            except TranslationQualityError:
                raise
            except Exception:
                guard.fail("模型服务请求失败")
                raise

        def do_translate(self, text, rate_limit_params=None):
            try:
                return super().do_translate(text, rate_limit_params)
            except TranslationQualityError:
                raise
            except Exception:
                guard.fail("模型服务请求失败")
                raise

    thinking = request.get("thinking", "disabled")
    translator = GuardedOpenAITranslator(
        lang_in=request["lang_in"], lang_out=request["lang_out"], model=request["model"],
        base_url=request["base_url"], api_key=request["api_key"],
        thinking=None if thinking == "auto" else thinking,
        ignore_cache=request.get("ignore_cache", False))
    # Separate protected output from older, potentially truncated cached results.
    translator.add_cache_impact_parameters("zotero_response_guard", 1)
    translator.add_cache_impact_parameters("max_output_tokens", guard.max_tokens)
    translator.cache = NonEmptyCache(translator.cache)
    translator.client.chat.completions.create = guard.wrap_completion(translator.client.chat.completions.create)
    return translator


@contextmanager
def protect_paragraphs(guard):
    from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator
    from unittest.mock import patch
    original = ILTranslator.post_translate_paragraph

    def guarded_post(self, paragraph, tracker, translate_input, translated_text):
        # A nonempty JSON response can still contain an empty paragraph output.
        if not isinstance(translated_text, str) or not translated_text.strip():
            guard.fail("段落译文为空")
            raise TranslationQualityError("段落译文为空，保留原文并将任务标记为失败。")
        return original(self, paragraph, tracker, translate_input, translated_text)

    with patch.object(ILTranslator, "post_translate_paragraph", guarded_post):
        yield


def clean(value):
    text = str(value)
    if SECRET:
        text = text.replace(SECRET, "[REDACTED]")
    text = re.sub(r"(?i)(authorization[\s:]+(?:bearer\s+)?)[^\s,\"']+", r"\1[REDACTED]", text)
    return text[:1500]


def emit(event):
    PROTOCOL.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
    PROTOCOL.flush()


def probe():
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        raise ValueError("需要 Python 3.10–3.13；推荐 Python 3.12。")
    try:
        version = importlib.metadata.version("BabelDOC")
    except importlib.metadata.PackageNotFoundError as error:
        raise ValueError("此 Python 环境未安装 BabelDOC。请运行安装脚本或安装 BabelDOC==0.6.4。") from error
    if version != PINNED_VERSION:
        raise ValueError(f"当前 BabelDOC {version}；此插件要求 BabelDOC {PINNED_VERSION}。")
    # BabelDOC 0.6.4 hardcodes Path.home() at module import; redirect only that
    # initialization so its models/fonts/cache stay next to the extracted bridge.
    from unittest.mock import patch
    with patch.object(Path, "home", return_value=Path(__file__).resolve().parent / "engine-home"):
        import babeldoc.const  # noqa: F401
    # Check native wheels/imports too, without downloading assets or calling the model.
    from babeldoc.format.pdf.high_level import async_translate  # noqa: F401
    from babeldoc.docvision.doclayout import DocLayoutModel  # noqa: F401
    return {"type": "probe", "babeldoc": version, "python": sys.version.split()[0], "executable": sys.executable}


def validate(request):
    input_file = Path(request["input_file"]).expanduser().resolve(strict=True)
    if not input_file.is_file() or input_file.suffix.lower() != ".pdf":
        raise ValueError("输入必须是本地 PDF 文件。")
    with input_file.open("rb") as stream:
        if not stream.read(1024).lstrip().startswith(b"%PDF-"):
            raise ValueError("输入文件没有有效的 PDF 文件头。")
    output_dir = Path(request["output_dir"]).expanduser().resolve(strict=True)
    if not output_dir.is_dir() or input_file.parent == output_dir:
        raise ValueError("输出必须是独立的任务目录。")
    endpoint = urlsplit(request.get("base_url", ""))
    if endpoint.scheme not in ("http", "https") or not endpoint.netloc or endpoint.username or endpoint.password:
        raise ValueError("模型服务地址必须是 HTTP(S) 地址，且不能包含账号密码。")
    for key in ("model", "api_key", "lang_in", "lang_out"):
        if not str(request.get(key, "")).strip():
            raise ValueError(f"缺少配置项：{key}")
    pages = str(request.get("pages", "")).strip()
    if pages and not re.fullmatch(r"\d+(?:-\d+)?(?:\s*,\s*\d+(?:-\d+)?)*", pages):
        raise ValueError("页码格式应为 1,3-5，留空表示全文。")
    if pages:
        for part in pages.split(","):
            bounds = [int(p) for p in part.strip().split("-")]
            if min(bounds) < 1 or len(bounds) == 2 and bounds[0] > bounds[1]:
                raise ValueError("页码从 1 开始，范围必须从小到大。")
    qps = int(request.get("qps", 2))
    if not 1 <= qps <= 20:
        raise ValueError("每秒请求数须在 1–20 范围内。")
    mode = request.get("output_mode", "both")
    if mode not in ("mono", "dual", "both"):
        raise ValueError("无效的 PDF 输出模式。")
    if request.get("thinking", "disabled") not in ("disabled", "enabled", "auto"):
        raise ValueError("思考模式须选择关闭、开启或服务默认。")
    tokens = request.get("max_output_tokens", 8192)
    if type(tokens) is not int or not 512 <= tokens <= 131072:
        raise ValueError("输出 token 上限须为 512–131072 的整数，并符合模型服务限制。")
    for option in ("ignore_cache", "debug"):
        if type(request.get(option, False)) is not bool:
            raise ValueError(f"{option} 须为布尔值。")
    return input_file, output_dir, pages or None, qps, mode


def config_kwargs(request, layout, translator):
    input_file, output_dir, pages, qps, mode = validate(request)
    from babeldoc.format.pdf.translation_config import WatermarkOutputMode
    return dict(translator=translator, term_extraction_translator=translator,
                input_file=str(input_file), output_dir=str(output_dir),
                working_dir=str(output_dir / "work"), lang_in=request["lang_in"],
                lang_out=request["lang_out"], doc_layout_model=layout, pages=pages,
                qps=qps, pool_max_workers=qps, term_pool_max_workers=qps,
                no_mono=mode == "dual", no_dual=mode == "mono",
                use_alternating_pages_dual=request.get("dual_layout") == "alternating",
                auto_enable_ocr_workaround=bool(request.get("ocr", False)),
                debug=request.get("debug", False),
                auto_extract_glossary=False, save_auto_extracted_glossary=False,
                watermark_output_mode=WatermarkOutputMode.NoWatermark,
                report_interval=0.3)


def collect_outputs(result, output_dir):
    outputs = []
    for kind, attrs in [
        ("mono", ("no_watermark_mono_pdf_path", "mono_pdf_path")),
        ("dual", ("no_watermark_dual_pdf_path", "dual_pdf_path")),
    ]:
        path = next((getattr(result, attr, None) for attr in attrs if getattr(result, attr, None)), None)
        if not path:
            continue
        path = Path(path).resolve(strict=True)
        if path.parent != output_dir.resolve() or path.suffix.lower() != ".pdf":
            raise ValueError("BabelDOC 返回了任务目录外的输出路径。")
        with path.open("rb") as stream:
            if not stream.read(1024).lstrip().startswith(b"%PDF-"):
                raise ValueError("翻译结果不是有效的 PDF。")
        outputs.append({"kind": kind, "path": str(path)})
    if not outputs:
        raise ValueError("BabelDOC 未生成 PDF。")
    return outputs


async def translate(request):
    _, output_dir, _, qps, _ = validate(request)
    emit({"type": "progress", "stage": "检查 BabelDOC 环境…", "progress": 0})
    probe()
    from babeldoc.format.pdf import high_level
    from babeldoc.docvision.doclayout import DocLayoutModel
    from babeldoc.format.pdf.translation_config import TranslationConfig
    from babeldoc.translator.translator import set_translate_rate_limiter
    high_level.init()
    emit({"type": "progress", "stage": "加载版面模型与字体，首次使用会下载资源…", "progress": 0})
    guard = ResponseGuard(request, output_dir)
    guard.record("settings", thinking=request.get("thinking", "disabled"),
                 ignore_cache=request.get("ignore_cache", False), max_output_tokens=guard.max_tokens,
                 babeldoc=PINNED_VERSION)
    translator = make_translator(request, guard)
    set_translate_rate_limiter(qps)
    # BabelDOC 0.6.4 auto-selects CoreML on macOS. CoreML can abort at
    # interpreter shutdown when launched from Zotero (SIGABRT / recursive_mutex).
    # Restrict this one model load to ONNX's portable CPU execution provider.
    import onnxruntime
    from unittest.mock import patch
    with patch.object(onnxruntime, "get_available_providers", return_value=["CPUExecutionProvider"]):
        layout = DocLayoutModel.load_onnx()
    config = TranslationConfig(**config_kwargs(request, layout, translator))
    getattr(layout, "init_font_mapper", lambda _: None)(config)
    complete = False
    with protect_paragraphs(guard):
        async for event in high_level.async_translate(config):
            if event["type"].startswith("progress_"):
                number = float(event.get("overall_progress", 0))
                stage = clean(event.get("stage", "翻译中"))
                guard.record("progress", stage=stage, progress=number if math.isfinite(number) else 0)
                emit({"type": "progress", "stage": stage,
                      "progress": max(0, min(100, number)) if math.isfinite(number) else 0})
            elif event["type"] == "error":
                guard.record("engine_error")
                guard.check()
                raise RuntimeError(clean(event.get("error", "BabelDOC 翻译失败")))
            elif event["type"] == "finish":
                guard.check()
                outputs = collect_outputs(event["translate_result"], output_dir)
                complete = True
                guard.record("finish", output_kinds=[o["kind"] for o in outputs])
                emit({"type": "finish", "outputs": outputs})
                break
    if not complete:
        raise RuntimeError("BabelDOC 意外退出，未返回完成事件。")


def main():
    global SECRET
    # Keep third-party print/logs off the protocol stream.
    sys.stdout = sys.stderr
    logging.disable(logging.CRITICAL)
    try:
        line = sys.stdin.readline(1024 * 1024 + 1)
        if len(line) > 1024 * 1024:
            raise ValueError("请求过大。")
        request = json.loads(line)
        SECRET = str(request.get("api_key", ""))
        if request.get("action") == "probe":
            emit(probe())
        elif request.get("action") == "translate":
            asyncio.run(translate(request))
        else:
            raise ValueError("未知操作。")
    except (Exception, SystemExit) as error:
        emit({"type": "error", "message": clean(error)})
        return 1
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
