#!/usr/bin/env python3
"""
plaud_recap.py  -  Plaud meeting-email extractor + daily recap scaffolder

WHY THIS EXISTS
  Every meeting recorded with Plaud lands in the inbox as an email: the
  processed meeting notes in the email body, and the raw transcript attached
  (txt / docx / srt / vtt, sometimes pdf, sometimes an audio file too).
  This script turns a folder of those saved emails (.eml) into one organized
  per-day bundle that a person or an agent can write the daily recap from.
  Parsing and extraction here are purely mechanical and offline; the judgment
  work (decisions, action items, risks) stays with whoever reads the output.

WHAT IT DOES
  1. Scans a folder (recursively) for .eml files.
  2. Keeps messages that look like Plaud mail (sender/subject filter, see --match).
  3. Keeps messages received on the target date in the target timezone.
  4. Extracts the processed-notes body (HTML -> readable markdown-ish text).
  5. Extracts and decodes transcript attachments:
       .txt/.md      kept as-is
       .srt/.vtt     cue numbers + timestamps stripped into clean text (original kept)
       .docx         text pulled natively (unzip + document.xml, no dependencies)
       .pdf          saved raw; text via `pdftotext` when installed, else flagged
       audio         saved raw, flagged (not transcribed here)
  6. Writes <out>/<date>/ with one folder per meeting, plus:
       meetings.json      machine-readable index of everything extracted
       recap_skeleton.md  pre-structured scaffold in the house recap format
                          (decisions / action items / risks / impact / rollup)

HOW TO RUN
  python3 plaud_recap.py --source ./plaud_inbox
  python3 plaud_recap.py --source ./plaud_inbox --date 2026-08-26 --tz America/Los_Angeles
  # loosen or extend the filter if Plaud mail arrives forwarded from another address:
  python3 plaud_recap.py --source ./plaud_inbox --match plaud --match "fwd: meeting"
  # take every email in the folder regardless of sender/subject:
  python3 plaud_recap.py --source ./plaud_inbox --all
  # take every date found instead of one target day:
  python3 plaud_recap.py --source ./plaud_inbox --any-date

REQUIREMENTS
  Python 3.9+ standard library only. Nothing to pip install.
  (`pdftotext` from poppler is used opportunistically for PDF attachments.)

NOTES
  Transcripts contain speech-recognition errors and tentative wording. This
  script never rewrites content - it only decodes and organizes. The skeleton
  it emits deliberately leaves judgment cells blank rather than guessing.
"""

import argparse
import email
import email.policy
import email.utils
import html
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser

DEFAULT_MATCH = ["plaud"]          # case-insensitive substrings tested against From + Subject
DEFAULT_TZ = "America/Los_Angeles"

TEXT_EXTS = {".txt", ".md", ".text", ".log"}
SUBTITLE_EXTS = {".srt", ".vtt"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"}


# ----------------------------------------------------------------------------- timezone

def resolve_tz(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        print(f"[!] Timezone {name!r} unavailable (no zoneinfo/tzdata?); falling back to UTC. "
              f"Date filtering may be off by a few hours.", file=sys.stderr)
        return timezone.utc


# ----------------------------------------------------------------------------- html -> text

class _HtmlToText(HTMLParser):
    """Small HTML -> markdown-ish text converter. Good enough for email bodies."""

    BLOCK_TAGS = {"p", "div", "section", "article", "table", "tr", "ul", "ol", "blockquote"}
    SKIP_TAGS = {"script", "style", "head", "title", "meta"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0
        self._list_stack = []
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in ("br",):
            self.parts.append("\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("ul", "ol"):
            self._list_stack.append(tag)
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n" + "  " * max(0, len(self._list_stack) - 1) + "- ")
        elif tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag == "a":
            self._href = dict(attrs).get("href")
        elif tag == "hr":
            self.parts.append("\n---\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self.parts.append("\n")
        elif tag == "a":
            if self._href and not self._href.startswith(("cid:", "mailto:")):
                self.parts.append(f" ({self._href})")
            self._href = None
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth and data:
            self.parts.append(re.sub(r"[ \t]+", " ", data))

    def text(self):
        out = "".join(self.parts)
        out = re.sub(r"[ \t]+\n", "\n", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()


def html_to_text(markup):
    p = _HtmlToText()
    try:
        p.feed(markup)
        p.close()
    except Exception:
        # last resort: strip tags crudely
        return html.unescape(re.sub(r"<[^>]+>", " ", markup)).strip()
    return p.text()


# ----------------------------------------------------------------------------- attachment decoders

def decode_text_bytes(raw, charset=None):
    # utf-16 only with a BOM: BOM-less utf-16-le "succeeds" on most even-length
    # bytes and turns cp1252 transcripts into CJK mojibake. cp1252 before
    # latin-1 for smart quotes; latin-1 last because it never fails.
    encodings = [charset, "utf-8"]
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        encodings.append("utf-16")
    encodings += ["cp1252", "latin-1"]
    for enc in filter(None, encodings):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def clean_subtitles(text):
    """Strip SRT/VTT cue numbers and timestamps; keep the spoken lines."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s == "WEBVTT" or s.startswith(("NOTE ", "STYLE", "REGION")):
            continue
        if re.fullmatch(r"\d+", s):                       # SRT cue index
            continue
        if re.search(r"\d{1,2}:\d{2}(:\d{2})?[.,]\d{3}\s*-->", s):  # timestamp line
            continue
        s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)           # <v Speaker> etc.
        lines.append(s)
    return "\n".join(lines).strip()


def docx_to_text(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception:
        return None
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def pdf_to_text(path):
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-layout", path, "-"],
                           capture_output=True, timeout=60)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace").strip() or None
    except Exception:
        pass
    return None


# ----------------------------------------------------------------------------- message handling

def iter_eml_files(source):
    for root, _dirs, files in os.walk(source):
        for f in sorted(files):
            if f.lower().endswith(".eml"):
                yield os.path.join(root, f)


def load_message(path):
    try:
        with open(path, "rb") as fh:
            return email.message_from_binary_file(fh, policy=email.policy.default)
    except Exception as e:
        print(f"[!] Could not parse {path}: {e}", file=sys.stderr)
        return None


def matches_filter(msg, patterns):
    hay = " ".join([str(msg.get("From", "")), str(msg.get("Subject", ""))]).lower()
    return any(p.lower() in hay for p in patterns)


def received_at(msg, path, tz):
    """Best-effort received time as an aware datetime in tz."""
    dt = None
    raw = msg.get("Date")
    if raw:
        try:
            dt = email.utils.parsedate_to_datetime(raw)
        except Exception:
            dt = None
    if dt is None:
        dt = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def extract_body(msg):
    """Processed notes live in the body. Plaud's rich version is the HTML part;
    the text/plain sibling is sometimes a one-line stub - take whichever carries
    more content."""
    plain, htm = None, None
    for part in msg.walk():
        if (part.is_multipart() or part.get_filename()
                or part.get_content_disposition() == "attachment"):
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            content = decode_text_bytes(payload, part.get_content_charset())
        if ctype == "text/plain" and plain is None:
            plain = content
        elif ctype == "text/html" and htm is None:
            htm = content
    plain = (plain or "").strip()
    htm_text = html_to_text(htm).strip() if htm and htm.strip() else ""
    if htm_text and len(htm_text) > 2 * len(plain):
        return htm_text, "text/html"
    if plain:
        return plain, "text/plain"
    if htm_text:
        return htm_text, "text/html"
    return "", None


def safe_name(name, fallback="attachment"):
    name = os.path.basename(name or "").strip() or fallback
    name = re.sub(r"[^\w.\- ]+", "_", name)[:120]
    if not name.strip(". "):   # '.', '..', 'a/..' -> would escape/hit the dir itself
        name = fallback
    return name


def slugify(subject, maxlen=48):
    s = re.sub(r"^(\s*(re|fw|fwd)\s*:\s*)+", "", subject or "", flags=re.I)
    s = re.sub(r"\[[^\]]*\]", " ", s)          # drop [PLAUD]-style tags
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:maxlen].strip("-") or "meeting"


# Preferred extensions for unnamed attachments; the extension drives decoding
# and transcript picking, so a bare "attachment" name would lose the content.
EXT_FOR_TYPE = {
    "text/plain": ".txt", "text/markdown": ".md", "text/vtt": ".vtt",
    "application/x-subrip": ".srt", "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def extract_attachments(msg, att_dir):
    """Save every attachment (named, or marked attachment without a filename);
    decode what we can. One bad attachment never kills the meeting."""
    out = []
    seen = set()
    for part in msg.walk():
        if part.is_multipart():
            continue
        fname = part.get_filename()
        if not fname and part.get_content_disposition() != "attachment":
            continue
        raw = part.get_payload(decode=True)
        if raw is None:
            continue
        ctype = part.get_content_type()
        if not fname:
            fname = "attachment" + (EXT_FOR_TYPE.get(ctype)
                                    or mimetypes.guess_extension(ctype) or ".bin")
        name = safe_name(fname)
        base, ext = os.path.splitext(name)
        n = 1
        while name in seen:
            n += 1
            name = f"{base}_{n}{ext}"
        seen.add(name)

        ext = ext.lower()
        rec = {"name": name, "size": len(raw), "ext": ext, "text": None, "kind": "other"}
        try:
            os.makedirs(att_dir, exist_ok=True)
            path = os.path.join(att_dir, name)
            with open(path, "wb") as fh:
                fh.write(raw)
            if ext in TEXT_EXTS:
                rec["kind"] = "text"
                rec["text"] = decode_text_bytes(raw, part.get_content_charset())
            elif ext in SUBTITLE_EXTS:
                rec["kind"] = "subtitle"
                rec["text"] = clean_subtitles(decode_text_bytes(raw, part.get_content_charset()))
            elif ext == ".docx":
                rec["kind"] = "docx"
                rec["text"] = docx_to_text(raw)
            elif ext == ".pdf":
                rec["kind"] = "pdf"
                rec["text"] = pdf_to_text(path)
            elif ext in AUDIO_EXTS:
                rec["kind"] = "audio"
        except Exception as e:
            print(f"[!] Attachment {name!r} failed to save/decode ({e}); "
                  f"skipping it, not the meeting.", file=sys.stderr)
            rec["kind"] = "error"
            rec["text"] = None
        out.append(rec)
    return out


def pick_transcript(attachments):
    """The raw transcript: prefer a name that says so, else the longest decoded text."""
    decoded = [a for a in attachments if a["text"]]
    if not decoded:
        return None
    named = [a for a in decoded if re.search(r"transcript|verbatim|原文", a["name"], re.I)]
    pool = named or decoded
    return max(pool, key=lambda a: len(a["text"]))


# ----------------------------------------------------------------------------- outputs

RECAP_GUARDRAILS = """\
<!--
  How to fill this in (house rules):
  - The raw transcript is ground truth; Plaud's processed notes are a hint, not the record.
  - Transcripts contain speech-recognition errors and tentative ideas. Do not turn every
    statement into a decision, and do not "clean up" ambiguity by inventing specifics.
  - Action items need owner / due / dependency / status; leave a cell blank and flag it
    rather than guessing. Mark uncertain names, store numbers, and dates with (?).
  - Anything drafted for sending (emails, messages) is DRAFT ONLY - show verbatim, never send.
-->
"""


def meeting_section(idx, m):
    t = m["received_local_hm"]
    lines = [
        f"## {idx}. {m['title']}  —  {t}",
        "",
        f"- **Source email:** {m['subject']} (from {m['from']}, received {t})",
        f"- **Raw transcript:** {m['transcript_file'] or 'MISSING - not found in attachments'}"
        + (f" ({m['transcript_words']:,} words)" if m["transcript_words"] else ""),
        "- **Purpose / context:** ",
        "- **Participants (only those identifiable in the transcript):** ",
        "",
        "### Decisions",
        "| Decision | Evidence (quote or transcript section) |",
        "|---|---|",
        "|  |  |",
        "",
        "### Action items",
        "| # | Action | Owner | Due | Dependency | Status |",
        "|---|---|---|---|---|---|",
        "| 1 |  |  |  |  |  |",
        "",
        "### Risks, blockers, open questions",
        "- ",
        "",
        "### Site / workstream impact",
        "- ",
        "",
    ]
    return "\n".join(lines)


def build_skeleton(date_str, tz_name, meetings):
    head = [
        f"# Plaud Daily Recap — {date_str}",
        "",
        f"_Timezone: {tz_name}. Meetings captured: {len(meetings)}._",
        "",
        RECAP_GUARDRAILS,
    ]
    body = [meeting_section(i + 1, m) for i, m in enumerate(meetings)]
    tail = [
        "## Daily rollup",
        "",
        "- **Meetings captured:** " + (", ".join(m["title"] for m in meetings) or "none"),
        "- **Top actions across meetings:** ",
        "- **Decisions of the day:** ",
        "- **Risks and unresolved questions:** ",
        "- **Follow-ups drafted, awaiting approval (drafts only — nothing sent):** ",
        "- **Gaps / data hygiene** (missing transcripts, undecodable attachments, suspect dates): ",
        "",
    ]
    return "\n".join(head + body + tail)


def word_count(text):
    return len(re.findall(r"\S+", text or ""))


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Extract Plaud meeting emails into a per-day recap bundle.")
    ap.add_argument("--source", required=True, help="folder containing saved .eml files (searched recursively)")
    ap.add_argument("--out", default="./plaud_out", help="output folder (default ./plaud_out)")
    ap.add_argument("--date", default=None, help="target day YYYY-MM-DD (default: today in --tz)")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"IANA timezone for 'the day' (default {DEFAULT_TZ})")
    ap.add_argument("--match", action="append", default=None,
                    help="case-insensitive substring required in From or Subject "
                         "(repeatable; default: 'plaud')")
    ap.add_argument("--all", action="store_true", help="skip the sender/subject filter entirely")
    ap.add_argument("--any-date", action="store_true", help="skip the date filter, bundle every email found")
    ap.add_argument("--debug", action="store_true", help="print per-message accept/reject detail")
    args = ap.parse_args()

    tz = resolve_tz(args.tz)
    if args.date:
        try:
            target = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            sys.exit(f"[!] --date must be YYYY-MM-DD, got {args.date!r}")
    else:
        target = datetime.now(tz).date()
    patterns = args.match or DEFAULT_MATCH

    # Zero emails is a normal outcome ("no recordings today" is a valid recap):
    # still produce the empty bundle + skeleton and exit 0.
    if not os.path.isdir(args.source):
        print(f"[!] --source folder not found: {args.source}; treating as zero emails.",
              file=sys.stderr)
        eml_paths = []
    else:
        eml_paths = list(iter_eml_files(args.source))
        if not eml_paths:
            print(f"[!] No .eml files under {args.source}. Save each Plaud email as raw .eml "
                  f"(Gmail: 'Show original' -> Download; most clients: drag the message out). "
                  f"Proceeding with an empty bundle.", file=sys.stderr)

    accepted, rejected = [], []
    for path in eml_paths:
        msg = load_message(path)
        if msg is None:
            continue
        subject = str(msg.get("Subject", "")).strip() or "(no subject)"
        sender = str(msg.get("From", "")).strip()
        when = received_at(msg, path, tz)
        why = None
        if not args.all and not matches_filter(msg, patterns):
            why = f"filter miss (looked for {patterns} in From/Subject)"
        elif not args.any_date and when.date() != target:
            why = f"date {when.date()} != {target}"
        if why:
            rejected.append((path, subject, why))
            if args.debug:
                print(f"  skip  {os.path.basename(path)}: {why}")
            continue
        accepted.append((when, path, msg, subject, sender))
        if args.debug:
            print(f"  take  {os.path.basename(path)}: {subject!r} @ {when:%H:%M}")

    accepted.sort(key=lambda t: t[0])
    date_str = target.isoformat() if not args.any_date else "all-dates"
    day_dir = os.path.join(args.out, date_str)
    # A previous bundle for this day would leave stale meeting folders behind a
    # re-run and make meetings.json disagree with disk - rebuild from scratch.
    # Only remove a dir that is recognizably ours (has meetings.json).
    if os.path.isdir(day_dir) and os.path.exists(os.path.join(day_dir, "meetings.json")):
        shutil.rmtree(day_dir)
    os.makedirs(day_dir, exist_ok=True)

    meetings = []
    for i, (when, path, msg, subject, sender) in enumerate(accepted, 1):
        try:
            slug = slugify(subject)
            mdir = os.path.join(day_dir, f"{i:02d}-{slug}")
            os.makedirs(mdir, exist_ok=True)

            body, body_type = extract_body(msg)
            atts = extract_attachments(msg, os.path.join(mdir, "attachments"))
            transcript = pick_transcript(atts)

            with open(os.path.join(mdir, "email_summary.md"), "w", encoding="utf-8") as fh:
                fh.write(f"# {subject}\n\n_Plaud processed notes, from the email body "
                         f"({body_type or 'no body found'})._\n\n{body}\n")
            tpath = None
            if transcript:
                tpath = os.path.join(mdir, "transcript.txt")
                with open(tpath, "w", encoding="utf-8") as fh:
                    fh.write(transcript["text"])
        except Exception as e:
            print(f"[!] Failed to process {path}: {e}; skipping this message, not the day.",
                  file=sys.stderr)
            continue

        title = re.sub(r"^(\s*(re|fw|fwd)\s*:\s*)+", "", subject, flags=re.I)
        title = re.sub(r"\[[^\]]*\]", "", title)
        title = re.sub(r"\s+", " ", title).strip(" -:") or slug
        meetings.append({
            "index": i,
            "title": title,
            "subject": subject,
            "from": sender,
            "received_utc": when.astimezone(timezone.utc).isoformat(),
            "received_local": when.isoformat(),
            "received_local_hm": when.strftime("%H:%M"),
            "dir": os.path.relpath(mdir, args.out),
            "source_eml": path,
            "body_type": body_type,
            "body_words": word_count(body),
            "transcript_file": os.path.relpath(tpath, args.out) if tpath else None,
            "transcript_words": word_count(transcript["text"]) if transcript else 0,
            "attachments": [{k: a[k] for k in ("name", "size", "ext", "kind")} |
                            {"decoded": bool(a["text"])} for a in atts],
        })

    with open(os.path.join(day_dir, "meetings.json"), "w", encoding="utf-8") as fh:
        json.dump({"date": date_str, "tz": args.tz, "generated_utc":
                   datetime.now(timezone.utc).isoformat(), "meetings": meetings}, fh, indent=2)
    with open(os.path.join(day_dir, "recap_skeleton.md"), "w", encoding="utf-8") as fh:
        fh.write(build_skeleton(date_str, args.tz, meetings))

    print(f"[=] {len(eml_paths)} .eml scanned, {len(meetings)} Plaud meeting(s) for {date_str}, "
          f"{len(rejected)} skipped")
    for m in meetings:
        flag = "" if m["transcript_file"] else "   [! no transcript found]"
        print(f"    {m['index']:02d} {m['received_local_hm']}  {m['title']}"
              f"  ({m['transcript_words']:,} transcript words){flag}")
    if not meetings:
        print("    No matching Plaud emails for that day. A recap of 'no recordings today' is "
              "still a valid recap. (--debug shows why each message was skipped.)")
    print(f"[=] Bundle: {day_dir}")
    print(f"    Fill in: {os.path.join(day_dir, 'recap_skeleton.md')}")


if __name__ == "__main__":
    main()
