#!/usr/bin/env python3
"""Shared helpers for the photo-tidy skill: config, run folders, status files,
JSON helpers, background launch and polling.

Nothing in this skill deletes a photo. The only removals anywhere are in
pt_undo.py, which takes back the albums and copies that pt_apply.py made.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.normpath(os.path.join(HERE, ".."))
DEFAULT_CONFIG = os.path.join(SKILL_DIR, "config.json")
VENV_DIR = os.environ.get("PT_VENV") or os.path.join(SKILL_DIR, ".venv")
VENV_PY = os.path.join(VENV_DIR, "bin", "python3")

PHOTO_EXT = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".gif", ".tif", ".tiff", ".webp", ".dng", ".bmp"}
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".avi", ".3gp", ".mkv"}

DEFAULTS = {
    "source": {
        "mode": "photos",
        "photos_library": "",
        "folder": "~/Pictures/Phone Import",
        "include_videos": True,
        "include_hidden": False,
        "include_shared": False,
    },
    "run_root": "~/.hermes/workspaces/photo-tidy/runs",
    "thumb_px": 256,
    "workers": 6,
    "events": {
        "gap_hours": 8,
        "location_jump_km": 60,
        "min_event_photos": 3,
        "small_event_bucket": "month",
    },
    "junk": {
        "screenshots": True,
        "screenshot_min_age_days": 30,
        "screen_recordings": True,
        "labels": ["document", "receipt", "whiteboard", "qr code", "barcode", "business card", "text document", "invoice"],
        "min_px": 400,
        "min_bytes": 40000,
        "blur_threshold": 18.0,
        "blur_percentile": 5,
        "blur_cap": 100.0,
        "dark_mean": 22,
        "bright_mean": 236,
        "flat_std": 14,
        "failure_score": 0.85,
        "burst_extras": True,
    },
    "duplicates": {
        "phash_max_distance": 8,
        "dhash_max_distance": 12,
        "time_window_hours": 48,
        "neighbor_window": 60,
        "use_photos_fingerprint": True,
    },
    "places": {"use_photos_places": True, "offline_geocoder": True},
    "naming": {
        "enabled": True,
        "ollama_url": "http://127.0.0.1:11434",
        "model": "qwen3.5:4b",
        "timeout_seconds": 90,
        "max_events": 1500,
        "home_label": "Home",
    },
    "embeddings": {
        "enabled": False,
        "model": "embeddinggemma-2",
        "min_cosine": 0.965,
        "candidate_phash_distance": 18,
        "timeout_seconds": 60,
    },
    "apply": {
        "photos_folder": "Hermes Tidy",
        "events_folder": "Events",
        "junk_album": "Review - Junk",
        "dup_album": "Review - Duplicates",
        "export_dir": "",
        "batch_size": 150,
    },
    "review": {"host": "127.0.0.1", "port": 8765},
    "watch": {"min_new": 1, "compare_prior_runs": 3},
    "searches": [],
}


# ----------------------------------------------------------------------------- environment

def ensure_venv():
    """Re-run the calling script under the skill's own virtualenv when the
    current interpreter is some other python3. Hermes calls scripts with
    whatever python3 is on PATH; the libraries live in .venv."""
    if os.environ.get("PT_NO_VENV") or os.environ.get("PT_VENV_EXEC"):
        return
    if not os.path.exists(VENV_PY):
        return
    if os.path.realpath(sys.prefix) == os.path.realpath(VENV_DIR):
        return
    env = dict(os.environ, PT_VENV_EXEC="1")
    os.execve(VENV_PY, [VENV_PY] + sys.argv, env)


def expand(p):
    return os.path.abspath(os.path.expanduser(str(p))) if p else ""


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path=None):
    path = expand(path) if path else DEFAULT_CONFIG
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    cfg = deep_merge(DEFAULTS, data)
    cfg["_path"] = path
    cfg["run_root"] = expand(cfg["run_root"])
    cfg["source"]["folder"] = expand(cfg["source"]["folder"])
    if cfg["source"]["photos_library"]:
        cfg["source"]["photos_library"] = expand(cfg["source"]["photos_library"])
    if cfg["apply"].get("export_dir"):
        cfg["apply"]["export_dir"] = expand(cfg["apply"]["export_dir"])
    return cfg


def now_local():
    return datetime.now().astimezone()


def iso(dt):
    return dt.isoformat(timespec="seconds") if dt else None


def parse_iso(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ----------------------------------------------------------------------------- runs

def run_root(cfg):
    root = cfg["run_root"]
    os.makedirs(root, exist_ok=True)
    return root


def thumbs_dir(cfg):
    d = os.path.join(run_root(cfg), "thumbs")
    os.makedirs(d, exist_ok=True)
    return d


def new_run_dir(cfg, tag=""):
    stamp = now_local().strftime("%Y-%m-%d_%H%M%S")
    name = f"{stamp}_{tag}" if tag else stamp
    d = os.path.join(run_root(cfg), name)
    n = 2
    while os.path.exists(d):
        d = os.path.join(run_root(cfg), f"{name}_{n}")
        n += 1
    os.makedirs(d)
    return d


def list_runs(cfg, require=None):
    root = run_root(cfg)
    out = []
    for name in sorted(os.listdir(root), reverse=True):
        d = os.path.join(root, name)
        if not os.path.isdir(d) or name == "thumbs":
            continue
        if require and not os.path.exists(os.path.join(d, require)):
            continue
        out.append(d)
    return out


def latest_run_dir(cfg, require="inventory.jsonl"):
    runs = list_runs(cfg, require)
    return runs[0] if runs else None


def resolve_run_dir(cfg, args, require="inventory.jsonl"):
    """--run-dir wins; otherwise the newest run that has `require`."""
    if getattr(args, "run_dir", None):
        d = expand(args.run_dir)
        if not os.path.isdir(d):
            raise SystemExit(f"ERROR: run dir not found: {d}")
        return d
    d = latest_run_dir(cfg, require)
    if not d:
        raise SystemExit(f"ERROR: no run under {cfg['run_root']} has {require} yet")
    return d


# ----------------------------------------------------------------------------- files

def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path, obj, indent=1):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    os.replace(tmp, path)


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def safe_name(s, limit=80):
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", str(s or "")).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:limit].rstrip(" .") or "Untitled"


# ----------------------------------------------------------------------------- maths

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def hamming_hex(a, b):
    if not a or not b or len(a) != len(b):
        return 99
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# ----------------------------------------------------------------------------- status and ledger

class Ledger:
    def __init__(self):
        self.rows = []

    def add(self, source, status, detail=""):
        self.rows.append({"source": source, "status": status, "detail": detail, "at": iso(now_local())})

    def lines(self):
        return [f"{r['source']} | {r['status']} | {r['detail']}" for r in self.rows]


class Status:
    """A small JSON file other calls can poll. pt_*.py --wait reads it."""

    def __init__(self, path, phase="start"):
        self.path = path
        self.data = {"state": "running", "phase": phase, "done": 0, "total": 0, "msg": "",
                     "started": iso(now_local()), "updated": iso(now_local()), "pid": os.getpid()}
        self._last = 0.0
        self.write(force=True)

    def update(self, phase=None, done=None, total=None, msg=None, force=False):
        if phase is not None:
            self.data["phase"] = phase
        if done is not None:
            self.data["done"] = done
        if total is not None:
            self.data["total"] = total
        if msg is not None:
            self.data["msg"] = msg
        self.write(force=force)

    def finish(self, ok=True, msg="", result=None):
        self.data["state"] = "done" if ok else "error"
        self.data["msg"] = msg
        if result is not None:
            self.data["result"] = result
        self.write(force=True)

    def write(self, force=False):
        now = time.monotonic()
        if not force and now - self._last < 1.0:
            return
        self._last = now
        self.data["updated"] = iso(now_local())
        write_json(self.path, self.data)

    @staticmethod
    def read(path):
        return read_json(path, {}) or {}


def detach(argv, log_path):
    """Start argv in its own session so it outlives the caller's terminal."""
    env = dict(os.environ)
    env.pop("PT_VENV_EXEC", None)
    with open(log_path, "ab") as log:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             start_new_session=True, cwd=SKILL_DIR, env=env)
    return p.pid


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def wait_status(path, seconds, label="job"):
    """Poll a status file for up to `seconds`. Prints one line per change.
    Returns (data, exit_code): 0 done, 1 error, 3 still running."""
    end = time.monotonic() + max(1, seconds)
    last = ""
    while True:
        data = Status.read(path)
        line = f"{label}: {data.get('state','?')} {data.get('phase','')} {data.get('done',0)}/{data.get('total',0)} {data.get('msg','')}".strip()
        if line != last:
            print(line, flush=True)
            last = line
        state = data.get("state")
        if state == "done":
            return data, 0
        if state == "error":
            return data, 1
        if state == "running" and data.get("pid") and not pid_alive(data["pid"]):
            upd = parse_iso(data.get("updated"))
            if upd and (now_local() - upd).total_seconds() > 20:
                print(f"{label}: process {data['pid']} is gone and the status file stopped updating; treat as failed", flush=True)
                return data, 1
        if time.monotonic() >= end:
            return data, 3
        time.sleep(2)


def background_launch(script, run_dir, extra_args, status_name, log_name):
    """Relaunch `script` detached with --run-dir, print the handles, exit 0."""
    status_path = os.path.join(run_dir, status_name)
    log_path = os.path.join(run_dir, log_name)
    Status(status_path, phase="queued")
    argv = [sys.executable, script, "--run-dir", run_dir] + absolutize(list(extra_args))
    pid = detach(argv, log_path)
    print(f"RUN_DIR={run_dir}")
    print(f"STATUS={status_path}")
    print(f"LOG={log_path}")
    print(f"PID={pid}")
    print(f"NEXT=python3 {script} --wait {run_dir} --seconds 110")
    return 0


def absolutize(args, flags=("--config", "--export", "--ids-file", "--wait")):
    """A detached process starts in the skill directory, so path arguments
    must not stay relative to wherever the caller was."""
    out = list(args)
    for i, a in enumerate(out[:-1]):
        if a in flags:
            out[i + 1] = expand(out[i + 1])
    return out


def strip_background(argv):
    return [a for a in argv if a != "--background"]
