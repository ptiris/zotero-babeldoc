"""Real BabelDOC + local deterministic model fixture; never uses a paid API."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

import pymupdf
from mock_model import Handler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=ROOT / "test-results/engine-smoke")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--response-mode", choices=("normal", "empty", "truncated", "recover"), default="normal")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve(); directory.mkdir(parents=True, exist_ok=True)
    runner = directory / "runner.py"
    shutil.copy2(ROOT / "addon/bridge/runner.py", runner)
    job = directory / ("job-" + uuid.uuid4().hex); job.mkdir()
    source = job / "BabelDOC integration test.pdf"
    pdf = pymupdf.open(); page = pdf.new_page(width=595, height=842)
    page.insert_text((64, 80), "BabelDOC Integration Test", fontsize=22)
    page.insert_textbox(pymupdf.Rect(64, 140, 530, 270), "This paper studies the translation of scientific documents. The translated paper preserves its original layout and can be read inside the reference manager.", fontsize=12)
    pdf.save(source); pdf.close()
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    output = job / "output"; output.mkdir()
    handler = type("FixtureHandler", (Handler,), dict(calls=0, response_mode=args.response_mode, request_options=[]))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    request = dict(action="translate", input_file=str(source), output_dir=str(output), api_key="fixture-key",
                   base_url=f"http://127.0.0.1:{server.server_port}/v1", model="fixture-" + uuid.uuid4().hex,
                   lang_in="en", lang_out="zh", pages="", qps=10, output_mode="both", dual_layout="side-by-side", ocr=False,
                   thinking="disabled", max_output_tokens=8192, ignore_cache=True, debug=args.debug)
    start = time.monotonic()
    report = {"status": "failed", "provider": "local deterministic fixture", "outputs": []}
    try:
        result = subprocess.run([sys.executable, "-u", str(runner)], input=json.dumps(request) + "\n",
                                text=True, capture_output=True, timeout=args.timeout)
        (directory / "stderr.log").write_text(result.stderr, encoding="utf-8")
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        finishes = [e for e in events if e.get("type") == "finish"]
        report.update(exit_code=result.returncode, model_requests=handler.calls, scenario=args.response_mode,
                      request_options=handler.request_options,
                      original_unchanged=hashlib.sha256(source.read_bytes()).hexdigest() == original)
        assert report['original_unchanged'] and handler.calls > 0
        assert all(r['max_tokens'] == 8192 and r['thinking'] == {'type': 'disabled'} for r in handler.request_options)
        if args.response_mode in ("empty", "truncated"):
            errors = [e for e in events if e.get("type") == "error"]
            assert result.returncode != 0 and not finishes and errors, "unsafe engine output was accepted"
            assert "翻译响应" in errors[-1]["message"] or "译文" in errors[-1]["message"]
            report.update(status="passed", expected_rejection=True, error_message=errors[-1]["message"])
            return
        assert result.returncode == 0 and finishes, "engine failed: " + str([e for e in events if e.get('type') == 'error'])
        for item in finishes[-1]["outputs"]:
            path = Path(item["path"]).resolve()
            assert path.is_relative_to(output.resolve()), "output outside job directory"
            with pymupdf.open(path) as translated:
                text = "\n".join(page.get_text() for page in translated)
                report["outputs"].append(dict(kind=item["kind"], pages=len(translated), contains_chinese="翻译" in text))
        assert {o['kind'] for o in report['outputs']} == {'mono', 'dual'}
        assert all(o['contains_chinese'] for o in report['outputs'])
        if args.debug:
            assert (output / 'diagnostics.jsonl').is_file()
            assert list((output / 'work').rglob('il_translated.json'))
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        report['seconds'] = round(time.monotonic() - start, 1)
        report_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        (directory / "report.json").write_text(report_text, encoding="utf-8")
        (directory / ("report-" + args.response_mode + ".json")).write_text(report_text, encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
