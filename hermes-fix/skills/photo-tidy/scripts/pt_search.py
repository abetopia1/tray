#!/usr/bin/env python3
"""Run real searches against a run and report whether they find anything.
Use it before applying (--fields raw: only what Photos already knew) and
after planning (--fields all: plus the event names and places the plan
added) to see whether the organisation actually helps.

  python3 pt_search.py [--run-dir DIR]                 # the searches in config.json
  python3 pt_search.py -q "sharm honeymoon" -q "tundra"
  python3 pt_search.py --fields raw                    # dates, labels, people, places only

A query matches when every word appears in an event's text (name, place,
labels, people, month, year) or a photo's text. Exit 0 when every query
with min_events met it, 1 otherwise.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").lower())


def event_text(ev, fields):
    parts = []
    if fields != "raw":
        parts += [ev.get("name", ""), ev.get("title", "")]
    pl = ev.get("place") or {}
    parts += [pl.get("city", ""), pl.get("state", ""), pl.get("country", "")]
    parts += ev.get("labels_top", [])
    parts += ev.get("persons_top", [])
    if ev.get("start"):
        d = datetime.fromisoformat(ev["start"])
        parts += [str(d.year), MONTHS[d.month - 1], d.strftime("%B %Y"), d.strftime("%Y-%m")]
    return norm(" | ".join(str(p) for p in parts if p))


def photo_text(r):
    pl = r.get("place") or {}
    parts = [r.get("name", ""), r.get("title", ""), pl.get("city", ""), pl.get("state", ""), pl.get("country", ""), pl.get("name", "")]
    parts += r.get("labels") or []
    parts += r.get("persons") or []
    parts += r.get("albums") or []
    parts += r.get("keywords") or []
    if r.get("date"):
        d = C.parse_iso(r["date"])
        if d:
            parts += [str(d.year), MONTHS[d.month - 1], d.strftime("%Y-%m")]
    if r.get("screenshot"):
        parts.append("screenshot")
    if r.get("kind") == "video":
        parts.append("video")
    return norm(" | ".join(str(p) for p in parts if p))


def terms(q):
    return [t.strip('"') for t in re.findall(r'"[^"]+"|\S+', q.lower())]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--run-dir")
    ap.add_argument("--fields", choices=["raw", "all"], default="all")
    ap.add_argument("-q", "--query", action="append", default=[])
    args = ap.parse_args(argv)
    cfg = C.load_config(args.config)
    run_dir = C.resolve_run_dir(cfg, args, "inventory.jsonl")
    plan = C.read_json(os.path.join(run_dir, "plan.json"), {}) or {}
    events = plan.get("events", [])
    recs = C.read_jsonl(os.path.join(run_dir, "inventory.jsonl"))
    queries = [{"q": q, "min_events": 1} for q in args.query] or list(cfg.get("searches") or [])
    if not queries:
        print("no searches: pass -q or fill config.json searches")
        return 5
    ev_docs = [(ev, event_text(ev, args.fields)) for ev in events]
    ph_docs = [(r, photo_text(r)) for r in recs]
    print(f"RUN_DIR={run_dir} fields={args.fields} events={len(events)} photos={len(recs)}")
    print(f"{'query':32} {'events':>6} {'photos':>7}  result")
    fails = 0
    for q in queries:
        ts = terms(q["q"])
        ev_hits = [ev for ev, doc in ev_docs if all(t in doc for t in ts)]
        ph_hits = [r for r, doc in ph_docs if all(t in doc for t in ts)]
        need = int(q.get("min_events", 1))
        ok = len(ev_hits) >= need
        if not ok:
            fails += 1
        sample = "; ".join((ev.get("title") or ev.get("name") or "")[:40] for ev in ev_hits[:2])
        print(f"{q['q'][:32]:32} {len(ev_hits):>6} {len(ph_hits):>7}  {'PASS' if ok else 'MISS'} {sample}")
    print(f"RESULT {len(queries) - fails}/{len(queries)} searches found an event")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
