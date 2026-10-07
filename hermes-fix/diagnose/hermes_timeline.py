#!/usr/bin/env python3
"""hermes_timeline.py: where did the time go in a Hermes session? Read-only.

Copies ~/.hermes/state.db (plus -wal/-shm) to a temp dir, opens the copy
read-only, and reconstructs one session's timeline: every model call and tool
call with its duration, then a verdict on whether the run was model-bound or
tool-bound.

  python3 hermes_timeline.py                 # longest session in the last 2 days
  python3 hermes_timeline.py --list          # recent sessions, pick one
  python3 hermes_timeline.py --session ID    # one session
  python3 hermes_timeline.py --days 7 --top 15 --json

Standard library only. Never writes to the Hermes database.
"""
import argparse
import json
import os
import re
import shutil
import signal
import sqlite3
import sys
import tempfile
from collections import defaultdict
from datetime import datetime

HERMES_HOME = os.path.expanduser(os.environ.get("HERMES_HOME", "~/.hermes"))
try:  # let `| head` end the output quietly
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass
SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{6,}|Bearer\s+\S+|(?i:token|key|secret|password)['\"]?\s*[:=]\s*['\"]?\S+)")


def redact(text, limit=90):
    text = SECRET.sub("[redacted]", str(text or ""))
    text = " ".join(text.split())
    return text[:limit] + ("..." if len(text) > limit else "")


def open_readonly_copy(db_path):
    tmp = tempfile.mkdtemp(prefix="hermes_timeline_")
    base = os.path.join(tmp, "state.db")
    shutil.copy2(db_path, base)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(db_path + suffix):
            shutil.copy2(db_path + suffix, base + suffix)
    conn = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn, tmp


def columns_of(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def fmt_ts(ts):
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(ts)


def fmt_dur(seconds):
    seconds = max(0.0, float(seconds or 0))
    if seconds < 60:
        return f"{seconds:5.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


def list_sessions(conn, days, limit=25):
    scols = columns_of(conn, "sessions")
    wanted = ["id", "source", "model", "started_at", "ended_at", "message_count", "tool_call_count",
              "api_call_count", "input_tokens", "output_tokens", "title", "chat_type"]
    select = ", ".join(c for c in wanted if c in scols)
    spans = {r["session_id"]: r for r in conn.execute(
        "SELECT session_id, MIN(timestamp) AS first_ts, MAX(timestamp) AS last_ts, COUNT(*) AS n FROM messages GROUP BY session_id")}
    rows = []
    cutoff = datetime.now().timestamp() - days * 86400
    for s in conn.execute(f"SELECT {select} FROM sessions ORDER BY started_at DESC LIMIT 400"):
        s = dict(s)
        span = spans.get(s["id"])
        start = s.get("started_at") or (span["first_ts"] if span else None)
        end = span["last_ts"] if span else s.get("ended_at")
        if start is None or (days and start < cutoff):
            continue
        s["duration"] = (end - start) if (end and start) else 0.0
        s["n_messages"] = span["n"] if span else s.get("message_count", 0)
        rows.append(s)
        if len(rows) >= limit:
            break
    return rows


def session_timeline(conn, session_id):
    mcols = columns_of(conn, "messages")
    wanted = ["id", "role", "tool_name", "tool_calls", "timestamp", "token_count", "finish_reason", "compacted", "content"]
    select = ", ".join(c for c in wanted if c in mcols)
    msgs = [dict(r) for r in conn.execute(
        f"SELECT {select} FROM messages WHERE session_id = ? ORDER BY timestamp, id", (session_id,))]
    steps = []
    prev_ts = None
    pending_calls = {}
    for m in msgs:
        ts = m.get("timestamp")
        gap = (ts - prev_ts) if (prev_ts is not None and ts is not None) else 0.0
        role = m.get("role") or "?"
        calls = []
        if m.get("tool_calls"):
            try:
                raw = json.loads(m["tool_calls"])
                for c in raw if isinstance(raw, list) else []:
                    fn = c.get("function", c) if isinstance(c, dict) else {}
                    name = fn.get("name") or c.get("name") or "?"
                    args = fn.get("arguments") or c.get("arguments") or c.get("input") or ""
                    calls.append((name, redact(args, 70)))
                    if c.get("id"):
                        pending_calls[c["id"]] = name
            except (ValueError, TypeError, AttributeError):
                calls.append(("?", redact(m["tool_calls"], 70)))
        if role == "assistant":
            phase = "model"
            label = "model chose: " + "; ".join(f"{n}({a})" for n, a in calls) if calls else "final text: " + redact(m.get("content"), 70)
        elif role == "tool":
            name = m.get("tool_name") or "tool"
            phase = f"tool:{name}"
            label = f"{name} result: " + redact(m.get("content"), 60)
        elif role == "user":
            phase = "user"
            label = "user: " + redact(m.get("content"), 70)
        else:
            phase = role
            label = f"{role}: " + redact(m.get("content"), 70)
        steps.append({"ts": ts, "gap": gap, "phase": phase, "role": role, "label": label,
                      "calls": calls, "token_count": m.get("token_count"), "compacted": m.get("compacted"),
                      "finish_reason": m.get("finish_reason")})
        if ts is not None:
            prev_ts = ts
    return steps


def summarize(steps):
    by_phase = defaultdict(float)
    by_tool = defaultdict(lambda: {"n": 0, "secs": 0.0, "max": 0.0})
    iterations = 0
    finals = 0
    repeated = 0
    seen_calls = defaultdict(int)
    compactions = 0
    for s in steps:
        by_phase[s["phase"]] += s["gap"]
        if s["phase"].startswith("tool:"):
            t = by_tool[s["phase"][5:]]
            t["n"] += 1
            t["secs"] += s["gap"]
            t["max"] = max(t["max"], s["gap"])
        if s["role"] == "assistant":
            if s["calls"]:
                iterations += 1
                for name, args in s["calls"]:
                    seen_calls[(name, args)] += 1
            else:
                finals += 1
        if s.get("compacted"):
            compactions += 1
    repeated = sum(n - 1 for n in seen_calls.values() if n > 1)
    model_secs = by_phase.get("model", 0.0)
    tool_secs = sum(v for k, v in by_phase.items() if k.startswith("tool:"))
    user_secs = by_phase.get("user", 0.0)
    total = sum(by_phase.values())
    active = max(total - user_secs, 0.0)
    model_calls = sum(1 for s in steps if s["role"] == "assistant")
    tokens = [s["token_count"] for s in steps if s.get("token_count")]
    return {
        "total_secs": total, "active_secs": active, "model_secs": model_secs, "tool_secs": tool_secs,
        "user_wait_secs": user_secs, "iterations": iterations, "model_calls": model_calls, "finals": finals,
        "repeated_identical_calls": repeated, "compactions": compactions,
        "avg_model_secs": (model_secs / model_calls) if model_calls else 0.0,
        "by_tool": {k: dict(v) for k, v in by_tool.items()},
        "token_first": tokens[0] if tokens else None, "token_max": max(tokens) if tokens else None,
    }


def verdict(summary):
    active = summary["active_secs"] or 1.0
    model_pct = 100.0 * summary["model_secs"] / active
    tool_pct = 100.0 * summary["tool_secs"] / active
    lines = []
    if model_pct >= 55:
        lines.append(f"Model-bound: {model_pct:.0f}% of active time was waiting for the model "
                     f"(avg {fmt_dur(summary['avg_model_secs']).strip()} per call). Switch to a faster model or lower reasoning effort.")
    elif tool_pct >= 55:
        top = max(summary["by_tool"].items(), key=lambda kv: kv[1]["secs"], default=(None, None))
        lines.append(f"Tool-bound: {tool_pct:.0f}% of active time was inside tools; the biggest was "
                     f"{top[0]} ({fmt_dur(top[1]['secs']).strip()} over {top[1]['n']} calls). "
                     f"Replace the exploration with a script and lower terminal.timeout.")
    else:
        lines.append(f"Mixed: model {model_pct:.0f}%, tools {tool_pct:.0f}%. Both the model and the task shape need fixing.")
    if summary["repeated_identical_calls"]:
        lines.append(f"{summary['repeated_identical_calls']} tool call(s) repeated with identical arguments; the loop guard should hard-stop these.")
    if summary["iterations"] >= 30:
        lines.append(f"{summary['iterations']} tool-calling iterations for one request is exploration, not execution; a skill with a fixed script cuts this to a handful.")
    if summary["token_max"] and summary["token_first"] and summary["token_max"] > 4 * max(summary["token_first"], 1):
        lines.append(f"Context grew from ~{summary['token_first']} to ~{summary['token_max']} tokens; large tool outputs slow every later call.")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(HERMES_HOME, "state.db"))
    ap.add_argument("--session", help="session id (prefix is enough)")
    ap.add_argument("--list", action="store_true", help="list recent sessions and exit")
    ap.add_argument("--days", type=float, default=2.0)
    ap.add_argument("--top", type=int, default=12, help="slowest steps to show")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = ap.parse_args(argv)

    db_path = os.path.expanduser(args.db)
    if not os.path.exists(db_path):
        print(f"no Hermes database at {db_path}", file=sys.stderr)
        return 1
    conn, tmp = open_readonly_copy(db_path)
    try:
        sessions = list_sessions(conn, args.days)
        if args.list or not sessions and not args.session:
            print(f"Recent sessions (last {args.days:g} days):")
            for s in sessions:
                print(f"- {s['id'][:12]}  {fmt_ts(s.get('started_at'))}  {fmt_dur(s['duration']).strip():>8}  "
                      f"{s.get('source') or '?':<12} {s.get('model') or '?':<28} msgs={s['n_messages']}  "
                      f"tools={s.get('tool_call_count') or 0}  {redact(s.get('title'), 50)}")
            if not sessions:
                print("(none)")
            return 0
        if args.session:
            match = [s for s in list_sessions(conn, 0, limit=400) if s["id"].startswith(args.session)]
            if not match:
                print(f"no session starting with {args.session}", file=sys.stderr)
                return 1
            target = match[0]
        else:
            target = max(sessions, key=lambda s: s["duration"])
        steps = session_timeline(conn, target["id"])
        summary = summarize(steps)
        slow = sorted((s for s in steps if s["phase"] != "user"), key=lambda s: s["gap"], reverse=True)[:args.top]

        if args.json:
            json.dump({"session": {k: v for k, v in target.items()}, "summary": summary,
                       "slowest": slow, "steps": steps}, sys.stdout, default=str, indent=1)
            return 0

        print(f"# Hermes session timeline: {target['id']}")
        print(f"- started {fmt_ts(target.get('started_at'))}, source {target.get('source') or '?'}, "
              f"model {target.get('model') or '?'}, title: {redact(target.get('title'), 60)}")
        print(f"- elapsed {fmt_dur(summary['total_secs']).strip()} (active {fmt_dur(summary['active_secs']).strip()}, "
              f"waiting for the user {fmt_dur(summary['user_wait_secs']).strip()})")
        print(f"- model: {summary['model_calls']} calls, {fmt_dur(summary['model_secs']).strip()} total, "
              f"avg {fmt_dur(summary['avg_model_secs']).strip()} per call")
        print(f"- tools: {fmt_dur(summary['tool_secs']).strip()} total; iterations with tool calls: {summary['iterations']}; "
              f"final answers: {summary['finals']}; compactions: {summary['compactions']}")
        if summary["by_tool"]:
            print("- per tool:")
            for name, t in sorted(summary["by_tool"].items(), key=lambda kv: kv[1]["secs"], reverse=True):
                print(f"  - {name}: {t['n']} calls, {fmt_dur(t['secs']).strip()} total, slowest {fmt_dur(t['max']).strip()}")
        if summary["token_max"]:
            print(f"- context size (token_count): first ~{summary['token_first']}, max ~{summary['token_max']}")
        print()
        print("## Verdict")
        for line in verdict(summary):
            print(f"- {line}")
        print()
        print(f"## Slowest {len(slow)} steps")
        print("| when | took | phase | what |")
        print("|---|---|---|---|")
        for s in slow:
            print(f"| {fmt_ts(s['ts'])} | {fmt_dur(s['gap']).strip()} | {s['phase']} | {s['label'].replace('|', '/')} |")
        print()
        print("## Full timeline")
        for s in steps:
            print(f"{fmt_ts(s['ts'])}  {fmt_dur(s['gap'])}  {s['phase']:<22} {s['label']}")
        return 0
    finally:
        conn.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
