#!/usr/bin/env python3
"""hermes_timeline.py: where did the time go in a Hermes run? Read-only.

Copies ~/.hermes/state.db (plus -wal/-shm) to a temp dir, opens the copy
read-only, and reconstructs one run: every model call and tool call with its
duration, then a verdict on whether the run was model-bound or tool-bound.

Gateway chats live for weeks, so the unit of analysis is a turn (one user
message and everything Hermes did until the next one), not the whole session.

  python3 hermes_timeline.py                 # slowest turn in the last 2 days
  python3 hermes_timeline.py --list          # recent sessions and their slowest turn
  python3 hermes_timeline.py --session ID    # slowest turn of one session (prefix is enough)
  python3 hermes_timeline.py --whole-session # aggregate the whole session instead of one turn
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
COMPACTION_PREFIX = re.compile(r"^\s*\[?\s*context\s+compact", re.I)


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


# ----------------------------------------------------------------------------- sessions

def list_sessions(conn, days, limit=25):
    scols = columns_of(conn, "sessions")
    wanted = ["id", "source", "model", "started_at", "ended_at", "message_count", "tool_call_count",
              "api_call_count", "input_tokens", "output_tokens", "title", "chat_type"]
    select = ", ".join(c for c in wanted if c in scols)
    spans = {r["session_id"]: r for r in conn.execute(
        "SELECT session_id, MIN(timestamp) AS first_ts, MAX(timestamp) AS last_ts, COUNT(*) AS n FROM messages GROUP BY session_id")}
    rows = []
    cutoff = datetime.now().timestamp() - days * 86400
    for s in conn.execute(f"SELECT {select} FROM sessions"):
        s = dict(s)
        span = spans.get(s["id"])
        start = s.get("started_at") or (span["first_ts"] if span else None)
        end = span["last_ts"] if span else s.get("ended_at")
        last_active = end or start
        # Gateway sessions live for weeks, so the window is judged on last activity.
        if start is None or (days and last_active < cutoff):
            continue
        s["last_active"] = last_active
        s["duration"] = (end - start) if (end and start) else 0.0
        s["n_messages"] = span["n"] if span else s.get("message_count", 0)
        rows.append(s)
    rows.sort(key=lambda s: s["last_active"], reverse=True)
    return rows[:limit] if limit else rows


# ----------------------------------------------------------------------------- messages

def session_steps(conn, session_id):
    mcols = columns_of(conn, "messages")
    wanted = ["id", "role", "tool_name", "tool_calls", "tool_call_id", "timestamp", "token_count",
              "finish_reason", "compacted", "active", "observed", "message_uid", "content"]
    select = ", ".join(c for c in wanted if c in mcols)
    msgs = [dict(r) for r in conn.execute(
        f"SELECT {select} FROM messages WHERE session_id = ? ORDER BY timestamp, id", (session_id,))]

    # In-place compaction archives the pre-compaction rows (active=0, compacted=1)
    # and re-inserts the kept tail as fresh rows with the same timestamps. The
    # archive is the real history, so keep it, drop rewound rows (active=0 and
    # compacted=0), and dedupe the re-inserted copies.
    live = []
    seen = set()
    for m in msgs:
        if "active" in mcols and "compacted" in mcols:
            if not m.get("active") and not m.get("compacted"):
                continue
        uid = m.get("message_uid") or (m.get("role"), round(float(m.get("timestamp") or 0), 3),
                                       m.get("tool_call_id"), (m.get("content") or "")[:200])
        if uid in seen:
            continue
        seen.add(uid)
        live.append(m)

    steps = []
    prev_ts = None
    cum_chars = 0
    for m in live:
        ts = m.get("timestamp")
        gap = (ts - prev_ts) if (prev_ts is not None and ts is not None) else 0.0
        role = m.get("role") or "?"
        content = m.get("content") or ""
        calls = []
        if m.get("tool_calls"):
            try:
                raw = json.loads(m["tool_calls"])
                for c in raw if isinstance(raw, list) else []:
                    fn = c.get("function", c) if isinstance(c, dict) else {}
                    name = fn.get("name") or c.get("name") or "?"
                    args = fn.get("arguments") or c.get("arguments") or c.get("input") or ""
                    if not isinstance(args, str):
                        args = json.dumps(args, sort_keys=True)
                    calls.append((name, redact(args, 70)))
            except (ValueError, TypeError, AttributeError):
                calls.append(("?", redact(m["tool_calls"], 70)))
        is_compaction = bool(m.get("compacted")) and role == "user" and COMPACTION_PREFIX.search(content[:60])
        is_compaction = is_compaction or (role == "user" and COMPACTION_PREFIX.search(content[:60]) is not None)
        if is_compaction:
            phase = "compaction"
            label = "context compaction: summary written by the model"
        elif role == "assistant":
            phase = "model"
            label = "model chose: " + "; ".join(f"{n}({a})" for n, a in calls) if calls else "final text: " + redact(content, 70)
        elif role == "tool":
            name = m.get("tool_name") or "tool"
            phase = f"tool:{name}"
            label = f"{name} result ({len(content)} chars): " + redact(content, 60)
        elif role == "user":
            phase = "user"
            label = "user: " + redact(content, 70)
        else:
            phase = role
            label = f"{role}: " + redact(content, 70)
        ctx_est = m.get("token_count") or (cum_chars // 4 if cum_chars else None)
        cum_chars += len(content) + len(m.get("tool_calls") or "")
        steps.append({"ts": ts, "gap": gap, "phase": phase, "role": role, "label": label, "calls": calls,
                      "ctx_tokens": ctx_est if role == "assistant" else None,
                      "result_chars": len(content) if role == "tool" else 0,
                      "compacted": m.get("compacted"), "finish_reason": m.get("finish_reason")})
        if ts is not None:
            prev_ts = ts
    return steps


def split_turns(steps):
    """A turn starts at every real user message (compaction carriers do not count)."""
    turns = []
    current = []
    for s in steps:
        if s["phase"] == "user" and current:
            turns.append(current)
            current = []
        if not current:
            s = dict(s, gap=0.0)   # idle time before the user's message belongs to no turn
        current.append(s)
    if current:
        turns.append(current)
    return turns


# ----------------------------------------------------------------------------- analysis

def summarize(steps):
    by_phase = defaultdict(float)
    by_tool = defaultdict(lambda: {"n": 0, "secs": 0.0, "max": 0.0})
    iterations = finals = compactions = 0
    seen_calls = defaultdict(int)
    largest = {"chars": 0, "tool": None, "ts": None}
    for s in steps:
        by_phase[s["phase"]] += s["gap"]
        if s["phase"].startswith("tool:"):
            t = by_tool[s["phase"][5:]]
            t["n"] += 1
            t["secs"] += s["gap"]
            t["max"] = max(t["max"], s["gap"])
            if s["result_chars"] > largest["chars"]:
                largest = {"chars": s["result_chars"], "tool": s["phase"][5:], "ts": s["ts"]}
        if s["role"] == "assistant":
            if s["calls"]:
                iterations += 1
                for name, args in s["calls"]:
                    seen_calls[(name, args)] += 1
            else:
                finals += 1
        if s["phase"] == "compaction":
            compactions += 1
    repeated = sum(n - 1 for n in seen_calls.values() if n > 1)
    model_secs = by_phase.get("model", 0.0)
    tool_secs = sum(v for k, v in by_phase.items() if k.startswith("tool:"))
    compaction_secs = by_phase.get("compaction", 0.0)
    user_secs = by_phase.get("user", 0.0)
    total = sum(by_phase.values())
    active = max(total - user_secs, 0.0)
    model_calls = sum(1 for s in steps if s["role"] == "assistant")
    ctx = [s["ctx_tokens"] for s in steps if s.get("ctx_tokens")]
    return {
        "total_secs": total, "active_secs": active, "model_secs": model_secs, "tool_secs": tool_secs,
        "compaction_secs": compaction_secs, "user_wait_secs": user_secs, "iterations": iterations,
        "model_calls": model_calls, "finals": finals, "repeated_identical_calls": repeated,
        "compactions": compactions, "avg_model_secs": (model_secs / model_calls) if model_calls else 0.0,
        "by_tool": {k: dict(v) for k, v in by_tool.items()},
        "ctx_first": ctx[0] if ctx else None, "ctx_max": max(ctx) if ctx else None,
        "largest_tool_result": largest,
    }


def verdict(summary):
    active = summary["active_secs"] or 1.0
    model_pct = 100.0 * summary["model_secs"] / active
    tool_pct = 100.0 * summary["tool_secs"] / active
    comp_pct = 100.0 * summary["compaction_secs"] / active
    lines = []
    if model_pct >= 55:
        lines.append(f"Model-bound: {model_pct:.0f}% of active time was waiting for the model "
                     f"(avg {fmt_dur(summary['avg_model_secs']).strip()} per call). A faster model or lower reasoning effort is the lever.")
    elif tool_pct >= 55:
        top = max(summary["by_tool"].items(), key=lambda kv: kv[1]["secs"], default=(None, None))
        lines.append(f"Tool-bound: {tool_pct:.0f}% of active time was inside tools; the biggest was "
                     f"{top[0]} ({fmt_dur(top[1]['secs']).strip()} over {top[1]['n']} calls). "
                     f"A fixed script instead of exploration, and a lower terminal.timeout, are the levers.")
    else:
        lines.append(f"Mixed: model {model_pct:.0f}%, tools {tool_pct:.0f}%, compaction {comp_pct:.0f}%. "
                     "Both the model and the task shape need fixing.")
    if comp_pct >= 10:
        lines.append(f"Context compaction took {comp_pct:.0f}% of active time ({summary['compactions']} pass(es)); "
                     "route compression to a faster auxiliary model.")
    if summary["repeated_identical_calls"]:
        lines.append(f"{summary['repeated_identical_calls']} tool call(s) repeated with identical arguments; the loop guard should hard-stop these.")
    if summary["iterations"] >= 30:
        lines.append(f"{summary['iterations']} tool-calling iterations for one request is exploration, not execution; a skill with a fixed script cuts this to a handful.")
    if summary["ctx_max"] and summary["ctx_first"] and summary["ctx_max"] > 4 * max(summary["ctx_first"], 1):
        lines.append(f"Context grew from ~{summary['ctx_first']} to ~{summary['ctx_max']} tokens (estimated from stored "
                     "message sizes); large tool outputs slow every later call.")
    big = summary["largest_tool_result"]
    if big["chars"] >= 20000:
        lines.append(f"Largest tool result was {big['chars']} chars from {big['tool']}; tool_output.max_bytes caps this.")
    return lines


def pick_turn(conn, sessions, whole_session):
    """Return (session, steps, turn_index) for the slowest unit among the candidate sessions."""
    best = None
    for s in sessions:
        steps = session_steps(conn, s["id"])
        if not steps:
            continue
        units = [steps] if whole_session else split_turns(steps)
        for idx, unit in enumerate(units):
            active = summarize(unit)["active_secs"]
            if best is None or active > best[3]:
                best = (s, unit, idx, active)
    return best


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(HERMES_HOME, "state.db"))
    ap.add_argument("--session", help="session id (prefix is enough)")
    ap.add_argument("--list", action="store_true", help="list recent sessions and exit")
    ap.add_argument("--whole-session", action="store_true", help="aggregate the whole session instead of its slowest turn")
    ap.add_argument("--days", type=float, default=2.0, help="look at sessions active in the last N days")
    ap.add_argument("--top", type=int, default=12, help="slowest steps to show")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = ap.parse_args(argv)

    db_path = os.path.expanduser(args.db)
    if not os.path.exists(db_path):
        print(f"no Hermes database at {db_path}", file=sys.stderr)
        return 1
    conn, tmp = open_readonly_copy(db_path)
    try:
        if args.session:
            candidates = [s for s in list_sessions(conn, 0, limit=0) if s["id"].startswith(args.session)]
            if not candidates:
                print(f"no session starting with {args.session}", file=sys.stderr)
                return 1
        else:
            candidates = list_sessions(conn, args.days)

        if args.list or not candidates:
            print(f"Sessions active in the last {args.days:g} days (slowest turn in brackets):")
            for s in candidates:
                steps = session_steps(conn, s["id"])
                slowest = max((summarize(t)["active_secs"] for t in split_turns(steps)), default=0.0)
                print(f"- {s['id'][:12]}  last active {fmt_ts(s.get('last_active'))}  [{fmt_dur(slowest).strip():>7}]  "
                      f"{s.get('source') or '?':<12} {s.get('model') or '?':<26} msgs={s['n_messages']}  "
                      f"{redact(s.get('title'), 50)}")
            if not candidates:
                print("(none)")
            return 0

        picked = pick_turn(conn, candidates, args.whole_session)
        if not picked:
            print("no messages found for the candidate sessions", file=sys.stderr)
            return 1
        target, steps, turn_idx, _ = picked
        summary = summarize(steps)
        slow = sorted((s for s in steps if s["phase"] != "user"), key=lambda s: s["gap"], reverse=True)[:args.top]
        unit = "whole session" if args.whole_session else f"turn {turn_idx + 1}"

        if args.json:
            json.dump({"session": target, "unit": unit, "summary": summary, "slowest": slow, "steps": steps},
                      sys.stdout, default=str, indent=1)
            return 0

        first_user = next((s for s in steps if s["phase"] == "user"), None)
        print(f"# Hermes timeline: session {target['id']}, {unit}")
        print(f"- source {target.get('source') or '?'}, model {target.get('model') or '?'}, "
              f"session title: {redact(target.get('title'), 60)}")
        if first_user:
            print(f"- turn started {fmt_ts(first_user['ts'])} with: {first_user['label'][6:]}")
        print(f"- elapsed {fmt_dur(summary['total_secs']).strip()}, of which active {fmt_dur(summary['active_secs']).strip()}")
        print(f"- model: {summary['model_calls']} calls, {fmt_dur(summary['model_secs']).strip()} total, "
              f"avg {fmt_dur(summary['avg_model_secs']).strip()} per call")
        print(f"- tools: {fmt_dur(summary['tool_secs']).strip()} total; compaction: {fmt_dur(summary['compaction_secs']).strip()} "
              f"({summary['compactions']} pass(es)); iterations with tool calls: {summary['iterations']}; final answers: {summary['finals']}")
        if summary["by_tool"]:
            print("- per tool:")
            for name, t in sorted(summary["by_tool"].items(), key=lambda kv: kv[1]["secs"], reverse=True):
                print(f"  - {name}: {t['n']} calls, {fmt_dur(t['secs']).strip()} total, slowest {fmt_dur(t['max']).strip()}")
        if summary["ctx_max"]:
            print(f"- context size (estimated tokens): first ~{summary['ctx_first']}, max ~{summary['ctx_max']}")
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
