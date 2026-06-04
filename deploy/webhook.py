#!/usr/bin/env python3
"""GitHub webhook receiver — 收到默认分支 push 后异步执行 deploy.sh。

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
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

LISTEN_HOST = os.getenv("WEBHOOK_HOST", "127.0.0.1")
LISTEN_PORT = int(os.getenv("WEBHOOK_PORT", "9000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").encode()
DEPLOY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy.sh")
MAX_PAYLOAD_BYTES = int(os.getenv("WEBHOOK_MAX_PAYLOAD_BYTES", "1048576"))
LOG_DIR = Path(os.getenv("WEBHOOK_LOG_DIR", "/opt/business-analysis/backend/logs"))


def _deploy_already_running() -> bool:
    result = subprocess.run(
        ["pgrep", "-f", f"bash {DEPLOY_SCRIPT}"],
        capture_output=True,
        text=True,
    )
    current_pid = str(os.getpid())
    pids = [pid for pid in result.stdout.split() if pid != current_pid]
    return bool(pids)


def start_deploy() -> tuple[bool, str]:
    """Start deploy.sh in the background and return (started, log_path)."""
    if _deploy_already_running():
        return False, ""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"webhook-deploy-{time.strftime('%Y%m%d_%H%M%S')}.log"
    with open(log_path, "ab", buffering=0) as log_file:
        subprocess.Popen(
            ["sudo", "/usr/bin/env", "bash", DEPLOY_SCRIPT],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return True, str(log_path)


class WebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_PAYLOAD_BYTES:
            self.send_response(413)
            self.end_headers()
            self.wfile.write(b"payload too large")
            return
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

            started, log_path = start_deploy()
            if not started:
                print("[webhook] deploy skipped: deployment already running", flush=True)
                self.send_response(202)
                self.end_headers()
                self.wfile.write(b"deployment already running")
                return

            print(f"[webhook] push to {default_branch}, deploy started: {log_path}", flush=True)
            self.send_response(202)
            self.end_headers()
            self.wfile.write(f"deploy accepted\nlog: {log_path}".encode())
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
