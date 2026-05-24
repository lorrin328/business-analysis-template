#!/usr/bin/env python3
"""GitHub webhook receiver — 收到 master push 后自动执行 deploy.sh。

启动方式（systemd）：
    sudo systemctl start webhook-deploy

手动测试：
    WEBHOOK_SECRET=your_secret python3 deploy/webhook.py
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

LISTEN_HOST = os.getenv("WEBHOOK_HOST", "127.0.0.1")
LISTEN_PORT = int(os.getenv("WEBHOOK_PORT", "9000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").encode()
DEPLOY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy.sh")


def run_deploy():
    """执行一键部署脚本，返回 (ok: bool, output: str)。"""
    try:
        result = subprocess.run(
            ["sudo", "/usr/bin/env", "bash", DEPLOY_SCRIPT],
            capture_output=True, text=True, timeout=300,
        )
        output = result.stdout.strip() + "\n" + result.stderr.strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "DEPLOY TIMEOUT after 300s"
    except Exception as exc:
        return False, f"DEPLOY ERROR: {exc}"


class WebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 验证签名
        if WEBHOOK_SECRET:
            sig = self.headers.get("X-Hub-Signature-256", "")
            expected = "sha256=" + hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"invalid signature")
                return

        event = self.headers.get("X-GitHub-Event", "")
        if event != "ping":
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {}

        if event == "ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pong")
            return

        if event == "push":
            ref = payload.get("ref", "")
            default_branch = payload.get("repository", {}).get("default_branch", "master")
            if ref != f"refs/heads/{default_branch}":
                # 非默认分支，跳过
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"skipped (not default branch)")
                return

            print(f"[webhook] push to {default_branch}, deploying...", flush=True)
            ok, output = run_deploy()
            status = "OK" if ok else "FAIL"
            print(f"[webhook] deploy {status}", flush=True)
            print(output, flush=True)

            self.send_response(200 if ok else 500)
            self.end_headers()
            self.wfile.write(f"deploy {status}\n{output}".encode())
            return

        # 其他事件忽略
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ignored")

    def log_message(self, format, *args):
        print(f"[webhook] {args[0]}", flush=True)


if __name__ == "__main__":
    if not WEBHOOK_SECRET:
        print("[webhook] ERROR: WEBHOOK_SECRET is required; refusing to start", flush=True)
        sys.exit(1)
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), WebhookHandler)
    print(f"[webhook] listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
