#!/usr/bin/env python3
"""뷰어 캔버스를 파일로 받아 두는 아주 작은 서버.

브라우저 스크린샷 도구는 데스크톱 창이 보여야 하는데, 창이 가려지면 실패한다.
그래서 페이지 안에서 canvas.toDataURL() 로 WebGL 픽셀을 직접 꺼내
이 서버로 POST 해서 파일로 떨군다. 각도별로 같은 크기·같은 조건이 나온다.

    uv run python scripts/capture_server.py 8778

페이지 쪽:
    fetch("http://localhost:8778/save?name=a0", {method:"POST", body: dataURL})
"""
import base64
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        q = parse_qs(urlparse(self.path).query)
        name = (q.get("name") or ["capture"])[0]
        name = "".join(ch for ch in name if ch.isalnum() or ch in "-_")
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("ascii", "replace")
        if "," in body:
            head, body = body.split(",", 1)
        else:
            head = "data:image/png"
        ext = "jpg" if "jpeg" in head or "jpg" in head else "png"
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, f"{name}.{ext}")
        with open(path, "wb") as f:
            f.write(base64.b64decode(body))
        size = os.path.getsize(path)
        print(f"saved {path} {size:,}B", flush=True)

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"ok {size}".encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8778
    print(f"capture server on http://localhost:{port}  -> {OUT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
