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
    Handler.calls = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    request = dict(action="translate", input_file=str(source), output_dir=str(output), api_key="fixture-key",
                   base_url=f"http://127.0.0.1:{server.server_port}/v1", model="fixture-" + uuid.uuid4().hex,
                   lang_in="en", lang_out="zh", pages="", qps=2, output_mode="both", dual_layout="side-by-side", ocr=False)
    start = time.monotonic()
    report = {"status": "failed", "provider": "local deterministic fixture", "outputs": []}
    try:
        result = subprocess.run([sys.executable, "-u", str(runner)], input=json.dumps(request) + "\n",
                                text=True, capture_output=True, timeout=args.timeout)
        (directory / "stderr.log").write_text(result.stderr, encoding="utf-8")
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        finishes = [e for e in events if e.get("type") == "finish"]
        report.update(exit_code=result.returncode, model_requests=Handler.calls,
                      original_unchanged=hashlib.sha256(source.read_bytes()).hexdigest() == original)
        assert result.returncode == 0 and finishes, "engine failed: " + str([e for e in events if e.get('type') == 'error'])
        for item in finishes[-1]["outputs"]:
            path = Path(item["path"]).resolve()
            assert path.is_relative_to(output.resolve()), "output outside job directory"
            with pymupdf.open(path) as translated:
                text = "\n".join(page.get_text() for page in translated)
                report["outputs"].append(dict(kind=item["kind"], pages=len(translated), contains_chinese="翻译" in text))
        assert {o['kind'] for o in report['outputs']} == {'mono', 'dual'}
        assert all(o['contains_chinese'] for o in report['outputs'])
        assert report['original_unchanged'] and Handler.calls > 0
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        report['seconds'] = round(time.monotonic() - start, 1)
        (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
