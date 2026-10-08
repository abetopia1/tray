#!/usr/bin/env python3
"""Read-only lookup against Fuzzy's Network Stack tracker."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

SHEET_ID = "3764671690526596"
EXPECTED_TITLE = "[Fuzzy's - Toast] Network Stack tracker"
API_URL = f"https://api.smartsheet.com/2.0/sheets/{SHEET_ID}"
TOKEN_FILE = Path.home() / ".fuzzys-recon" / "token"
USEFUL_TITLES = {
    "Dine Planning Date",
    "Dine Planning Date (FBC Date)",
    "Toast Confirmed Cut-Over Date",
    "MSP Changeover Target date",
    "MSP Changeover Date confirmed",
    "Weeks Away",
    "Original Restaurant Number",
    "Restaurant name",
    "Operating Group",
    "MSP Status",
    "MSP Choice",
    "Contract Status",
    "MSP Kick-off Deadline",
    "MSP Conversion Deadline",
    "Franchisee Submitted Spectrum inquiry",
    "Pending Scale (Mel) to connect",
    "Spectrum Foot Print (In/out)",
    "Site Prep completed",
    "Cut sheet - Site Survey Status",
    "Spectrum Install Tech Scheduled",
    "FBC",
    "POS System",
    "MSP Intro Call Date",
    "MSP Critical Start Date",
    "Original MSP",
}


def get_token() -> str:
    token = os.environ.get("SMARTSHEET_ACCESS_TOKEN", "").strip()
    if not token and TOKEN_FILE.is_file():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("Smartsheet credential is unavailable")
    return token


def fetch_sheet() -> dict:
    request = urllib.request.Request(
        API_URL,
        headers={"Authorization": f"Bearer {get_token()}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(300).decode("utf-8", errors="replace")
        raise RuntimeError(f"Smartsheet HTTP {exc.code}: {detail}") from exc
    if str(payload.get("id")) != SHEET_ID:
        raise RuntimeError(f"Wrong sheet ID returned: {payload.get('id')!r}")
    if payload.get("name") != EXPECTED_TITLE:
        raise RuntimeError(f"Wrong sheet title returned: {payload.get('name')!r}")
    rows = payload.get("rows", [])
    total = payload.get("totalRowCount")
    if total is not None and int(total) != len(rows):
        raise RuntimeError(f"Partial sheet: received {len(rows)} of {total} rows")
    return payload


def cell_value(cell: dict):
    value = cell.get("displayValue")
    return cell.get("value") if value is None else value


def row_map(row: dict, id_to_title: dict[int, str]) -> dict[str, object]:
    mapped: dict[str, object] = {}
    for cell in row.get("cells", []):
        title = id_to_title.get(cell.get("columnId"))
        if title:
            mapped[title] = cell_value(cell)
    return mapped


def compact_record(row: dict, row_id: object) -> dict[str, object]:
    selected: dict[str, object] = {"row_id": row_id}
    for title, value in row.items():
        if title in USEFUL_TITLES:
            selected[title] = value
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    sheet = fetch_sheet()
    id_to_title = {column["id"]: column["title"] for column in sheet.get("columns", [])}
    rows = [(row.get("id"), row_map(row, id_to_title)) for row in sheet.get("rows", [])]
    results: dict[str, list[dict[str, object]]] = {}
    for original_query in args.query:
        query = original_query.strip().lower()
        matches: list[dict[str, object]] = []
        for row_id, mapped in rows:
            haystack = "\n".join(str(value) for value in mapped.values() if value is not None).lower()
            if query and query in haystack:
                matches.append(compact_record(mapped, row_id))
        results[original_query] = matches

    output = {
        "sheet": {
            "id": str(sheet.get("id")),
            "title": sheet.get("name"),
            "version": sheet.get("version"),
            "modified_at": sheet.get("modifiedAt"),
            "permalink": sheet.get("permalink"),
            "row_count": len(rows),
            "total_row_count": sheet.get("totalRowCount"),
            "complete": sheet.get("totalRowCount") is None or int(sheet["totalRowCount"]) == len(rows),
        },
        "queries": results,
    }
    rendered = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(rendered, encoding="utf-8")
        temp.chmod(0o600)
        os.replace(temp, path)
        path.chmod(0o600)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
