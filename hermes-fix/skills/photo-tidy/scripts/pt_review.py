#!/usr/bin/env python3
"""Serve the local review page for a run and store the decisions it makes.
The page reads plan.json and the inventory, shows junk, duplicates, groups
and names in that order, and writes decisions.json on every change. The
"Approve" button stamps decisions.json with the plan's hash; pt_apply.py
refuses to run without that stamp.

  python3 pt_review.py serve [--run-dir DIR] [--host 127.0.0.1] [--port 8765] [--background]
  python3 pt_review.py status
  python3 pt_review.py stop

Bind to the Mac's Tailscale address (--host 100.x.y.z) to review from the
iPhone. Only decisions.json is ever written. Exit 0 ok, 1 error.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

PAGE = os.path.join(C.HERE, "review_page.html")
MAX_BODY = 30 * 1024 * 1024
COMPACT_KEYS = ("name", "thumb", "date", "kind", "w", "h", "bytes", "favorite", "screenshot", "persons", "place")


class State:
    def __init__(self, run_dir, cfg):
        self.run_dir = run_dir
        self.cfg = cfg
        self.tdir = C.thumbs_dir(cfg)
        self.plan_path = os.path.join(run_dir, "plan.json")
        self.dec_path = os.path.join(run_dir, "decisions.json")
        self.lock = threading.Lock()
        self.plan_hash = C.sha256_file(self.plan_path)
        plan = C.read_json(self.plan_path)
        plan["apply_command"] = f"python3 {os.path.join(C.HERE, 'pt_apply.py')} --run-dir {run_dir} --yes"
        self.plan_bytes = json.dumps(plan, ensure_ascii=False).encode("utf-8")
        inv = {}
        for r in C.read_jsonl(os.path.join(run_dir, "inventory.jsonl")):
            d = {k: r.get(k) for k in COMPACT_KEYS if r.get(k) not in (None, False, [], {}, "")}
            if d.get("place"):
                d["place"] = d["place"].get("city") or d["place"].get("name") or ""
            d["labels"] = (r.get("labels") or [])[:3]
            inv[r["id"]] = d
        self.inv_bytes = json.dumps(inv, ensure_ascii=False).encode("utf-8")

    def decisions(self):
        d = C.read_json(self.dec_path, None)
        if not d:
            d = {"version": 1, "junk": {}, "dups": {}, "events": {}, "keep": {}, "approved_at": None, "plan_hash": None}
        return d

    def save(self, d, approve=False):
        if not isinstance(d, dict):
            raise ValueError("decisions must be an object")
        d.setdefault("version", 1)
        for k in ("junk", "dups", "events", "keep"):
            if not isinstance(d.get(k, {}), dict):
                raise ValueError(f"{k} must be an object")
            d.setdefault(k, {})
        if approve:
            d["approved_at"] = C.iso(C.now_local())
            d["plan_hash"] = self.plan_hash
        elif d.get("plan_hash") and d["plan_hash"] != self.plan_hash:
            d["approved_at"], d["plan_hash"] = None, None
        d["updated_at"] = C.iso(C.now_local())
        with self.lock:
            C.write_json(self.dec_path, d)
        return d


def make_handler(state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                with open(PAGE, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if path == "/api/plan":
                return self._send(200, state.plan_bytes)
            if path == "/api/inventory":
                return self._send(200, state.inv_bytes)
            if path == "/api/decisions":
                return self._send(200, json.dumps(state.decisions()).encode("utf-8"))
            if path.startswith("/thumbs/"):
                name = os.path.basename(path[len("/thumbs/"):])
                full = os.path.join(state.tdir, name)
                if name.endswith(".jpg") and os.path.isfile(full):
                    with open(full, "rb") as fh:
                        data = fh.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    return self.wfile.write(data)
                return self._send(404, b"not found", "text/plain")
            return self._send(404, b"not found", "text/plain")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, json.dumps({"ok": False, "error": "body too large"}).encode())
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except ValueError as err:
                return self._send(400, json.dumps({"ok": False, "error": f"bad json: {err}"}).encode())
            try:
                if path == "/api/decisions":
                    d = state.save(body)
                    return self._send(200, json.dumps({"ok": True, "updated_at": d["updated_at"]}).encode())
                if path == "/api/approve":
                    d = state.save(body, approve=True)
                    return self._send(200, json.dumps({"ok": True, "approved_at": d["approved_at"], "plan_hash": d["plan_hash"]}).encode())
            except (ValueError, OSError) as err:
                return self._send(400, json.dumps({"ok": False, "error": str(err)}).encode())
            return self._send(404, json.dumps({"ok": False, "error": "no such route"}).encode())

    return H


def tailscale_ip():
    try:
        out = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5).stdout.strip()
        return out.split("\n")[0] if out else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def serve(args, cfg):
    run_dir = C.resolve_run_dir(cfg, args, "plan.json")
    host = args.host or cfg["review"]["host"]
    port = int(args.port or cfg["review"]["port"])
    pid_path = os.path.join(run_dir, "review.pid")
    if args.background:
        old = C.read_json(pid_path, {})
        if old.get("pid") and C.pid_alive(old["pid"]):
            print(f"URL={old.get('url')}")
            print(f"already running (pid {old['pid']}); use 'stop' first to change host or port")
            return 0
        argv = [sys.executable, os.path.abspath(__file__), "serve", "--run-dir", run_dir, "--host", host, "--port", str(port)]
        if args.config:
            argv += ["--config", C.expand(args.config)]
        pid = C.detach(argv, os.path.join(run_dir, "review.log"))
        url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/"
        C.write_json(pid_path, {"pid": pid, "url": url, "host": host, "port": port, "run_dir": run_dir})
        print(f"URL={url}")
        ts = tailscale_ip()
        if host == "0.0.0.0" and ts:
            print(f"PHONE_URL=http://{ts}:{port}/")
        print(f"PID={pid}")
        print(f"DECISIONS={os.path.join(run_dir, 'decisions.json')}")
        return 0
    state = State(run_dir, cfg)
    try:
        httpd = ThreadingHTTPServer((host, port), make_handler(state))
    except OSError as err:
        print(f"ERROR: cannot bind {host}:{port}: {err}", file=sys.stderr)
        return 1
    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/"
    C.write_json(pid_path, {"pid": os.getpid(), "url": url, "host": host, "port": port, "run_dir": run_dir})
    print(f"URL={url}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def find_pid(cfg, args):
    runs = [C.expand(args.run_dir)] if args.run_dir else C.list_runs(cfg, "review.pid")
    for d in runs:
        info = C.read_json(os.path.join(d, "review.pid"), {})
        if info.get("pid"):
            return d, info
    return None, {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["serve", "status", "stop"])
    ap.add_argument("--config")
    ap.add_argument("--run-dir")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    ap.add_argument("--background", action="store_true")
    args = ap.parse_args(argv)
    cfg = C.load_config(args.config)
    if args.cmd == "serve":
        return serve(args, cfg)
    d, info = find_pid(cfg, args)
    if not info:
        print("no review server recorded")
        return 1 if args.cmd == "stop" else 0
    alive = C.pid_alive(info["pid"])
    if args.cmd == "status":
        print(f"URL={info.get('url')}")
        print(f"RUN_DIR={d}")
        print(f"ALIVE={'yes' if alive else 'no'} PID={info['pid']}")
        dec = C.read_json(os.path.join(d, "decisions.json"), {}) or {}
        print(f"APPROVED={dec.get('approved_at') or 'no'}")
        return 0
    if alive:
        os.kill(info["pid"], signal.SIGTERM)
        print(f"stopped pid {info['pid']}")
    else:
        print(f"pid {info['pid']} was not running")
    C.write_json(os.path.join(d, "review.pid"), {"pid": None, "stopped_at": C.iso(C.now_local()), "url": info.get("url"), "run_dir": d})
    return 0


if __name__ == "__main__":
    sys.exit(main())
