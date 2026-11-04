#!/usr/bin/env python3
"""Build the inventory for one run: one JSON line per photo or video with its
date, GPS, Photos metadata, a small thumbnail, perceptual hashes and a few
pixel statistics. Reads only. Never touches an original.

  python3 pt_scan.py                          # full scan, foreground
  python3 pt_scan.py --background             # start detached, print RUN_DIR and STATUS
  python3 pt_scan.py --wait RUN_DIR [--seconds 110]
  python3 pt_scan.py --ids-file FILE          # only these uuids (photos mode) or paths (folder mode)
  python3 pt_scan.py --limit 300              # trial run on the newest 300 items

Exit 0 done, 1 error, 3 still running (--wait only), 5 config or usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

C.ensure_venv()

FILENAME_DATE = re.compile(r"(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?:(?:[ _T-]|\s+at\s+)?(\d{2})[-.:_]?(\d{2})[-.:_]?(\d{2})?)?")
SKIP_DIRS = {"Organized", "Review", ".pt", "thumbs", "@eaDir"}


# ----------------------------------------------------------------------------- pixel work (runs in worker processes)

def _open_image(path):
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    img = Image.open(path)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def pixel_stats(pixels_path, thumb_path, thumb_px):
    """Thumbnail plus hashes and simple statistics. Reuses an existing thumb."""
    from PIL import Image, ImageFilter, ImageStat
    import imagehash

    out = {}
    if thumb_path and os.path.exists(thumb_path):
        img = Image.open(thumb_path)
        img.load()
    else:
        img = _open_image(pixels_path)
        img.thumbnail((thumb_px, thumb_px))
        img = img.convert("RGB")
        if thumb_path:
            tmp = f"{thumb_path}.tmp{os.getpid()}"
            img.save(tmp, "JPEG", quality=80, optimize=True)
            os.replace(tmp, thumb_path)
    out["thumb"] = os.path.basename(thumb_path) if thumb_path else None
    out["tw"], out["th"] = img.size
    out["phash"] = str(imagehash.phash(img))
    out["dhash"] = str(imagehash.dhash(img))
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    out["lum_mean"] = round(stat.mean[0], 1)
    out["lum_std"] = round(stat.stddev[0], 1)
    lap = gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
    out["blur"] = round(ImageStat.Stat(lap).var[0], 1)
    return out


def exif_meta(path):
    """Date, GPS, camera and size from the file's own EXIF (folder mode)."""
    out = {}
    img = _open_image(path)
    out["w"], out["h"] = img.size
    try:
        exif = img.getexif()
    except Exception:
        return out
    base = dict(exif)
    try:
        ifd = exif.get_ifd(0x8769)
    except Exception:
        ifd = {}
    make = str(base.get(0x010F, "") or "").strip()
    model = str(base.get(0x0110, "") or "").strip()
    if make or model:
        out["camera"] = f"{make} {model}".strip()
    raw = ifd.get(0x9003) or ifd.get(0x9004) or base.get(0x0132)
    offset = ifd.get(0x9011) or ifd.get(0x9010)
    if raw:
        dt = parse_exif_date(str(raw), str(offset) if offset else None)
        if dt:
            out["date"] = dt.isoformat(timespec="seconds")
            out["date_src"] = "exif"
    try:
        gps = exif.get_ifd(0x8825)
    except Exception:
        gps = {}
    if gps and 2 in gps and 4 in gps:
        lat = _dms(gps[2], gps.get(1, "N"))
        lon = _dms(gps[4], gps.get(3, "E"))
        if lat is not None and lon is not None and (lat, lon) != (0.0, 0.0):
            out["lat"], out["lon"] = round(lat, 6), round(lon, 6)
    return out


def _dms(v, ref):
    try:
        d, m, s = [float(x) for x in v]
    except Exception:
        return None
    val = d + m / 60.0 + s / 3600.0
    if str(ref).upper() in ("S", "W"):
        val = -val
    return val


def parse_exif_date(raw, offset=None):
    raw = raw.strip().replace("-", ":", 2) if raw[:4].isdigit() and raw[4] == "-" else raw.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M", "%Y:%m:%d"):
        try:
            dt = datetime.strptime(raw[:19], fmt)
            break
        except ValueError:
            dt = None
    if not dt or dt.year < 1990:
        return None
    if offset:
        m = re.match(r"([+-])(\d{2}):?(\d{2})", offset.strip())
        if m:
            sign = 1 if m.group(1) == "+" else -1
            tz = timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))
            return dt.replace(tzinfo=tz)
    return dt


def filename_date(name):
    m = FILENAME_DATE.search(name)
    if not m:
        return None
    y, mo, d, hh, mi, ss = m.groups()
    try:
        return datetime(int(y), int(mo), int(d), int(hh or 0), int(mi or 0), int(ss or 0))
    except ValueError:
        return None


def video_meta(path):
    out = {}
    if shutil.which("ffprobe"):
        try:
            r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
                               capture_output=True, text=True, timeout=60)
            info = json.loads(r.stdout or "{}")
            tags = (info.get("format") or {}).get("tags") or {}
            ct = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")
            if ct:
                dt = C.parse_iso(ct.replace("Z", "+00:00"))
                if dt:
                    out["date"] = dt.isoformat(timespec="seconds")
                    out["date_src"] = "ffprobe"
            loc = tags.get("com.apple.quicktime.location.ISO6709") or tags.get("location")
            if loc:
                m = re.match(r"([+-]\d+\.?\d*)([+-]\d+\.?\d*)", loc)
                if m:
                    out["lat"], out["lon"] = round(float(m.group(1)), 6), round(float(m.group(2)), 6)
            for s in info.get("streams") or []:
                if s.get("codec_type") == "video":
                    out["w"], out["h"] = s.get("width"), s.get("height")
                    break
        except Exception:
            pass
    if "date" not in out:
        dt = filename_date(os.path.basename(path))
        if dt:
            out["date"], out["date_src"] = dt.isoformat(timespec="seconds"), "filename"
        else:
            dt = datetime.fromtimestamp(os.path.getmtime(path)).astimezone()
            out["date"], out["date_src"] = dt.isoformat(timespec="seconds"), "mtime"
    return out


def work(item):
    out = {"id": item["id"]}
    try:
        if item["need_exif"] and item["original"]:
            if item["kind"] == "video":
                out.update(video_meta(item["original"]))
            else:
                try:
                    out.update(exif_meta(item["original"]))
                except Exception as err:
                    out["meta_error"] = f"{type(err).__name__}: {err}"[:200]
                if "date" not in out:
                    dt = filename_date(os.path.basename(item["original"]))
                    if dt:
                        out["date"], out["date_src"] = dt.isoformat(timespec="seconds"), "filename"
                    else:
                        dt = datetime.fromtimestamp(os.path.getmtime(item["original"])).astimezone()
                        out["date"], out["date_src"] = dt.isoformat(timespec="seconds"), "mtime"
        pixels = item.get("pixels")
        if item["kind"] == "video" and pixels and os.path.splitext(pixels)[1].lower() in C.VIDEO_EXT:
            pixels = None
        if pixels and (os.path.exists(pixels) or (item["thumb"] and os.path.exists(item["thumb"]))):
            out.update(pixel_stats(pixels, item["thumb"], item["thumb_px"]))
    except Exception as err:
        out["error"] = f"{type(err).__name__}: {err}"[:200]
    return out


# ----------------------------------------------------------------------------- sources

def folder_records(cfg, ids=None, limit=None):
    root = cfg["source"]["folder"]
    if not os.path.isdir(root):
        raise SystemExit(f"ERROR: source folder not found: {root}")
    wanted = None
    if ids:
        wanted = set()
        for p in ids:
            p = p.strip()
            if p:
                wanted.add(os.path.relpath(C.expand(p) if os.path.isabs(p) else os.path.join(root, p), root))
    recs = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in C.PHOTO_EXT:
                kind = "photo"
            elif ext in C.VIDEO_EXT and cfg["source"]["include_videos"]:
                kind = "video"
            else:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if wanted is not None and rel not in wanted:
                continue
            try:
                st = os.stat(full)
            except OSError:
                continue
            rid = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:16]
            recs.append({
                "id": rid, "src": "folder", "uuid": None, "path": full, "rel": rel, "missing": False,
                "name": fn, "ext": ext.lstrip("."), "kind": kind, "live": False,
                "screenshot": bool(re.search(r"screenshot|screen shot|capture d", fn, re.I)),
                "screen_recording": bool(kind == "video" and re.search(r"screen ?record", fn, re.I)),
                "burst": False, "burst_selected": False, "burst_key": False,
                "date": None, "date_added": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
                "date_src": None, "w": None, "h": None, "bytes": st.st_size, "mtime": int(st.st_mtime),
                "lat": None, "lon": None, "place": {}, "home": False,
                "labels": [], "persons": [], "albums": [], "keywords": [], "favorite": False, "hidden": False, "shared": False,
                "score": {}, "fingerprint": None, "camera": None, "title": "",
                "_pixels": full,
            })
    recs.sort(key=lambda r: r["mtime"], reverse=True)
    if limit:
        recs = recs[:limit]
    return recs


def photos_records(cfg, status, ids=None, limit=None, ledger=None):
    import pt_photos
    return pt_photos.read_library(cfg, status, uuids=ids, limit=limit, ledger=ledger)


# ----------------------------------------------------------------------------- main

def run_scan(args, cfg):
    run_dir = args.run_dir
    status = C.Status(os.path.join(run_dir, "scan.status.json"), phase="listing")
    led = C.Ledger()
    t0 = time.monotonic()
    ids = None
    if args.ids_file:
        with open(C.expand(args.ids_file), encoding="utf-8") as fh:
            ids = [l.strip() for l in fh if l.strip()]
    mode = cfg["source"]["mode"]
    try:
        if mode == "photos":
            recs = photos_records(cfg, status, ids=ids, limit=args.limit, ledger=led)
        elif mode == "folder":
            recs = folder_records(cfg, ids=ids, limit=args.limit)
        else:
            raise SystemExit(f"ERROR: source.mode must be photos or folder, not {mode!r}")
    except SystemExit:
        raise
    except Exception as err:
        status.finish(False, f"listing failed: {type(err).__name__}: {err}")
        print(f"ERROR: listing failed: {type(err).__name__}: {err}", file=sys.stderr)
        return 1
    led.add("listing", "COMPLETE", f"{len(recs)} items from {mode} source in {time.monotonic()-t0:.0f}s")
    status.update(phase="pixels", done=0, total=len(recs), force=True)

    tdir = C.thumbs_dir(cfg)
    items = []
    for r in recs:
        items.append({
            "id": r["id"], "kind": r["kind"], "original": r.get("path") or None,
            "pixels": r.pop("_pixels", None), "thumb": os.path.join(tdir, f"{r['id']}.jpg"),
            "need_exif": r["src"] == "folder", "thumb_px": int(cfg["thumb_px"]),
        })
    by_id = {r["id"]: r for r in recs}
    workers = max(1, int(cfg.get("workers") or 1))
    errors = thumbs = 0
    done = 0
    ctx = mp.get_context("spawn") if sys.platform == "darwin" else mp.get_context()
    with ctx.Pool(workers) as pool:
        for out in pool.imap_unordered(work, items, chunksize=8):
            r = by_id[out.pop("id")]
            if out.get("error"):
                errors += 1
            if out.get("thumb"):
                thumbs += 1
            r.update(out)
            done += 1
            if done % 25 == 0 or done == len(items):
                status.update(done=done, msg=f"thumbs {thumbs}, errors {errors}")
    for r in recs:
        r.pop("mtime", None)
        if r.get("thumb") is None:
            r["thumb"] = None
    missing = sum(1 for r in recs if r.get("missing"))
    photos = sum(1 for r in recs if r["kind"] == "photo")
    videos = len(recs) - photos
    dated = sum(1 for r in recs if r.get("date"))
    gps = sum(1 for r in recs if r.get("lat") is not None)
    led.add("pixels", "COMPLETE" if errors == 0 else "PARTIAL", f"{thumbs} thumbnails, {errors} errors, {missing} originals not on disk")
    C.write_jsonl(os.path.join(run_dir, "inventory.jsonl"), recs)
    meta = {
        "scanned_at": C.iso(C.now_local()), "mode": mode, "source": cfg["source"],
        "counts": {"total": len(recs), "photos": photos, "videos": videos, "missing": missing,
                   "thumbs": thumbs, "errors": errors, "dated": dated, "gps": gps},
        "ids_file": args.ids_file, "limit": args.limit, "seconds": round(time.monotonic() - t0),
        "ledger": led.rows,
    }
    C.write_json(os.path.join(run_dir, "meta.json"), meta)
    status.finish(True, f"{len(recs)} items", result=meta["counts"])
    print(f"RUN_DIR={run_dir}")
    print(f"INVENTORY={os.path.join(run_dir, 'inventory.jsonl')}")
    print(f"COUNTS total={len(recs)} photos={photos} videos={videos} dated={dated} gps={gps} thumbs={thumbs} missing={missing} errors={errors} seconds={meta['seconds']}")
    print("LEDGER:")
    for line in led.lines():
        print("  " + line)
    print(f"NEXT=python3 {os.path.join(C.HERE, 'pt_plan.py')} --run-dir {run_dir} --background")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--run-dir")
    ap.add_argument("--ids-file")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--tag", default="")
    ap.add_argument("--background", action="store_true")
    ap.add_argument("--wait", metavar="RUN_DIR")
    ap.add_argument("--seconds", type=int, default=110)
    args = ap.parse_args(argv)
    if args.wait:
        data, rc = C.wait_status(os.path.join(C.expand(args.wait), "scan.status.json"), args.seconds, "scan")
        if rc == 0:
            print(f"RUN_DIR={C.expand(args.wait)}")
            print(f"NEXT=python3 {os.path.join(C.HERE, 'pt_plan.py')} --run-dir {C.expand(args.wait)} --background")
        elif rc == 3:
            print(f"NEXT=python3 {os.path.abspath(__file__)} --wait {C.expand(args.wait)} --seconds {args.seconds}")
        return rc
    try:
        cfg = C.load_config(args.config)
    except (OSError, ValueError) as err:
        print(f"ERROR: config: {err}", file=sys.stderr)
        return 5
    if not args.run_dir:
        args.run_dir = C.new_run_dir(cfg, args.tag or ("new" if args.ids_file else ""))
    else:
        args.run_dir = C.expand(args.run_dir)
        os.makedirs(args.run_dir, exist_ok=True)
    if args.background:
        extra = [a for a in (argv if argv is not None else sys.argv[1:]) if a != "--background"]
        if "--run-dir" in extra:
            i = extra.index("--run-dir")
            del extra[i:i + 2]
        return C.background_launch(os.path.abspath(__file__), args.run_dir, extra, "scan.status.json", "scan.log")
    return run_scan(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
