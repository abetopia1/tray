#!/usr/bin/env python3
"""
paste_census.py  -  Full local export + dashboard for the Paste clipboard app (macOS)

WHY THIS EXISTS
  The Paste MCP connector caps every query at 100 items and is flaky. This script
  bypasses all of that by reading Paste's own SQLite database directly, on your Mac.
  No item cap, no network, no connector. Runs entirely offline, read-only.

WHAT IT DOES
  1. Finds Paste's database (com.wiheads.paste container) or use --db to point at it.
  2. Copies it (plus -wal/-shm) to a temp dir and opens READ-ONLY. Never writes to the original.
  3. Auto-detects the Core Data item table + which columns hold timestamp / app / type / content.
  4. Best-effort decodes the binary-plist (BPLIST) content blobs.
  5. Writes paste_history.csv and paste_history.jsonl (full history).
  6. Builds paste_dashboard.html (self-contained, open in any browser).

HOW TO RUN
  python3 paste_census.py
  # or, if auto-detect fails, point it at the file directly:
  python3 paste_census.py --db "~/Library/Containers/com.wiheads.paste/Data/Library/Application Support/Paste/Paste.sqlite"
  # optional: limit window, change output folder
  python3 paste_census.py --since 2025-12-03 --until 2026-06-04 --out ./paste_out

REQUIREMENTS
  Python 3.8+ standard library only. Nothing to pip install.

IF SOMETHING LOOKS WRONG
  Run with --debug. It prints the detected tables, the column-role guesses, and 3 sample
  rows. Paste me that output and I'll hardwire the right columns for your schema version.

NOTE ON CONTENT
  Paste stores the actual copied value as a binary plist (often an NSKeyedArchiver archive).
  Decoding is best-effort: clean strings come through; some items will show as <binary:N bytes>.
  The quantitative dashboard (counts by app/type/date/hour/day) does NOT depend on content,
  so it stays accurate even where a blob won't decode. Content only affects theme tagging
  and the sensitive-data scan.
"""

import argparse, os, sys, glob, shutil, tempfile, sqlite3, plistlib, csv, json, re, html
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

CORE_DATA_EPOCH = 978307200  # seconds between 1970-01-01 and 2001-01-01 (Core Data reference date)

DEFAULT_DB_GLOBS = [
    "~/Library/Containers/com.wiheads.paste/Data/Library/Application Support/Paste/*.sqlite",
    "~/Library/Containers/com.wiheads.paste/Data/Library/Application Support/Paste/*.sqlite3",
    "~/Library/Containers/com.wiheads.paste/Data/Library/Application Support/Paste/*.db",
    # broad fallbacks
    "~/Library/Containers/com.wiheads.paste/Data/Library/Application Support/**/*.sqlite",
    "~/Library/Application Support/Paste/**/*.sqlite",
]

# ----------------------------------------------------------------------------- locate + open

def find_db(user_path):
    if user_path:
        p = os.path.expanduser(user_path)
        if os.path.exists(p):
            return p
        sys.exit(f"[!] --db path not found: {p}")
    candidates = []
    for g in DEFAULT_DB_GLOBS:
        candidates += glob.glob(os.path.expanduser(g), recursive=True)
    # de-dupe, prefer largest (the real store, not aux files)
    candidates = sorted(set(candidates), key=lambda f: os.path.getsize(f), reverse=True)
    if not candidates:
        sys.exit("[!] Could not locate Paste's database automatically.\n"
                 "    Find it with:\n"
                 "    find ~/Library/Containers/com.wiheads.paste -iname '*.sqlite' 2>/dev/null\n"
                 "    then re-run with  --db \"<that path>\"")
    return candidates[0]

def open_readonly_copy(db_path):
    tmp = tempfile.mkdtemp(prefix="paste_census_")
    base = os.path.join(tmp, "paste.sqlite")
    shutil.copy2(db_path, base)
    for suffix in ("-wal", "-shm"):
        aux = db_path + suffix
        if os.path.exists(aux):
            shutil.copy2(aux, base + suffix)
    uri = f"file:{base}?mode=ro"
    return sqlite3.connect(uri, uri=True), tmp

# ----------------------------------------------------------------------------- schema sniffing

def list_tables(con):
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]

def columns(con, table):
    return [(r[1], (r[2] or "").upper()) for r in con.execute(f'PRAGMA table_info("{table}")')]

def rowcount(con, table):
    try:
        return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    except sqlite3.Error:
        return 0

def looks_like_date_col(name, decl):
    n = name.upper()
    return ("DATE" in n or "TIME" in n or "TIMESTAMP" in n or "CREATED" in n
            or "MODIFIED" in n or "COPIED" in n) and decl in ("", "REAL", "FLOAT", "DOUBLE", "INTEGER", "INT")

def pick_item_table(con):
    """Pick the table most likely to hold clipboard items: a Z-table (or any table) with the
    most rows that also has a date-like column."""
    best, best_score = None, -1
    for t in list_tables(con):
        if t.startswith("sqlite_") or t in ("Z_METADATA", "Z_MODELCACHE", "Z_PRIMARYKEY"):
            continue
        cols = columns(con, t)
        has_date = any(looks_like_date_col(n, d) for n, d in cols)
        rc = rowcount(con, t)
        # score: rows matter most; require a date column; prefer Z-tables
        score = rc + (1_000_000 if has_date else -5_000_000) + (50_000 if t.upper().startswith("Z") else 0)
        if score > best_score:
            best, best_score = t, score
    return best

def pick_columns(con, table):
    cols = columns(con, table)
    names = [c[0] for c in cols]
    low = {c[0]: c[0].lower() for c in cols}

    def first_match(keywords, want_text=None):
        for n, d in cols:
            ln = low[n]
            if any(k in ln for k in keywords):
                if want_text is True and d not in ("", "TEXT", "VARCHAR", "CHAR", "CLOB"):
                    continue
                return n
        return None

    date_col = None
    for n, d in cols:
        if looks_like_date_col(n, d):
            date_col = n
            break

    app_col    = first_match(["appname", "application", "bundle", "sourceapp", "source", "app"])
    device_col = first_match(["device", "machine", "host"])
    type_col   = first_match(["itemtype", "datatype", "contenttype", "kind", "type"])

    # content: prefer an obvious text/blob content column; else the TEXT column with longest avg length
    content_col = first_match(["content", "string", "preview", "searchable", "text", "value", "data", "plist", "body", "title"])
    if not content_col:
        # fallback: widest TEXT column by sampled length
        text_cols = [n for n, d in cols if d in ("TEXT", "VARCHAR", "CHAR", "CLOB", "")]
        widths = {}
        for n in text_cols:
            try:
                rows = con.execute(f'SELECT "{n}" FROM "{table}" WHERE "{n}" IS NOT NULL LIMIT 200').fetchall()
                widths[n] = sum(len(str(r[0])) for r in rows) / max(1, len(rows))
            except sqlite3.Error:
                widths[n] = 0
        if widths:
            content_col = max(widths, key=widths.get)

    return {"date": date_col, "app": app_col, "device": device_col,
            "type": type_col, "content": content_col, "all": names}

# ----------------------------------------------------------------------------- value decoding

def to_unix(val):
    """Normalize a timestamp cell to unix seconds. Handles Core Data ref-date, epoch s, epoch ms."""
    if val is None:
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        # maybe an ISO string
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00")).timestamp()
        except Exception:
            return None
    if v > 1e14:      # microseconds
        v /= 1e6
    elif v > 1e12:    # milliseconds
        v /= 1e3
    if v < 1e9:       # Core Data reference date (seconds since 2001)
        v += CORE_DATA_EPOCH
    return v

def decode_content(raw):
    """Best-effort: return a short clean text preview for a content cell."""
    if raw is None:
        return ""
    if isinstance(raw, (bytes, bytearray)):
        # try binary plist
        try:
            obj = plistlib.loads(bytes(raw))
            return _longest_string(obj)
        except Exception:
            # maybe utf-8 text stored as blob
            try:
                return raw.decode("utf-8", "ignore").strip()
            except Exception:
                return f"<binary:{len(raw)} bytes>"
    s = str(raw).strip()
    return s

def _longest_string(obj, depth=0):
    """Walk a decoded plist (incl. NSKeyedArchiver dicts) and return the longest human string."""
    if depth > 8:
        return ""
    best = ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        # NSKeyedArchiver: the useful strings usually live under '$objects'
        vals = obj.get("$objects", None)
        it = vals if isinstance(vals, list) else obj.values()
        for v in it:
            s = _longest_string(v, depth + 1)
            if len(s) > len(best):
                best = s
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            s = _longest_string(v, depth + 1)
            if len(s) > len(best):
                best = s
    elif isinstance(obj, (bytes, bytearray)):
        try:
            d = obj.decode("utf-8")
            if d.isprintable():
                best = d
        except Exception:
            pass
    # ignore pure archiver bookkeeping tokens
    if best in ("$null", "NSString", "NSMutableString", "NSObject", "NSDictionary", "NSArray"):
        return ""
    return best

URL_RE   = re.compile(r"^(https?|ftp)://", re.I)
HEX_RE   = re.compile(r"^#?[0-9a-fA-F]{6}$")
PATH_RE  = re.compile(r"^(/|~/|file://)[^\n]+$")

def infer_type(explicit, content):
    if explicit:
        e = str(explicit).lower()
        # order matters: 'file' must be tested before 'url' so 'public.file-url' -> file
        for key in ("image", "png", "jpg", "jpeg", "gif", "tiff", "color", "file", "link", "url", "rtf", "html", "text"):
            if key in e:
                return {"png":"image","jpg":"image","jpeg":"image","gif":"image","tiff":"image",
                        "url":"link","rtf":"text","html":"text"}.get(key, key)
    c = (content or "").strip()
    if not c:
        return "unknown"
    if HEX_RE.match(c):    return "color"
    if URL_RE.match(c):    return "link"
    if PATH_RE.match(c) and "\n" not in c and len(c) < 400: return "file"
    return "text"

# ----------------------------------------------------------------------------- classification

DINE = ["wave","msp","spectrum","toast","docusign","franchise","fuzzy","kds","meraki","vlan",
        "cut sheet","cradlepoint","store number","restaurant number","acuvigil","executive brief",
        "hardware","dine","aloha","ringcentral","site survey","go-live","cutover","onboard",
        "charter","fuzzysks","sharepoint","insideihop","speedtest","openclaw","tracking number",
        "intake","boarding","freedompay","fiserv","dual brand","nro","group"]
DPH  = ["telework check","rochelle","vpn","test logistics","public health","aou","performance eval",
        "sr information systems","acceptance criteria","user stor","uat","iteration","lacounty","ph.lacounty"]
PERS = ["i-130","residency","gawazat","mogamma","spouse","sidimohtadi","instagram","dalia","ibrahim",
        "escape","quran","prophet","dhul-hijjah","henna","wedding","honeymoon","villa","thumbnail"]

def domain(text, typ):
    t = (text or "").lower()
    if any(k in t for k in DPH):  return "LA County DPH"
    if any(k in t for k in PERS): return "Personal & side-projects"
    if any(k in t for k in DINE): return "Dine Brands (Fuzzy's/Toast)"
    if typ == "image":            return "Media (untaggable)"
    return "Mixed / untaggable"

def activity(text, typ):
    t = (text or "").lower()
    if typ == "image": return "Screenshot"
    if typ == "link":  return "Link"
    if typ == "color": return "Color"
    if typ == "file":  return "File path"
    if "telework check" in t: return "Telework log"
    if t.strip().startswith("=") or "=index" in t or "=countif" in t or "=iferror" in t: return "Spreadsheet formula"
    if "00:00:" in t or "transcript" in t or "meeting metadata" in t: return "Meeting transcript/notes"
    if re.search(r"\b\d{5,6}\b", t) and t.count("\n") > 3: return "ID/number list"
    if "good morning" in t or "good afternoon" in t or "from:" in t or "subject:" in t: return "Email text"
    return "Note/snippet"

# sensitive-data scanners (counts only; values are NOT written to the dashboard)
SCANS = {
    "Emails":          re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "Phone numbers":   re.compile(r"(?:\+?\d[\d\-\(\) ]{7,}\d)"),
    "Public IPs":      re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "Crypto/keys":     re.compile(r"\b(bc1[a-z0-9]{20,}|[A-Za-z0-9_\-]{40,})\b"),
    "Tracking #s":     re.compile(r"\b1Z[0-9A-Z]{16}\b|\b\d{12,22}\b"),
}

# ----------------------------------------------------------------------------- extract

def extract(con, table, cols, since, until):
    sel = []
    role = {}
    for key in ("date", "app", "device", "type", "content"):
        c = cols[key]
        if c:
            role[key] = len(sel)
            sel.append(f'"{c}"')
    if "date" not in role:
        sys.exit("[!] No timestamp column detected. Re-run with --debug and send me the output.")
    q = f'SELECT {", ".join(sel)} FROM "{table}"'
    rows = con.execute(q).fetchall()

    out = []
    for r in rows:
        ts = to_unix(r[role["date"]])
        if ts is None:
            continue
        if since and ts < since: continue
        if until and ts >= until: continue
        content = decode_content(r[role["content"]]) if "content" in role else ""
        typ = infer_type(r[role["type"]] if "type" in role else None, content)
        app = (str(r[role["app"]]).strip() if "app" in role and r[role["app"]] is not None else "")
        dev = (str(r[role["device"]]).strip() if "device" in role and r[role["device"]] is not None else "")
        out.append({
            "ts": ts,
            "iso": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            "app": app or "(unknown)",
            "device": dev or "(unknown)",
            "type": typ,
            "content": content,
        })
    out.sort(key=lambda x: x["ts"], reverse=True)
    return out

# ----------------------------------------------------------------------------- outputs

def write_data(items, outdir):
    os.makedirs(outdir, exist_ok=True)
    csv_path = os.path.join(outdir, "paste_history.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "app", "device", "type", "preview"])
        for it in items:
            prev = it["content"].replace("\n", " ").replace("\r", " ")[:300]
            w.writerow([it["iso"], it["app"], it["device"], it["type"], prev])
    jsonl_path = os.path.join(outdir, "paste_history.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for it in items:
            slim = {k: it[k] for k in ("iso", "app", "device", "type")}
            slim["preview"] = it["content"].replace("\n", " ")[:200]
            f.write(json.dumps(slim, ensure_ascii=False) + "\n")
    return csv_path, jsonl_path

def aggregates(items):
    a = {}
    a["total"] = len(items)
    a["types"]   = Counter(i["type"] for i in items)
    a["apps"]    = Counter(i["app"] for i in items)
    a["devices"] = Counter(i["device"] for i in items)
    a["domain"]  = Counter(domain(i["content"], i["type"]) for i in items)
    a["activity"]= Counter(activity(i["content"], i["type"]) for i in items)
    months, hours, dows = Counter(), Counter(), Counter()
    for i in items:
        dt = datetime.fromtimestamp(i["ts"], timezone.utc)
        months[dt.strftime("%Y-%m")] += 1
        hours[dt.hour] += 1
        dows[dt.strftime("%a")] += 1
    a["months"], a["hours"], a["dows"] = months, hours, dows
    if items:
        lo = datetime.fromtimestamp(min(i["ts"] for i in items), timezone.utc)
        hi = datetime.fromtimestamp(max(i["ts"] for i in items), timezone.utc)
        a["span_days"] = max(1, (hi - lo).days)
        a["lo"], a["hi"] = lo.date().isoformat(), hi.date().isoformat()
    else:
        a["span_days"], a["lo"], a["hi"] = 0, "-", "-"
    a["ai"] = sum(1 for i in items if i["app"] in ("Claude", "ChatGPT", "ChatGPT Atlas"))
    sens = Counter()
    for i in items:
        for label, rx in SCANS.items():
            if rx.search(i["content"] or ""):
                sens[label] += 1
    a["sensitive"] = sens
    return a

def bar_rows(counter, top=None, accent="var(--amber)"):
    items = counter.most_common(top) if top else sorted(counter.items())
    mx = max([v for _, v in items], default=1)
    out = []
    for k, v in items:
        pct = int(v / mx * 100)
        out.append(
            f'<div class="row"><div class="nm">{html.escape(str(k))}</div>'
            f'<div class="track"><div class="fill" style="width:{pct}%;background:{accent}"></div></div>'
            f'<div class="ct">{v}</div></div>')
    return "\n".join(out)

def col_rows(counter, order=None):
    items = [(k, counter.get(k, 0)) for k in order] if order else sorted(counter.items())
    mx = max([v for _, v in items], default=1)
    out = []
    for k, v in items:
        h = int(v / mx * 100)
        out.append(f'<div class="col"><div class="cv">{v}</div><div class="bar" style="height:{h}%"></div>'
                   f'<div class="cl">{html.escape(str(k))}</div></div>')
    return "\n".join(out)

def render_dashboard(a, outdir):
    dom_order = ["Dine Brands (Fuzzy's/Toast)","LA County DPH","Personal & side-projects",
                 "Media (untaggable)","Mixed / untaggable"]
    dom_colors = {"Dine Brands (Fuzzy's/Toast)":"#f2a93b","LA County DPH":"#46d6c4",
                  "Personal & side-projects":"#b88bf0","Media (untaggable)":"#5e6671","Mixed / untaggable":"#39414e"}
    total = a["total"] or 1
    dom_bar = ""
    leg = ""
    for d in dom_order:
        v = a["domain"].get(d, 0)
        pct = round(100 * v / total)
        if v:
            dom_bar += f'<div class="seg" style="width:{pct}%;background:{dom_colors[d]}">{pct if pct>=8 else ""}</div>'
            leg += (f'<div class="li"><span class="dot" style="background:{dom_colors[d]}"></span>'
                    f'<span class="ln">{html.escape(d)}</span><span class="lv">{v} ({pct}%)</span></div>')
    months_sorted = sorted(a["months"].items())
    month_order = [m for m, _ in months_sorted]
    per_day = round(a["total"] / a["span_days"], 2) if a["span_days"] else 0
    sens_cards = "".join(
        f'<div class="sc"><div class="v">{a["sensitive"].get(l,0)}</div><div class="l">{l}</div></div>'
        for l in SCANS)

    H = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paste Census — {a['lo']} to {a['hi']}</title>
<link href="https://fonts.googleapis.com/css2?family=Saira:wght@300;700;900&family=Hanken+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0c0e11;--panel:#15181d;--panel2:#1b1f26;--line:#262b33;--ink:#e8eaed;--mut:#888f9b;--dim:#5b626d;
--amber:#f2a93b;--teal:#46d6c4;--rose:#ef6f8e;--mono:'JetBrains Mono',monospace;--disp:'Saira',sans-serif;--body:'Hanken Grotesk',sans-serif;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:var(--body);line-height:1.5;
background-image:radial-gradient(900px 500px at 88% -8%,rgba(242,169,59,.07),transparent 60%);}}
.wrap{{max-width:1080px;margin:0 auto;padding:38px 22px 80px}}
.kick{{font-family:var(--mono);font-size:11px;letter-spacing:.28em;color:var(--amber);text-transform:uppercase}}
h1{{font-family:var(--disp);font-weight:900;font-size:clamp(32px,6vw,58px);line-height:.95;margin:12px 0 6px;letter-spacing:-.02em}}
.sub{{color:var(--mut);font-size:15px;max-width:680px}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:26px 0 30px}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:16px}}
.kpi .v{{font-family:var(--mono);font-weight:700;font-size:26px;color:#fff}}
.kpi .l{{font-size:11px;color:var(--mut);margin-top:3px}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:22px;margin-bottom:18px}}
.grid2{{display:grid;grid-template-columns:1.3fr 1fr;gap:18px}}
h2{{font-family:var(--disp);font-weight:700;font-size:13px;letter-spacing:.18em;text-transform:uppercase;margin-bottom:18px}}
.row{{display:grid;grid-template-columns:150px 1fr 42px;align-items:center;gap:11px;font-size:13px;margin-bottom:8px}}
.nm{{color:var(--mut);font-family:var(--mono);font-size:11px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.track{{height:18px;background:var(--panel2);border-radius:4px;overflow:hidden}}
.fill{{height:100%;border-radius:4px}}
.ct{{font-family:var(--mono);font-size:12px;text-align:right}}
.dom-bar{{display:flex;height:34px;border-radius:8px;overflow:hidden;margin-bottom:16px;border:1px solid var(--line)}}
.seg{{display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:11px;color:#0c0e11;font-weight:700}}
.li{{display:flex;align-items:center;gap:10px;font-size:13px;margin-bottom:8px}}
.dot{{width:11px;height:11px;border-radius:3px}} .ln{{flex:1}} .lv{{font-family:var(--mono);color:var(--mut);font-size:12px}}
.cols{{display:flex;align-items:flex-end;gap:6px;height:150px;padding-top:8px}}
.col{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:5px;height:100%}}
.bar{{width:100%;max-width:34px;background:linear-gradient(180deg,var(--teal),#2b7d74);border-radius:4px 4px 0 0}}
.cl{{font-family:var(--mono);font-size:9.5px;color:var(--mut)}} .cv{{font-family:var(--mono);font-size:10px;color:var(--dim)}}
.sens{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}
.sc{{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:14px}}
.sc .v{{font-family:var(--mono);font-size:22px;color:var(--rose);font-weight:700}} .sc .l{{font-size:11px;color:var(--mut);margin-top:3px}}
.note{{font-size:12.5px;color:var(--mut);margin-top:14px;padding-top:12px;border-top:1px dashed var(--line)}}
footer{{margin-top:30px;font-family:var(--mono);font-size:11px;color:var(--dim);line-height:1.7}}
@media(max-width:880px){{.kpis,.sens{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<div class="kick">Paste · Full Local Census</div>
<h1>Your clipboard, in full.</h1>
<p class="sub">Complete history read directly from Paste's database. {a['lo']} to {a['hi']}. Counts are exact; domain and activity labels are keyword-inferred from decoded content.</p>
<div class="kpis">
  <div class="kpi"><div class="v">{a['total']:,}</div><div class="l">items</div></div>
  <div class="kpi"><div class="v">{a['span_days']}</div><div class="l">days covered</div></div>
  <div class="kpi"><div class="v">{per_day}</div><div class="l">copies / day</div></div>
  <div class="kpi"><div class="v">{round(100*a['ai']/total)}%</div><div class="l">from AI apps</div></div>
  <div class="kpi"><div class="v">{len(a['apps'])}</div><div class="l">source apps</div></div>
</div>
<div class="panel"><h2>Domain mix</h2><div class="dom-bar">{dom_bar}</div>{leg}
<div class="note">Keyword-classified from decoded content. "Untaggable" = images or items whose content did not decode to text.</div></div>
<div class="grid2">
  <div class="panel"><h2>Source apps (top 15)</h2>{bar_rows(a['apps'], 15)}</div>
  <div class="panel"><h2>Content type</h2>{bar_rows(a['types'], None, 'var(--teal)')}
  <h2 style="margin-top:22px">Device</h2>{bar_rows(a['devices'], None, 'var(--teal)')}</div>
</div>
<div class="panel"><h2>Volume by month</h2><div class="cols">{col_rows(a['months'], month_order)}</div></div>
<div class="grid2">
  <div class="panel"><h2>Day of week</h2><div class="cols">{col_rows(a['dows'], ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])}</div></div>
  <div class="panel"><h2>Hour of day (UTC)</h2><div class="cols">{col_rows(a['hours'], list(range(24)))}</div></div>
</div>
<div class="panel"><h2>Activity type</h2>{bar_rows(a['activity'], None)}</div>
<div class="panel"><h2>Sensitive-data scan</h2><div class="sens">{sens_cards}</div>
<div class="note">Counts of items whose content matched each pattern. Actual values are never written to this file. Consider pruning these from Paste.</div></div>
<footer>Generated locally by paste_census.py · read-only · {datetime.now().strftime('%Y-%m-%d %H:%M')}<br>
Counts exact. Domain/activity = keyword heuristics on best-effort-decoded BPLIST content. Timestamps normalized from Core Data reference date to UTC.</footer>
</div></body></html>"""
    path = os.path.join(outdir, "paste_dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(H)
    return path

# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Export Paste clipboard history + build a dashboard, locally.")
    ap.add_argument("--db", help="Path to Paste's .sqlite (auto-detected if omitted)")
    ap.add_argument("--out", default="./paste_out", help="Output folder (default ./paste_out)")
    ap.add_argument("--since", help="Only items on/after YYYY-MM-DD (UTC)")
    ap.add_argument("--until", help="Only items before YYYY-MM-DD (UTC)")
    ap.add_argument("--debug", action="store_true", help="Print detected schema + samples and exit")
    args = ap.parse_args()

    db = find_db(args.db)
    print(f"[*] Using database: {db}")
    con, tmp = open_readonly_copy(db)
    try:
        table = pick_item_table(con)
        if not table:
            sys.exit("[!] No suitable item table found. Run with --debug.")
        cols = pick_columns(con, table)
        print(f"[*] Item table: {table}  ({rowcount(con, table)} rows)")
        print(f"[*] Column roles: " + ", ".join(f"{k}={cols[k]}" for k in ('date','app','device','type','content')))

        if args.debug:
            print("\n--- TABLES ---")
            for t in list_tables(con):
                print(f"  {t:30} rows={rowcount(con,t)}")
            print(f"\n--- COLUMNS of {table} ---")
            for n, d in columns(con, table):
                print(f"  {n:30} {d}")
            print("\n--- 3 SAMPLE ROWS (raw selected cols) ---")
            sel = [cols[k] for k in ('date','app','device','type','content') if cols[k]]
            for r in con.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in sel)} FROM "{table}" LIMIT 3'):
                print("  ", tuple(str(x)[:80] for x in r))
            return

        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() if args.since else None
        until = datetime.strptime(args.until, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() if args.until else None

        items = extract(con, table, cols, since, until)
        print(f"[*] Extracted {len(items):,} items")
        if not items:
            sys.exit("[!] 0 items extracted. Try --debug to inspect the schema.")

        csv_p, jsonl_p = write_data(items, args.out)
        a = aggregates(items)
        dash = render_dashboard(a, args.out)

        print(f"\n[OK] Wrote:")
        print(f"      {csv_p}")
        print(f"      {jsonl_p}")
        print(f"      {dash}")
        print(f"\n[SUMMARY] {a['total']:,} items, {a['lo']} -> {a['hi']} ({a['span_days']} days, {round(a['total']/a['span_days'],1) if a['span_days'] else 0}/day)")
        top_apps = ", ".join(f"{k} {v}" for k, v in a['apps'].most_common(5))
        print(f"[SUMMARY] Top apps: {top_apps}")
        print(f"[SUMMARY] Types: " + ", ".join(f"{k} {v}" for k, v in a['types'].most_common()))
        print(f"\nOpen the dashboard:  open {dash}")
        print("To go deeper, send me paste_history.csv and I'll build the full analysis.")
    finally:
        con.close()
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
