#!/usr/bin/env python3
"""Apply the approved decisions of a run. Photos mode creates albums inside a
"Hermes Tidy" folder in Photos and adds photos to them; the albums sync to
the iPhone through iCloud Photos. Folder mode moves files into event
folders. Both modes can also copy approved events to an export folder.
Every action is appended to apply.log.jsonl as it happens; pt_undo.py reads
that log. Nothing here deletes a photo.

  python3 pt_apply.py [--run-dir DIR]            # dry run: prints what would happen
  python3 pt_apply.py --run-dir DIR --yes        # apply
  python3 pt_apply.py --run-dir DIR --yes --export ~/Pictures/Organized
  python3 pt_apply.py --run-dir DIR --yes --no-albums --export DIR   # copies only

Exit 0 applied, 2 partial (see the log), 4 not approved or plan changed
since approval, 5 usage.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

C.ensure_venv()


def resolve(plan, dec, cfg):
    """Turn plan plus decisions into concrete buckets of ids."""
    junk = [j["id"] for j in plan["junk"] if dec.get("junk", {}).get(j["id"])]
    dup_others = []
    dup_groups = []
    for g in plan["dups"]:
        if not dec.get("dups", {}).get(g["gid"]):
            continue
        keep = dec.get("keep", {}).get(g["gid"]) or g["keep"]
        members = [g["keep"]] + list(g["others"])
        others = [m for m in members if m != keep]
        dup_groups.append({"gid": g["gid"], "keep": keep, "others": others})
        dup_others.extend(others)
    moved = set(junk) | set(dup_others)
    events = []
    last = None
    for e in plan["events"]:
        d = dec.get("events", {}).get(e["eid"], {})
        if d.get("include") is False:
            continue
        ids = [i for i in e["ids"] if i not in moved]
        name = C.safe_name(d.get("name") or e["name"], 60)
        start = e.get("start") or ""
        prefix = start[:10] if start else (e.get("month") or "undated")
        title = C.safe_name(f"{prefix} {name}", 90)
        if d.get("merge_prev") and last is not None and not e.get("bucket"):
            last["ids"].extend(ids)
            last["merged"].append(e["eid"])
            continue
        ev = {"eid": e["eid"], "title": title, "year": prefix[:4], "ids": ids, "merged": [], "bucket": e.get("bucket", False)}
        events.append(ev)
        last = ev
    events = [e for e in events if e["ids"]]
    return {"junk": junk, "dup_groups": dup_groups, "dup_others": dup_others, "events": events}


def placed_ids(run_dir):
    """Ids a finished apply of `run_dir` put into albums or folders, from its
    plan and decisions, so a later plan can leave them alone. Empty when the
    run was never applied or was undone."""
    log_path = os.path.join(run_dir, "apply.log.jsonl")
    if not os.path.exists(log_path):
        return set()
    if any(r.get("op") == "complete" for r in C.read_jsonl(os.path.join(run_dir, "undo.log.jsonl"))):
        return set()
    plan = C.read_json(os.path.join(run_dir, "plan.json"))
    dec = C.read_json(os.path.join(run_dir, "decisions.json"), {}) or {}
    if not plan:
        return set()
    res = resolve(plan, dec, {})
    out = set(res["junk"]) | set(res["dup_others"])
    for ev in res["events"]:
        out.update(ev["ids"])
    return out


def check_approval(run_dir, plan_path, dec):
    if not dec or not dec.get("approved_at"):
        return "decisions.json has no approval; open the review page, go through the four tabs and press Approve"
    if dec.get("plan_hash") != C.sha256_file(plan_path):
        return "plan.json changed after the approval; review and approve again"
    if dec.get("applied_at"):
        return f"this run was already applied at {dec['applied_at']}; undo it first or make a new run"
    return ""


def unique_path(path):
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{base} ({n}){ext}"
        n += 1
    return path


# ----------------------------------------------------------------------------- photos mode

def apply_photos(res, cfg, log, status):
    import pt_photos as P
    A = cfg["apply"]
    summary = {"albums": 0, "added": 0, "missing": 0, "failed": 0}
    top, created = P.ensure_folder(A["photos_folder"])
    log({"op": "folder", "chain": [top], "name": A["photos_folder"], "created": created})
    ev_folder, created = P.ensure_folder(A["events_folder"], (top,))
    log({"op": "folder", "chain": [top, ev_folder], "name": A["events_folder"], "created": created})
    stamp = C.now_local().strftime("%Y-%m-%d")

    def make_album(name, chain, ids, kind):
        existing = P.find_albums(name, chain)
        if existing:
            name = f"{name} ({len(existing) + 1})"
        aid = P.create_album(name, chain)
        log({"op": "album", "id": aid, "name": name, "chain": chain, "kind": kind, "created": True})
        r = P.album_add(aid, ids, batch_size=int(A.get("batch_size", 150)))
        log({"op": "add", "album": aid, "name": name, "requested": r["requested"], "in_album": r["in_album"],
             "missing": r["missing_after_add"], "failed": r["failed"], "ids": ids})
        summary["albums"] += 1
        summary["added"] += r["requested"] - len(r["missing_after_add"])
        summary["missing"] += len(r["missing_after_add"])
        summary["failed"] += len(r["failed"])
        return aid

    total = len(res["events"]) + 2
    for k, ev in enumerate(res["events"]):
        status.update(phase="albums", done=k, total=total, msg=ev["title"])
        make_album(ev["title"], [top, ev_folder], ev["ids"], "event")
    if res["junk"]:
        status.update(phase="junk album", done=total - 2, total=total)
        make_album(f"{A['junk_album']} {stamp}", [top], res["junk"], "junk")
    if res["dup_others"]:
        status.update(phase="duplicates album", done=total - 1, total=total)
        make_album(f"{A['dup_album']} {stamp}", [top], res["dup_others"], "dups")
    return summary


# ----------------------------------------------------------------------------- folder mode

def apply_folder(res, cfg, inv, log, status):
    root = cfg["source"]["folder"]
    org = os.path.join(root, "Organized")
    rev = os.path.join(root, "Review")
    summary = {"moved": 0, "skipped": 0}
    dev = os.stat(root).st_dev
    plan_moves = []
    for ev in res["events"]:
        dest = os.path.join(org, ev["year"], ev["title"])
        for i in ev["ids"]:
            r = inv.get(i)
            if r and r.get("path"):
                plan_moves.append((r["path"], os.path.join(dest, os.path.basename(r["path"])), "event", ev["eid"]))
    for i in res["junk"]:
        r = inv.get(i)
        if r and r.get("path"):
            plan_moves.append((r["path"], os.path.join(rev, "Junk", os.path.basename(r["path"])), "junk", ""))
    for g in res["dup_groups"]:
        for i in g["others"]:
            r = inv.get(i)
            if r and r.get("path"):
                plan_moves.append((r["path"], os.path.join(rev, "Duplicates", g["gid"], os.path.basename(r["path"])), "dup", g["gid"]))
    for k, (src, dst, kind, ref) in enumerate(plan_moves):
        if k % 50 == 0:
            status.update(phase="moving", done=k, total=len(plan_moves))
        if not os.path.exists(src):
            log({"op": "skip", "src": src, "why": "source missing"})
            summary["skipped"] += 1
            continue
        if os.stat(src).st_dev != dev:
            log({"op": "skip", "src": src, "why": "different volume"})
            summary["skipped"] += 1
            continue
        if os.path.abspath(os.path.dirname(src)) == os.path.abspath(os.path.dirname(dst)):
            log({"op": "skip", "src": src, "why": "already in place"})
            summary["skipped"] += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        dst = unique_path(dst)
        os.rename(src, dst)
        log({"op": "move", "src": src, "dst": dst, "kind": kind, "ref": ref})
        summary["moved"] += 1
    return summary


# ----------------------------------------------------------------------------- export (both modes)

def export_copies(res, export_dir, inv, log, status):
    summary = {"copied": 0, "skipped": 0}
    jobs = []
    for ev in res["events"]:
        dest = os.path.join(export_dir, ev["year"], ev["title"])
        for i in ev["ids"]:
            r = inv.get(i)
            if r and r.get("path") and not r.get("missing"):
                jobs.append((r["path"], os.path.join(dest, r.get("name") or os.path.basename(r["path"]))))
            else:
                summary["skipped"] += 1
    for k, (src, dst) in enumerate(jobs):
        if k % 50 == 0:
            status.update(phase="export", done=k, total=len(jobs))
        if not os.path.exists(src):
            log({"op": "skip", "src": src, "why": "source missing"})
            summary["skipped"] += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        dst = unique_path(dst)
        shutil.copy2(src, dst)
        digest = C.sha256_file(dst)
        if digest != C.sha256_file(src):
            os.remove(dst)
            log({"op": "skip", "src": src, "why": "copy did not verify, removed the bad copy"})
            summary["skipped"] += 1
            continue
        log({"op": "copy", "src": src, "dst": dst, "sha256": digest})
        summary["copied"] += 1
    return summary


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--run-dir")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--export", metavar="DIR")
    ap.add_argument("--no-albums", action="store_true", help="photos mode: skip album creation")
    ap.add_argument("--background", action="store_true", help="with --yes: run detached, poll with --wait")
    ap.add_argument("--wait", metavar="RUN_DIR")
    ap.add_argument("--seconds", type=int, default=110)
    args = ap.parse_args(argv)
    if args.wait:
        d = C.expand(args.wait)
        data, rc = C.wait_status(os.path.join(d, "apply.status.json"), args.seconds, "apply")
        if rc == 0:
            print(f"APPLIED {data.get('result')}")
            print(f"UNDO=python3 {os.path.join(C.HERE, 'pt_undo.py')} --run-dir {d} --yes")
        elif rc == 3:
            print(f"NEXT=python3 {os.path.abspath(__file__)} --wait {d} --seconds {args.seconds}")
        return rc
    cfg = C.load_config(args.config)
    run_dir = C.resolve_run_dir(cfg, args, "plan.json")
    if args.background and args.yes and not args.dry_run:
        extra = [a for a in (argv if argv is not None else sys.argv[1:]) if a != "--background"]
        if "--run-dir" in extra:
            i = extra.index("--run-dir")
            del extra[i:i + 2]
        plan_path = os.path.join(run_dir, "plan.json")
        why = check_approval(run_dir, plan_path, C.read_json(os.path.join(run_dir, "decisions.json"), {}) or {})
        if why:
            print(f"NOT_APPLIED: {why}")
            return 4
        return C.background_launch(os.path.abspath(__file__), run_dir, extra, "apply.status.json", "apply.log")
    plan_path = os.path.join(run_dir, "plan.json")
    plan = C.read_json(plan_path)
    dec = C.read_json(os.path.join(run_dir, "decisions.json"), {}) or {}
    mode = plan.get("mode") or cfg["source"]["mode"]
    inv = {r["id"]: r for r in C.read_jsonl(os.path.join(run_dir, "inventory.jsonl"))}
    res = resolve(plan, dec, cfg)
    export_dir = C.expand(args.export) if args.export else (cfg["apply"].get("export_dir") or "")
    why = check_approval(run_dir, plan_path, dec)

    print(f"RUN_DIR={run_dir}")
    print(f"MODE={mode}")
    print(f"PLANNED events={len(res['events'])} event_photos={sum(len(e['ids']) for e in res['events'])} junk={len(res['junk'])} dup_groups={len(res['dup_groups'])} dup_photos={len(res['dup_others'])} export={'yes to ' + export_dir if export_dir else 'no'}")
    for e in res["events"][:6]:
        print(f"  {e['title']}: {len(e['ids'])} items" + (f" (merged {', '.join(e['merged'])})" if e["merged"] else ""))
    if len(res["events"]) > 6:
        print(f"  ... {len(res['events']) - 6} more")
    if why:
        print(f"NOT_APPLIED: {why}")
        return 4
    if not args.yes or args.dry_run:
        print("DRY_RUN: add --yes to apply")
        return 0

    log_path = os.path.join(run_dir, "apply.log.jsonl")
    if os.path.exists(log_path):
        print(f"NOT_APPLIED: {log_path} already exists; undo that apply first (pt_undo.py) or start a new run")
        return 4
    status = C.Status(os.path.join(run_dir, "apply.status.json"), phase="start")

    def log(row):
        row["at"] = C.iso(C.now_local())
        C.append_jsonl(log_path, row)

    log({"op": "begin", "mode": mode, "approved_at": dec.get("approved_at"), "plan_hash": dec.get("plan_hash")})
    t0 = time.monotonic()
    summary = {}
    rc = 0
    try:
        # Copies first: in folder mode the originals move right after.
        if export_dir:
            summary["export"] = export_copies(res, export_dir, inv, log, status)
        if mode == "photos" and not args.no_albums:
            summary["photos"] = apply_photos(res, cfg, log, status)
            if summary["photos"]["missing"] or summary["photos"]["failed"]:
                rc = 2
        elif mode == "folder":
            summary["folder"] = apply_folder(res, cfg, inv, log, status)
    except Exception as err:
        log({"op": "error", "error": f"{type(err).__name__}: {err}"})
        status.finish(False, f"{type(err).__name__}: {err}")
        print(f"ERROR: {type(err).__name__}: {err}", file=sys.stderr)
        print(f"PARTIAL: actions so far are in {log_path}; python3 {os.path.join(C.HERE, 'pt_undo.py')} --run-dir {run_dir} --yes takes them back")
        return 2
    log({"op": "end", "seconds": round(time.monotonic() - t0), "summary": summary})
    dec["applied_at"] = C.iso(C.now_local())
    dec["apply_summary"] = summary
    C.write_json(os.path.join(run_dir, "decisions.json"), dec)
    status.finish(True, "applied", result=summary)
    print(f"APPLIED {summary} in {round(time.monotonic() - t0)}s")
    print(f"LOG={log_path}")
    print(f"UNDO=python3 {os.path.join(C.HERE, 'pt_undo.py')} --run-dir {run_dir} --yes")
    if mode == "photos":
        print(f"On the iPhone: Photos > Albums > {cfg['apply']['photos_folder']}. Delete from the review albums yourself when you are sure; this tool never deletes.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
