#!/usr/bin/env python3
"""Check a written Chief of Staff brief against the run's evidence, then copy
it to the Desktop under a timed name that never overwrites an earlier brief.

  python3 cos_check.py RUN_DIR             # checks RUN_DIR/brief.md, copies on PASS
  python3 cos_check.py RUN_DIR --no-copy   # check only

Exit 0 PASS, 1 FAIL (reasons printed, nothing copied), 5 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "..", "config.json")
STORE_TOKEN = re.compile(r"#\s?(\d{5,6})\b")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️⭐⭕⌚⌛⏩-⏺]")
SECTION = re.compile(r"^\s*(?:#+\s*)?(?:Section\s+)?([1-5])[.)]\s+\S")


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--no-copy", action="store_true")
    args = ap.parse_args(argv)
    run_dir = os.path.abspath(os.path.expanduser(args.run_dir))
    brief_path = run_dir if run_dir.endswith(".md") else os.path.join(run_dir, "brief.md")
    run_dir = os.path.dirname(brief_path) if brief_path.endswith(".md") and run_dir.endswith(".md") else run_dir
    if not os.path.exists(brief_path):
        print(f"FAIL: brief not found at {brief_path}; write it there first")
        return 1
    cfg = load_config()
    with open(brief_path, encoding="utf-8") as fh:
        brief = fh.read()
    failures, warnings = [], []

    if len(brief) < 1500:
        failures.append(f"brief is only {len(brief)} characters; a complete five-section brief is far longer")
    first = next((l for l in brief.splitlines() if l.strip()), "")
    if not re.search(r"\b(COMPLETE|PARTIAL|BLOCKED)\b", first):
        failures.append("first line must state coverage COMPLETE, PARTIAL or BLOCKED")
    if "—" in brief:
        n = brief.count("—")
        failures.append(f"{n} em dash(es) present; replace each with a comma, a colon or a new sentence")
    emojis = EMOJI.findall(brief)
    if emojis:
        failures.append(f"{len(emojis)} emoji present; remove them")
    if re.search(r"SMARTSHEET_ACCESS_TOKEN\s*=|Bearer\s+[A-Za-z0-9]{20,}", brief):
        failures.append("a credential-shaped string is in the brief; remove it")
    found = []
    for line in brief.splitlines():
        m = SECTION.match(line)
        if m and (not found or int(m.group(1)) > found[-1]):
            found.append(int(m.group(1)))
    missing = [n for n in range(1, 6) if n not in found]
    if missing:
        failures.append(f"section heading(s) missing or out of order: {missing} (headings start with the section number, 1 to 5, in order)")

    master_path = os.path.join(run_dir, "evidence", "master.json")
    keys, names = set(), {}
    if os.path.exists(master_path):
        try:
            with open(master_path, encoding="utf-8") as fh:
                master = json.load(fh)
            key_col = master.get("keyColumn")
            name_col = next((c["title"] for c in master.get("columns", []) if "restaurant name" in c["title"].lower()), None)
            for row in master.get("rows", []):
                k = re.sub(r"\D", "", row["cells"].get(key_col, "") or "")
                if k:
                    keys.add(k)
                    names[k] = (row["cells"].get(name_col, "") if name_col else "") or ""
        except (OSError, ValueError, KeyError) as err:
            warnings.append(f"could not read evidence/master.json ({err}); store numbers not verified")
    else:
        warnings.append("no evidence/master.json in this run; store numbers not verified against the live Master")
    if keys:
        unknown, name_mismatch = {}, []
        for line in brief.splitlines():
            for num in STORE_TOKEN.findall(line):
                if num not in keys:
                    unknown[num] = unknown.get(num, 0) + 1
                    continue
                city = re.split(r"[,(]", names.get(num, ""))[0].strip()
                if city and city.lower() not in line.lower():
                    name_mismatch.append(f"#{num} is '{names[num]}' in the Master; the line says: {line.strip()[:90]}")
        if unknown:
            failures.append("store numbers not in the live Master: " + ", ".join(f"#{k} (x{v})" for k, v in sorted(unknown.items())))
        if name_mismatch:
            warnings.append("store number and name may disagree (verify): " + " | ".join(name_mismatch[:8]))

    status = {"checked_at": datetime.now().astimezone().isoformat(timespec="seconds"), "brief": brief_path,
              "failures": failures, "warnings": warnings, "status": "FAIL" if failures else "PASS"}
    if failures:
        print("FAIL")
        for f in failures:
            print(f"- {f}")
        for w in warnings:
            print(f"- warning: {w}")
        with open(os.path.join(run_dir, "status.json"), "w", encoding="utf-8") as fh:
            json.dump(status, fh, indent=1)
        return 1

    copy_path = ""
    if not args.no_copy:
        tz = None
        if ZoneInfo and cfg.get("timezone"):
            try:
                tz = ZoneInfo(cfg["timezone"])
            except Exception:
                tz = None
        now = datetime.now(tz) if tz else datetime.now().astimezone()
        desktop = os.path.expanduser(cfg.get("desktop", "~/Desktop"))
        os.makedirs(desktop, exist_ok=True)
        base = os.path.join(desktop, f"Chief_of_Staff_Brief_{now.strftime('%Y-%m-%d_%H%M')}")
        copy_path = base + ".md"
        n = 2
        while os.path.exists(copy_path):
            copy_path = f"{base}_{n}.md"
            n += 1
        shutil.copyfile(brief_path, copy_path)
        os.chmod(copy_path, 0o600)
    status["desktop_copy"] = copy_path
    with open(os.path.join(run_dir, "status.json"), "w", encoding="utf-8") as fh:
        json.dump(status, fh, indent=1)
    print("PASS")
    for w in warnings:
        print(f"- warning: {w}")
    if copy_path:
        print(f"DESKTOP_COPY={copy_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
