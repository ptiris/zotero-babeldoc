"""Local deterministic OpenAI-style fixture. Contains no real model or API key.
Used solely to verify engine and Zotero integration, not translation quality.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    calls = 0
    response_mode = "normal"
    request_options = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        type(self).calls += 1
        type(self).request_options.append({"max_tokens": body.get("max_tokens"),
                                           "thinking": body.get("thinking")})
        text = "\n".join(str(m.get("content", "")) for m in body.get("messages", []))
        if "test translation" in text.lower():
            translated = "测试翻译"
        elif "This paper studies" in text:
            translated = "本文研究科学文档的翻译。翻译后的论文保留原始布局，并可在文献管理器中阅读。"
        elif "BabelDOC Integration Test" in text:
            translated = "BabelDOC 集成测试"
        else:
            translated = "本文研究科学文档的翻译。翻译后的论文保留原始布局，并可在文献管理器中阅读。"
        if self.response_mode == "empty" or (self.response_mode == "recover" and self.calls == 1):
            translated = ""
        finish = "length" if self.response_mode == "truncated" else "stop"
        data = json.dumps({"id": "fixture", "object": "chat.completion", "created": 1,
                           "model": body.get("model", "fixture"),
                           "choices": [{"index": 0, "message": {"role": "assistant", "content": translated},
                                        "finish_reason": finish}],
                           "usage": {"prompt_tokens": 20, "completion_tokens": 20, "total_tokens": 40}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18987)
    parser.add_argument("--response-mode", choices=("normal", "empty", "truncated", "recover"), default="normal")
    args = parser.parse_args()
    Handler.response_mode = args.response_mode
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("Mock endpoint: http://127.0.0.1:" + str(server.server_port) + "/v1", flush=True)
    server.serve_forever()
