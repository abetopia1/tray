#!/usr/bin/env python3
"""Find photos that no earlier run has seen and, with --run, scan and plan
only those into a new run so they can be reviewed. Meant for a Hermes cron
job. Reads the library or folder; writes only under run_root.

  python3 pt_watch.py                 # count new items, print a sample
  python3 pt_watch.py --run           # new items >= watch.min_new: scan + plan them (foreground)
  python3 pt_watch.py --run --background ; python3 pt_watch.py --wait RUN_DIR

Exit 0 ok (NEW=0 included), 1 error, 3 still running (--wait).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

C.ensure_venv()


def known_ids(cfg):
    ids = set()
    runs = 0
    for d in C.list_runs(cfg, "inventory.jsonl"):
        runs += 1
        with open(os.path.join(d, "inventory.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                i = line.find('"id": "')
                if i >= 0:
                    j = line.find('"', i + 7)
                    ids.add(line[i + 7:j])
    return ids, runs


def current_items(cfg):
    mode = cfg["source"]["mode"]
    if mode == "photos":
        from osxphotos import PhotosDB
        lib = cfg["source"].get("photos_library") or None
        db = PhotosDB(dbfile=lib) if lib else PhotosDB()
        out = []
        for p in db.photos(images=True, movies=bool(cfg["source"].get("include_videos", True))):
            if p.intrash or (p.hidden and not cfg["source"].get("include_hidden")) or (p.shared and not cfg["source"].get("include_shared")):
                continue
            out.append((p.uuid, p.original_filename, C.iso(p.date_added)))
        return out
    import pt_scan
    return [(r["id"], r["rel"], r["date_added"]) for r in pt_scan.folder_records(cfg)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--run-dir")
    ap.add_argument("--background", action="store_true")
    ap.add_argument("--wait", metavar="RUN_DIR")
    ap.add_argument("--seconds", type=int, default=110)
    args = ap.parse_args(argv)
    if args.wait:
        d = C.expand(args.wait)
        data, rc = C.wait_status(os.path.join(d, "watch.status.json"), args.seconds, "watch")
        if rc == 0:
            for line in (data.get("result") or {}).get("tail", []):
                print(line)
        elif rc == 3:
            print(f"NEXT=python3 {os.path.abspath(__file__)} --wait {d} --seconds {args.seconds}")
        return rc
    cfg = C.load_config(args.config)
    if args.background:
        run_dir = args.run_dir or C.new_run_dir(cfg, "new")
        extra = [a for a in (argv if argv is not None else sys.argv[1:]) if a != "--background"]
        if "--run-dir" in extra:
            i = extra.index("--run-dir")
            del extra[i:i + 2]
        return C.background_launch(os.path.abspath(__file__), run_dir, extra, "watch.status.json", "watch.log")
    status = C.Status(os.path.join(args.run_dir, "watch.status.json"), phase="listing") if args.run_dir else None
    known, runs = known_ids(cfg)
    try:
        items = current_items(cfg)
    except Exception as err:
        if status:
            status.finish(False, f"{type(err).__name__}: {err}")
        print(f"ERROR: {type(err).__name__}: {err}", file=sys.stderr)
        return 1
    new = [it for it in items if it[0] not in known]
    new.sort(key=lambda it: it[2] or "", reverse=True)
    print(f"NEW={len(new)} known={len(known)} runs={runs} total={len(items)}")
    for uid, name, added in new[:8]:
        print(f"  {name} added {added}")
    tail = [f"NEW={len(new)}"]
    if not args.run or len(new) < int(cfg["watch"].get("min_new", 1)) or not new:
        if status:
            status.finish(True, f"{len(new)} new, nothing to run", result={"new": len(new), "tail": tail})
        if new and not args.run:
            print("NEXT=add --run to scan and plan them")
        return 0
    run_dir = args.run_dir or C.new_run_dir(cfg, "new")
    ids_path = os.path.join(run_dir, "new_ids.txt")
    with open(ids_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(it[0] if cfg["source"]["mode"] == "photos" else it[1] for it in new) + "\n")
    base = [sys.executable]
    cfgarg = ["--config", args.config] if args.config else []
    if status:
        status.update(phase="scan", total=len(new), force=True)
    r1 = subprocess.run(base + [os.path.join(C.HERE, "pt_scan.py"), "--run-dir", run_dir, "--ids-file", ids_path] + cfgarg,
                        capture_output=True, text=True)
    print(r1.stdout.strip())
    if r1.returncode != 0:
        print(r1.stderr.strip(), file=sys.stderr)
        if status:
            status.finish(False, "scan failed")
        return 1
    if status:
        status.update(phase="plan", force=True)
    r2 = subprocess.run(base + [os.path.join(C.HERE, "pt_plan.py"), "--run-dir", run_dir, "--compare-prior"] + (["--no-llm"] if args.no_llm else []) + cfgarg,
                        capture_output=True, text=True)
    print(r2.stdout.strip())
    if r2.returncode != 0:
        print(r2.stderr.strip(), file=sys.stderr)
        if status:
            status.finish(False, "plan failed")
        return 1
    tail = [l for l in r2.stdout.splitlines() if l.startswith(("SUMMARY", "SAMPLE_EVENTS", "NEXT="))]
    tail.insert(0, f"NEW={len(new)} RUN_DIR={run_dir}")
    if status:
        status.finish(True, f"{len(new)} new items planned", result={"new": len(new), "run_dir": run_dir, "tail": tail})
    print(f"RUN_DIR={run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
