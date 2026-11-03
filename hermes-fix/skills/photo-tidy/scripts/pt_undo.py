#!/usr/bin/env python3
"""Take back what pt_apply.py did for one run, in reverse order, from its
apply.log.jsonl. Albums the run created are deleted (an album deletion
never deletes a photo), folders the run created are removed only when
empty, moved files go back to where they came from, and exported copies are
removed only after their checksum still matches the original.

  python3 pt_undo.py [--run-dir DIR]        # show what would be undone
  python3 pt_undo.py --run-dir DIR --yes    # undo

Exit 0 done, 2 partial, 4 nothing to undo, 5 usage.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

C.ensure_venv()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--run-dir")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)
    cfg = C.load_config(args.config)
    run_dir = C.resolve_run_dir(cfg, args, "apply.log.jsonl")
    log_path = os.path.join(run_dir, "apply.log.jsonl")
    undo_path = os.path.join(run_dir, "undo.log.jsonl")
    rows = C.read_jsonl(log_path)
    if not rows:
        print("NOTHING_TO_UNDO: apply.log.jsonl is empty")
        return 4
    done_before = {r.get("key") for r in C.read_jsonl(undo_path) if r.get("ok")}
    if any(r.get("op") == "complete" for r in C.read_jsonl(undo_path)):
        print(f"NOTHING_TO_UNDO: {undo_path} says this run was already undone")
        return 4
    steps = []
    for i, r in enumerate(rows):
        key = f"{i}:{r.get('op')}"
        if key in done_before:
            continue
        if r.get("op") == "move":
            steps.append((key, "move back", r))
        elif r.get("op") == "copy":
            steps.append((key, "remove copy", r))
        elif r.get("op") == "album" and r.get("created"):
            steps.append((key, "delete album", r))
        elif r.get("op") == "folder" and r.get("created"):
            steps.append((key, "remove folder if empty", r))
    steps.reverse()
    print(f"RUN_DIR={run_dir}")
    print(f"STEPS={len(steps)}: " + ", ".join(f"{k} {sum(1 for s in steps if s[1] == k)}" for k in dict.fromkeys(s[1] for s in steps)))
    if not args.yes:
        for _, what, r in steps[:10]:
            print(f"  {what}: {r.get('name') or r.get('dst') or r.get('src')}")
        if len(steps) > 10:
            print(f"  ... {len(steps) - 10} more")
        print("DRY_RUN: add --yes to undo")
        return 0
    P = None
    ok = fail = 0
    for key, what, r in steps:
        row = {"key": key, "what": what, "ok": False}
        try:
            if what == "move back":
                if not os.path.exists(r["dst"]):
                    raise FileNotFoundError(f"moved file is gone: {r['dst']}")
                if os.path.exists(r["src"]):
                    raise FileExistsError(f"original path is occupied: {r['src']}")
                os.makedirs(os.path.dirname(r["src"]), exist_ok=True)
                os.rename(r["dst"], r["src"])
                for d in (os.path.dirname(r["dst"]), os.path.dirname(os.path.dirname(r["dst"]))):
                    try:
                        os.rmdir(d)
                    except OSError:
                        break
            elif what == "remove copy":
                if os.path.exists(r["dst"]):
                    if C.sha256_file(r["dst"]) != r.get("sha256"):
                        raise ValueError(f"copy was modified, left in place: {r['dst']}")
                    if not os.path.exists(r["src"]) or C.sha256_file(r["src"]) != r.get("sha256"):
                        raise ValueError(f"original no longer matches, copy left in place: {r['dst']}")
                    os.remove(r["dst"])
                    try:
                        os.rmdir(os.path.dirname(r["dst"]))
                    except OSError:
                        pass
            elif what == "delete album":
                if P is None:
                    import pt_photos as P
                P.delete_album(r["id"])
            elif what == "remove folder if empty":
                if P is None:
                    import pt_photos as P
                row["result"] = P.delete_folder_if_empty(r["chain"])
            row["ok"] = True
            ok += 1
        except Exception as err:
            row["error"] = f"{type(err).__name__}: {err}"
            fail += 1
        row["at"] = C.iso(C.now_local())
        C.append_jsonl(undo_path, row)
    if fail == 0:
        C.append_jsonl(undo_path, {"op": "complete", "at": C.iso(C.now_local())})
        dec = C.read_json(os.path.join(run_dir, "decisions.json"), {}) or {}
        dec.pop("applied_at", None)
        dec["undone_at"] = C.iso(C.now_local())
        C.write_json(os.path.join(run_dir, "decisions.json"), dec)
    print(f"UNDONE ok={ok} failed={fail}")
    print(f"LOG={undo_path}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
