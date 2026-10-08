#!/usr/bin/env python3
"""tracker_brief.py: read-only Smartsheet tracker snapshot, diff, and brief.

One run, no browser, no screenshots. Reads each configured sheet through the
Smartsheet REST API, diffs it against the snapshot saved by the last delivered
brief, prints the brief, and only then saves the new snapshots.

  python3 tracker_brief.py                  # brief to stdout, copy saved under $HERMES_HOME/cache/fuzzys-brief
  python3 tracker_brief.py --show-columns   # print detected columns per sheet and exit
  python3 tracker_brief.py --config PATH    # use another config.json

Exit codes: 0 brief printed, 2 no token or rejected token, 3 API, network,
deadline, or unexpected error, 4 sheet not found, 5 config or usage error.
Standard library only.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://api.smartsheet.com/2.0"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.normpath(os.path.join(HERE, "..", "config.json"))


def hermes_home():
    """The Hermes home this skill is installed in. The skill's own location
    (<home>/skills/fuzzys-cos-brief/scripts) wins over HERMES_HOME, because a
    gateway serving several profiles can hand a profile's script the default
    profile's environment."""
    derived = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
    if os.path.basename(os.path.dirname(derived)) == "profiles" or os.path.exists(os.path.join(derived, "config.yaml")):
        return derived
    env = os.environ.get("HERMES_HOME")
    if env:
        return os.path.expanduser(env)
    return os.path.expanduser("~/.hermes")


HERMES_HOME = hermes_home()
ENV_PATH = os.path.join(HERMES_HOME, ".env")
STATE_DIR = os.path.join(HERMES_HOME, "cache", "fuzzys-brief")
PAGE_SIZE = 5000
DEADLINE_SECONDS = 240          # whole run; the terminal call allows 300
REQUEST_TIMEOUT = 30
DATE_TYPES = ("DATE", "DATETIME", "ABSTRACT_DATETIME")
DATE_FORMATS = (
    "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%m/%d/%Y", "%m/%d/%y",
    "%m-%d-%Y", "%m-%d-%y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%d-%b-%Y",
)
KEY_HINTS = re.compile(r"(store|site|restaurant)\s*(#|no\.?|num|number|id)\b|^store$", re.I)
TOKEN_LINE = re.compile(r"^\s*(?:export\s+)?SMARTSHEET_ACCESS_TOKEN\s*=\s*(.*)$")
STARTED = time.monotonic()


class BriefError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def remaining_seconds():
    return DEADLINE_SECONDS - (time.monotonic() - STARTED)


# ----------------------------------------------------------------------------- auth + http

def load_token():
    token = os.environ.get("SMARTSHEET_ACCESS_TOKEN", "").strip()
    if token:
        return token
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as fh:
            for line in fh:
                match = TOKEN_LINE.match(line.rstrip("\n"))
                if not match:
                    continue
                value = match.group(1).strip()
                if value[:1] in ("'", '"'):
                    value = value[1:].split(value[0], 1)[0]
                else:
                    value = value.split(" #", 1)[0].split("\t#", 1)[0].strip()
                if value:
                    return value
    raise BriefError(
        f"SMARTSHEET_ACCESS_TOKEN is not set in the environment or in {ENV_PATH} "
        "(Smartsheet > Personal Settings > API Access).", 2,
    )


def http_get(path, token, params=None, retries=1):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "fuzzys-cos-brief/1.1",
    })
    for attempt in range(retries + 1):
        left = remaining_seconds()
        if left <= 5:
            raise BriefError(f"run deadline of {DEADLINE_SECONDS}s reached before {path}", 3)
        try:
            with urllib.request.urlopen(req, timeout=min(REQUEST_TIMEOUT, left)) as resp:
                raw = resp.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except ValueError:
                raise BriefError(f"non-JSON response on {path}: {raw[:120]!r}", 3)
        except urllib.error.HTTPError as err:
            if err.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(min(2 * (attempt + 1), max(remaining_seconds() - 5, 0)))
                continue
            body = err.read().decode("utf-8", "replace")[:200].replace("\n", " ")
            code = 4 if err.code == 404 else (2 if err.code in (401, 403) else 3)
            raise BriefError(f"Smartsheet HTTP {err.code} on {path}: {body}", code)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            if attempt < retries:
                time.sleep(min(2, max(remaining_seconds() - 5, 0)))
                continue
            raise BriefError(f"network error on {path}: {err}", 3)


# ----------------------------------------------------------------------------- sheets

def resolve_sheet_id(spec, token):
    if spec.get("id"):
        return int(spec["id"])
    needle = (spec.get("name_match") or spec.get("label") or "").strip()
    if not needle:
        raise BriefError(f"sheet entry needs an id or a name_match: {spec}", 5)
    listing = http_get("/sheets", token, {"includeAll": "true"})
    sheets = listing.get("data", [])
    exact = [s for s in sheets if s.get("name", "").strip().lower() == needle.lower()]
    partial = [s for s in sheets if needle.lower() in s.get("name", "").lower()]
    hits = exact or partial
    if not hits:
        raise BriefError(f"no Smartsheet sheet named like '{needle}' is visible to this token", 4)
    if len(hits) > 1:
        names = ", ".join(f"{s['name']} ({s['id']})" for s in hits[:6])
        raise BriefError(f"'{needle}' matches several sheets; pin the id in config.json: {names}", 5)
    return int(hits[0]["id"])


def fetch_sheet(sheet_id, token):
    first = http_get(f"/sheets/{sheet_id}", token, {"pageSize": PAGE_SIZE, "page": 1})
    rows = list(first.get("rows", []))
    total = first.get("totalRowCount", len(rows))
    page = 1
    while len(rows) < total and first.get("rows"):
        page += 1
        more = http_get(f"/sheets/{sheet_id}", token, {"pageSize": PAGE_SIZE, "page": page})
        batch = more.get("rows", [])
        if not batch:
            break
        rows.extend(batch)
    first["rows"] = rows
    return first


def cell_text(cell, col_type=""):
    value = cell.get("value")
    display = cell.get("displayValue")
    if col_type in DATE_TYPES and value not in (None, ""):
        return str(value).strip()          # ISO, independent of the display format
    if display not in (None, ""):
        return str(display).strip()
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value).strip()


def snapshot_from_sheet(sheet, spec):
    columns = [{"id": c["id"], "title": c.get("title", ""), "type": c.get("type", ""),
                "primary": bool(c.get("primary")), "formula": c.get("formula") or ""}
               for c in sheet.get("columns", [])]
    by_id = {c["id"]: c for c in columns}
    rows = []
    for row in sheet.get("rows", []):
        cells = {}
        for cell in row.get("cells", []):
            col = by_id.get(cell.get("columnId"))
            if col and col["title"]:
                cells[col["title"]] = cell_text(cell, col["type"])
        rows.append({"id": row.get("id"), "rowNumber": row.get("rowNumber"),
                     "modifiedAt": row.get("modifiedAt"), "cells": cells})
    titles = {c["title"] for c in columns}
    key_column = spec.get("key_column")
    if key_column and key_column not in titles:
        print(f"warning: key_column '{key_column}' is not a column of '{sheet.get('name')}'; detecting one instead",
              file=sys.stderr)
        key_column = None
    if not key_column:
        key_column = detect_key_column(columns, rows)
    values = [(r["cells"].get(key_column) or "").strip() for r in rows]
    non_blank = [v for v in values if v]
    if len(set(non_blank)) < len(non_blank):
        print(f"warning: key column '{key_column}' of '{sheet.get('name')}' is not unique across rows; "
              "rows sharing a key are merged in the diff. Pin key_column in config.json.", file=sys.stderr)
    return {
        "id": sheet.get("id"), "name": sheet.get("name"), "version": sheet.get("version"),
        "modifiedAt": sheet.get("modifiedAt"), "totalRowCount": sheet.get("totalRowCount", len(rows)),
        "readAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "keyColumn": key_column, "columns": columns, "rows": rows,
    }


def detect_key_column(columns, rows):
    def unique(title):
        values = [(r["cells"].get(title) or "").strip() for r in rows]
        non_blank = [v for v in values if v]
        return bool(non_blank) and len(set(non_blank)) == len(non_blank)

    hinted = [c["title"] for c in columns if KEY_HINTS.search(c["title"].strip())]
    primary = [c["title"] for c in columns if c["primary"]]
    for title in hinted + primary:
        if unique(title):
            return title
    if hinted:
        return hinted[0]
    if primary:
        return primary[0]
    return columns[0]["title"] if columns else None


def today_formula_columns(snapshot):
    return {c["title"].lower() for c in snapshot["columns"] if "today(" in (c.get("formula") or "").lower()}


def detect_date_columns(snapshot, spec, ignore_columns=()):
    if spec.get("date_columns"):
        return list(spec["date_columns"])
    ignore = {c.lower() for c in ignore_columns} | today_formula_columns(snapshot)
    found = []
    for col in snapshot["columns"]:
        if col["title"].lower() in ignore:
            continue
        if col["type"] in DATE_TYPES or "date" in col["title"].lower():
            found.append(col["title"])
    return found


# ----------------------------------------------------------------------------- snapshots + diff

def snapshot_path(sheet_id):
    return os.path.join(STATE_DIR, "snapshots", f"{sheet_id}.json")


def load_previous(sheet_id):
    path = snapshot_path(sheet_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def save_snapshot(snapshot):
    path = snapshot_path(snapshot["id"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False)
    os.replace(tmp, path)


def row_key(row, key_column):
    key = (row["cells"].get(key_column) or "").strip() if key_column else ""
    return key or f"row-id {row['id']}"


def diff_snapshots(prev, cur, ignore_columns):
    key_column = cur["keyColumn"]
    ignore = {c.lower() for c in ignore_columns} | today_formula_columns(cur)
    formula_cols = {c["title"] for c in cur["columns"] if c.get("formula")}
    prev_rows = {row_key(r, prev.get("keyColumn") or key_column): r for r in prev["rows"]}
    cur_rows = {row_key(r, key_column): r for r in cur["rows"]}
    added = sorted(k for k in cur_rows if k not in prev_rows)
    removed = sorted(k for k in prev_rows if k not in cur_rows)
    manual, derived = [], []
    for key in sorted(k for k in cur_rows if k in prev_rows):
        before, after = prev_rows[key]["cells"], cur_rows[key]["cells"]
        for column in sorted(set(before) | set(after)):
            if column.lower() in ignore:
                continue
            old, new = before.get(column, ""), after.get(column, "")
            if old != new:
                (derived if column in formula_cols else manual).append((key, column, old, new))
    return {"added": added, "removed": removed, "changes": manual + derived, "manual_changes": len(manual)}


# ----------------------------------------------------------------------------- dates + hygiene

def parse_date(text):
    text = (text or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def upcoming_items(snapshot, date_columns, today, lookahead_days):
    horizon = today + timedelta(days=lookahead_days)
    items = []
    for row in snapshot["rows"]:
        key = row_key(row, snapshot["keyColumn"])
        for column in date_columns:
            when = parse_date(row["cells"].get(column))
            if when and today <= when <= horizon:
                items.append((when, key, column))
    return sorted(items)


def hygiene_items(snapshot, required_columns):
    problems = []
    key_column = snapshot["keyColumn"]
    blank_keys = sum(1 for r in snapshot["rows"] if key_column and not (r["cells"].get(key_column) or "").strip())
    if blank_keys:
        problems.append(f"{blank_keys} row(s) with an empty '{key_column}'")
    for column in required_columns:
        missing = [row_key(r, key_column) for r in snapshot["rows"] if not (r["cells"].get(column) or "").strip()]
        if missing:
            shown = ", ".join(missing[:8]) + (" ..." if len(missing) > 8 else "")
            problems.append(f"{len(missing)} row(s) missing '{column}': {shown}")
    return problems


# ----------------------------------------------------------------------------- brief

def now_in(tz_name):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_name))
    except Exception:  # zoneinfo or tz data missing: fall back to UTC
        return datetime.now(timezone.utc)


def fmt_local(iso_utc, tz_name):
    if not iso_utc:
        return "unknown"
    try:
        stamp = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    except ValueError:
        return iso_utc
    try:
        from zoneinfo import ZoneInfo
        stamp = stamp.astimezone(ZoneInfo(tz_name))
    except Exception:
        pass
    return stamp.strftime("%Y-%m-%d %H:%M %Z")


def build_brief(results, cfg, now):
    tz_name = cfg.get("timezone", "America/Los_Angeles")
    lookahead = int(cfg.get("lookahead_days", 14))
    lines = []
    lines.append(f"# Fuzzy's Chief of Staff brief, {now.strftime('%Y-%m-%d %H:%M %Z')}")
    lines.append("")
    heads = []
    for r in results:
        cur, prev = r["cur"], r["prev"]
        if prev is None:
            heads.append(f"{r['label']} (v{cur['version']}, first read)")
        elif prev.get("version") == cur.get("version"):
            heads.append(f"{r['label']} (v{cur['version']}, unchanged)")
        else:
            heads.append(f"{r['label']} (v{prev.get('version')} to v{cur['version']})")
    lines.append("Source: live Smartsheet API read, read-only. Trackers: " + "; ".join(heads) + ".")
    lines.append("")

    lines.append("## Changes since last read")
    for r in results:
        cur, prev, diff = r["cur"], r["prev"], r["diff"]
        if prev is None:
            lines.append(f"### {r['label']}: baseline stored ({len(cur['rows'])} rows). Changes appear from the next run.")
            continue
        since = fmt_local(prev.get("readAt"), tz_name)
        if not (diff["added"] or diff["removed"] or diff["changes"]):
            lines.append(f"### {r['label']}: no change since {since} (version {cur['version']}, {len(cur['rows'])} rows)")
            continue
        derived = len(diff["changes"]) - diff["manual_changes"]
        lines.append(f"### {r['label']}: {diff['manual_changes']} cell(s) edited, {derived} formula cell(s) recomputed, "
                     f"{len(diff['added'])} row(s) added, {len(diff['removed'])} removed since {since}")
        for key in diff["added"][:20]:
            lines.append(f"- added row: {key}")
        for key in diff["removed"][:20]:
            lines.append(f"- removed row: {key}")
        for key, column, old, new in diff["changes"][:60]:
            lines.append(f"- {key}, {column}: {old or '(blank)'} -> {new or '(blank)'}")
        if len(diff["changes"]) > 60:
            lines.append(f"- ... {len(diff['changes']) - 60} more cell changes in the saved snapshot diff")
    lines.append("")

    lines.append(f"## Next {lookahead} days, dated milestones from the trackers")
    any_items = False
    for r in results:
        for when, key, column in r["upcoming"][:40]:
            any_items = True
            lines.append(f"- {when.isoformat()}  {key}, {column}  ({r['label']})")
    if not any_items:
        lines.append("- none found in the detected date columns (pin date_columns in config.json if this looks wrong)")
    lines.append("")

    lines.append("## Data hygiene")
    any_problem = False
    for r in results:
        for problem in r["hygiene"]:
            any_problem = True
            lines.append(f"- {r['label']}: {problem}")
    if not any_problem:
        lines.append("- no empty keys; add required_columns in config.json to check more")
    lines.append("")

    lines.append("## Not covered")
    lines.append("Email, Teams, and vendor calendars were not read. The tracker versions above are the proof "
                 "behind every line; verify a row in the live sheet before outreach.")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- main

def load_config(path):
    if not os.path.exists(path):
        raise BriefError(f"config not found: {path} (copy config.example.json to config.json)", 5)
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except ValueError as err:
        raise BriefError(f"config is not valid JSON: {err}", 5)
    if not isinstance(cfg.get("sheets"), list) or not cfg["sheets"]:
        raise BriefError("config.json needs a non-empty 'sheets' list", 5)
    return cfg


def run(args):
    cfg = load_config(args.config)
    token = load_token()
    tz_name = cfg.get("timezone", "America/Los_Angeles")
    now = now_in(tz_name)
    today = now.date()
    ignore_columns = cfg.get("ignore_columns", [])
    results = []
    for spec in cfg["sheets"]:
        label = spec.get("label") or spec.get("name_match") or "sheet"
        sheet_id = resolve_sheet_id(spec, token)
        cur = snapshot_from_sheet(fetch_sheet(sheet_id, token), spec)
        if not spec.get("label"):
            label = cur.get("name") or label
        date_columns = detect_date_columns(cur, spec, ignore_columns)
        if args.show_columns:
            print(f"== {label} (id {sheet_id}, version {cur['version']}, {len(cur['rows'])} rows)")
            print(f"   key column: {cur['keyColumn']}")
            print(f"   date columns: {', '.join(date_columns) or '(none detected)'}")
            for col in cur["columns"]:
                flags = ("  primary" if col["primary"] else "") + ("  formula" if col.get("formula") else "")
                print(f"   - {col['title']}  [{col['type']}]{flags}")
            continue
        prev = load_previous(sheet_id)
        diff = diff_snapshots(prev, cur, ignore_columns) if prev else None
        results.append({
            "label": label, "cur": cur, "prev": prev, "diff": diff,
            "upcoming": upcoming_items(cur, date_columns, today, int(cfg.get("lookahead_days", 14))),
            "hygiene": hygiene_items(cur, spec.get("required_columns", [])),
        })
    if args.show_columns:
        return 0
    brief = build_brief(results, cfg, now)
    sys.stdout.write(brief)
    sys.stdout.flush()
    if not args.no_save:
        # Saved only after the brief is out, so a failed run never moves the baseline.
        for r in results:
            save_snapshot(r["cur"])
        out_dir = os.path.join(STATE_DIR, "briefs")
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, now.strftime("%Y%m%d-%H%M") + ".md")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(brief)
        print(f"[saved to {out}]", file=sys.stderr)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 exit_on_error=False)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--show-columns", action="store_true", help="print detected columns per sheet and exit")
    ap.add_argument("--no-save", action="store_true", help="do not store the snapshot or the brief")
    try:
        args = ap.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as err:
        print(f"ERROR (5): usage: {err}", file=sys.stderr)
        return 5
    try:
        return run(args)
    except BriefError as err:
        print(f"ERROR ({err.code}): {err}", file=sys.stderr)
        return err.code
    except Exception as err:  # anything else is reported as a retriable failure, never a traceback
        print(f"ERROR (3): unexpected failure: {type(err).__name__}: {err}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
