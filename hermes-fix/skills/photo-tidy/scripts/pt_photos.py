#!/usr/bin/env python3
"""macOS Photos adapter. Reading goes through osxphotos, which opens a copy of
the library database and never writes to it. Writing goes through osascript
and is limited to creating folders and albums and adding items to albums.
There is no code path here that deletes a media item.

  python3 pt_photos.py --probe        # create a test folder and album, add one photo, verify, remove both again
  python3 pt_photos.py --tree         # list the Hermes Tidy folder, its albums and counts
  python3 pt_photos.py --library-info # which library osxphotos will read

Run --probe once from Terminal so macOS asks for the Photos automation
permission there. Exit 0 PASS, 1 FAIL.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

C.ensure_venv()

ITEM_SUFFIX = "/L0/001"


class PhotosError(Exception):
    pass


# ----------------------------------------------------------------------------- read (osxphotos)

def _first(v):
    if isinstance(v, (list, tuple)):
        return str(v[0]) if v else ""
    return str(v) if v else ""


def _place(p):
    try:
        pl = p.place
    except Exception:
        pl = None
    if not pl:
        return {}, False
    out = {"src": "photos"}
    try:
        n = pl.names
        out["city"] = _first(n.city) or _first(n.additional_city_info)
        out["state"] = _first(n.state_province)
        out["country"] = _first(n.country)
        out["area"] = _first(n.area_of_interest)
    except Exception:
        pass
    try:
        out["name"] = pl.name or ""
    except Exception:
        out["name"] = ""
    try:
        home = bool(pl.ishome)
    except Exception:
        home = False
    return out, home


def _score(p):
    try:
        s = p.score
    except Exception:
        s = None
    if not s:
        return {}
    keys = {"overall": "overall", "failure": "failure", "sharp": "sharply_focused_subject",
            "noise": "noise", "low_light": "low_light", "curation": "curation"}
    out = {}
    for k, attr in keys.items():
        v = getattr(s, attr, None)
        if v is not None:
            out[k] = round(float(v), 3)
    return out


def read_library(cfg, status=None, uuids=None, limit=None, ledger=None):
    from osxphotos import PhotosDB

    src = cfg["source"]
    lib = src.get("photos_library") or None
    t0 = time.monotonic()
    if status:
        status.update(phase="opening library", msg=lib or "system library", force=True)
    db = PhotosDB(dbfile=lib) if lib else PhotosDB()
    if ledger is not None:
        ledger.add("library", "COMPLETE", f"{db.library_path} opened in {time.monotonic()-t0:.0f}s")
    photos = db.photos(uuid=uuids or None, images=True, movies=bool(src.get("include_videos", True)))
    photos.sort(key=lambda p: (p.date_added or p.date or C.now_local()), reverse=True)
    if limit:
        photos = photos[:limit]
    recs = []
    skipped = {"hidden": 0, "shared": 0, "trash": 0, "error": 0}
    total = len(photos)
    for i, p in enumerate(photos):
        if status and (i % 200 == 0):
            status.update(phase="reading library", done=i, total=total)
        try:
            if p.intrash:
                skipped["trash"] += 1
                continue
            if p.hidden and not src.get("include_hidden"):
                skipped["hidden"] += 1
                continue
            if p.shared and not src.get("include_shared"):
                skipped["shared"] += 1
                continue
            place, home = _place(p)
            loc = p.location or (None, None)
            try:
                deriv = p.path_derivatives or []
            except Exception:
                deriv = []
            pixels = deriv[-1] if deriv else (p.path if p.path and os.path.exists(p.path) else None)
            exif = None
            try:
                exif = p.exif_info
            except Exception:
                exif = None
            camera = None
            if exif and (exif.camera_make or exif.camera_model):
                camera = f"{exif.camera_make or ''} {exif.camera_model or ''}".strip()
            persons = [x for x in (p.persons or []) if x and x != "_UNKNOWN_"]
            try:
                labels = list(p.labels or [])
            except Exception:
                labels = []
            recs.append({
                "id": p.uuid, "src": "photos", "uuid": p.uuid, "path": p.path or "", "missing": bool(p.ismissing or not p.path),
                "name": p.original_filename, "ext": os.path.splitext(p.original_filename or "")[1].lstrip(".").lower(),
                "kind": "video" if p.ismovie else "photo", "live": bool(p.live_photo),
                "screenshot": bool(p.screenshot), "screen_recording": bool(getattr(p, "screen_recording", False)),
                "burst": bool(p.burst), "burst_selected": bool(p.burst_selected), "burst_key": bool(p.burst_key),
                "date": C.iso(p.date), "date_added": C.iso(p.date_added), "date_src": "photos",
                "w": p.width, "h": p.height, "bytes": p.original_filesize,
                "lat": round(loc[0], 6) if loc[0] is not None else None,
                "lon": round(loc[1], 6) if loc[1] is not None else None,
                "place": place, "home": home,
                "labels": labels, "persons": persons, "albums": list(p.albums or []), "keywords": list(p.keywords or []),
                "favorite": bool(p.favorite), "hidden": bool(p.hidden), "shared": bool(p.shared),
                "score": _score(p), "fingerprint": p.fingerprint, "camera": camera, "title": p.title or "",
                "_pixels": pixels,
            })
        except Exception as err:
            skipped["error"] += 1
            if skipped["error"] <= 5 and ledger is not None:
                ledger.add("library", "PARTIAL", f"{getattr(p, 'uuid', '?')}: {type(err).__name__}: {err}")
    if ledger is not None:
        ledger.add("library filter", "COMPLETE", f"skipped hidden={skipped['hidden']} shared={skipped['shared']} trash={skipped['trash']} errors={skipped['error']}")
    return recs


def library_info(cfg):
    from osxphotos import PhotosDB
    lib = cfg["source"].get("photos_library") or None
    db = PhotosDB(dbfile=lib) if lib else PhotosDB()
    n = len(db.photos())
    return {"library": db.library_path, "db_version": db.db_version, "photos": n}


# ----------------------------------------------------------------------------- write (osascript)

def as_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


APPLE_EVENT_TIMEOUT = 1800   # Photos answers a big album slowly; the default Apple event timeout is 120 s (-1712)


_TELL_OPEN = re.compile(r'^([ \t]*)tell application "Photos"[ \t]*$', re.M)
_TELL_CLOSE = re.compile(r'^([ \t]*)end tell[ \t]*$', re.M)


def with_timeout(script):
    """Wrap every multi-line tell block in a long Apple event timeout. Blocks
    inside handlers are indented, so the inserted lines keep each block's own
    indentation and the opener and closer always pair up."""
    script = _TELL_OPEN.sub(lambda m: f'{m[1]}tell application "Photos"\n{m[1]}    with timeout of {APPLE_EVENT_TIMEOUT} seconds', script)
    return _TELL_CLOSE.sub(lambda m: f'{m[1]}    end timeout\n{m[1]}end tell', script)


def osascript(script, timeout=2400):
    script = with_timeout(script)
    try:
        r = subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise PhotosError("osascript not found; this step only runs on macOS")
    except subprocess.TimeoutExpired:
        raise PhotosError(f"osascript timed out after {timeout}s")
    if r.returncode != 0:
        msg = (r.stderr or "").strip() or f"osascript exit {r.returncode}"
        if "-1743" in msg or "Not authorized" in msg:
            msg += " | Photos automation permission is missing for this host. Run pt_photos.py --probe from Terminal once, or grant it under System Settings > Privacy & Security > Automation."
        raise PhotosError(msg)
    return (r.stdout or "").strip()


def _lines(out):
    return [l for l in out.split("\n") if l.strip()]


def folder_ref(chain):
    ref = ""
    for fid in chain:
        ref = f"folder id {as_str(fid)}" + (f" of {ref}" if ref else "")
    return ref


def find_folders(name, parent_chain=()):
    src = f"folders of ({folder_ref(parent_chain)})" if parent_chain else "folders"
    script = f'''
tell application "Photos"
    set out to {{}}
    repeat with f in ({src})
        if name of f is {as_str(name)} then set end of out to (id of f as text)
    end repeat
    set AppleScript's text item delimiters to linefeed
    return out as text
end tell'''
    return _lines(osascript(script))


def create_folder(name, parent_chain=()):
    at = f" at ({folder_ref(parent_chain)})" if parent_chain else ""
    script = f'''
tell application "Photos"
    set f to make new folder named {as_str(name)}{at}
    return (id of f as text)
end tell'''
    return osascript(script)


def ensure_folder(name, parent_chain=()):
    found = find_folders(name, parent_chain)
    if found:
        return found[0], False
    return create_folder(name, parent_chain), True


def find_albums(name, parent_chain):
    script = f'''
tell application "Photos"
    set out to {{}}
    repeat with a in (albums of ({folder_ref(parent_chain)}))
        if name of a is {as_str(name)} then set end of out to (id of a as text)
    end repeat
    set AppleScript's text item delimiters to linefeed
    return out as text
end tell'''
    return _lines(osascript(script))


def create_album(name, parent_chain):
    script = f'''
tell application "Photos"
    set a to make new album named {as_str(name)} at ({folder_ref(parent_chain)})
    return (id of a as text)
end tell'''
    return osascript(script)


def album_item_ids(album_id):
    script = f'''
tell application "Photos"
    set ids to id of media items of album id {as_str(album_id)}
    set AppleScript's text item delimiters to linefeed
    return ids as text
end tell'''
    return set(_lines(osascript(script)))


def album_count(album_id):
    return int(osascript(f"""
tell application "Photos"
    return (count of media items of album id {as_str(album_id)}) as text
end tell""") or 0)


def _add_batch(album_id, item_ids):
    lst = ", ".join(as_str(i) for i in item_ids)
    script = f'''
tell application "Photos"
    set theAlbum to album id {as_str(album_id)}
    set theItems to {{}}
    repeat with u in {{{lst}}}
        set end of theItems to (media item id (contents of u))
    end repeat
    add theItems to theAlbum
    return (count of media items of theAlbum) as text
end tell'''
    osascript(script)


def album_add(album_id, uuids, batch_size=150, on_progress=None):
    """Add photos by uuid. A batch that fails is split until the failing
    items are isolated and reported, so one missing photo cannot sink a run."""
    wanted = [u if u.endswith(ITEM_SUFFIX) else u + ITEM_SUFFIX for u in uuids]
    failed = []
    done = 0

    def add(chunk):
        nonlocal done
        try:
            _add_batch(album_id, chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done)
        except PhotosError as err:
            if len(chunk) == 1:
                failed.append((chunk[0][: -len(ITEM_SUFFIX)], str(err)[:160]))
                return
            mid = len(chunk) // 2
            add(chunk[:mid])
            add(chunk[mid:])

    for i in range(0, len(wanted), batch_size):
        add(wanted[i:i + batch_size])
    present = album_item_ids(album_id)
    missing = [w[: -len(ITEM_SUFFIX)] for w in wanted if w not in present]
    return {"requested": len(wanted), "in_album": len(present), "missing_after_add": missing, "failed": failed}


def delete_album(album_id):
    osascript(f"""
tell application "Photos"
    delete album id {as_str(album_id)}
end tell""")


def delete_folder_if_empty(chain):
    """Photos refuses to delete a nested folder through any scripted reference,
    so a nested chain is left to go with its top folder. A top-level folder is
    deleted once no album remains anywhere beneath it."""
    if len(chain) > 1:
        return "kept, nested folders leave with their top folder"
    script = f'''
on albumsBeneath(f)
    tell application "Photos"
        set n to count of albums of f
        repeat with s in folders of f
            set n to n + (my albumsBeneath(s))
        end repeat
        return n
    end tell
end albumsBeneath

tell application "Photos"
    set f to ({folder_ref(chain)})
    if (my albumsBeneath(f)) is 0 then
        delete f
        return "deleted"
    end if
    return "kept"
end tell'''
    return osascript(script)


def tree(top_name):
    script = f'''
tell application "Photos"
    set out to {{}}
    repeat with f in folders
        if name of f is {as_str(top_name)} then
            set end of out to "FOLDER " & (name of f)
            repeat with a in albums of f
                set end of out to "  ALBUM " & (name of a) & " | " & (count of media items of a) & " | " & (id of a as text)
            end repeat
            repeat with g in folders of f
                set end of out to "  FOLDER " & (name of g)
                repeat with a in albums of g
                    set end of out to "    ALBUM " & (name of a) & " | " & (count of media items of a) & " | " & (id of a as text)
                end repeat
            end repeat
        end if
    end repeat
    set AppleScript's text item delimiters to linefeed
    return out as text
end tell'''
    return osascript(script)


def probe(cfg):
    name = cfg["apply"]["photos_folder"] + " probe"
    print(f"probe: folder {name!r}")
    t0 = time.monotonic()
    one = osascript("""
tell application "Photos"
    return (id of media item 1) as text
end tell""")
    print(f"  one media item id: {one}  ({time.monotonic()-t0:.1f}s)")
    fid, _ = ensure_folder(name)
    print(f"  folder id: {fid}")
    sub, _ = ensure_folder("Events", (fid,))
    print(f"  subfolder id: {sub}")
    aid = create_album("Probe album", (fid, sub))
    print(f"  album id: {aid}")
    res = album_add(aid, [one[: -len(ITEM_SUFFIX)] if one.endswith(ITEM_SUFFIX) else one])
    print(f"  add: {res}")
    ok = res["in_album"] >= 1 and not res["missing_after_add"]
    delete_album(aid)
    print(f"  album removed; probe folder {delete_folder_if_empty((fid,))}")
    print("PASS" if ok else "FAIL: the photo did not land in the album")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--library-info", action="store_true")
    args = ap.parse_args(argv)
    cfg = C.load_config(args.config)
    try:
        if args.probe:
            return probe(cfg)
        if args.tree:
            print(tree(cfg["apply"]["photos_folder"]) or "(no Hermes Tidy folder yet)")
            return 0
        if args.library_info:
            print(library_info(cfg))
            return 0
    except PhotosError as err:
        print(f"FAIL: {err}")
        return 1
    ap.print_help()
    return 5


if __name__ == "__main__":
    sys.exit(main())
