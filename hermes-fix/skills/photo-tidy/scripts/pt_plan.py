#!/usr/bin/env python3
"""Turn an inventory into a plan: junk candidates with reasons, duplicate
groups with a keeper, events split by time gaps and location jumps, a place
per event, and a name per event (local Ollama model, rule-based fallback).
Writes plan.json. Moves nothing.

  python3 pt_plan.py                         # newest run, foreground
  python3 pt_plan.py --run-dir DIR --background
  python3 pt_plan.py --wait DIR [--seconds 110]
  python3 pt_plan.py --no-llm                # rule names only, no Ollama call
  python3 pt_plan.py --compare-prior         # also match duplicates against earlier runs (the watcher does this)

Exit 0 done, 1 error, 3 still running (--wait only), 5 usage error.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pt_common as C  # noqa: E402

C.ensure_venv()


# ----------------------------------------------------------------------------- records

def prep(r):
    dt = C.parse_iso(r.get("date"))
    r["_dt"] = dt
    r["_ts"] = dt.timestamp() if dt else None
    r["_local"] = dt.replace(tzinfo=None) if dt else None
    r["_labels"] = [str(l).lower() for l in (r.get("labels") or [])]
    r["_aspect"] = (r["w"] / r["h"]) if r.get("w") and r.get("h") else None
    return r


# ----------------------------------------------------------------------------- junk

def burst_groups(recs):
    """Burst photos, grouped by near-identical capture time and size."""
    groups = []
    cur = []
    for r in sorted((x for x in recs if x.get("burst") and x["_ts"]), key=lambda x: x["_ts"]):
        if cur and (r["_ts"] - cur[-1]["_ts"] > 3 or (r["w"], r["h"]) != (cur[-1]["w"], cur[-1]["h"])):
            groups.append(cur)
            cur = []
        cur.append(r)
    if cur:
        groups.append(cur)
    return groups


def blur_cutoff(recs, J):
    """Laplacian variance depends on content, so the cutoff is relative: the
    bottom blur_percentile of the run, kept between blur_threshold and blur_cap."""
    vals = sorted(r["blur"] for r in recs if r.get("blur") is not None and r["kind"] == "photo"
                  and not r.get("screenshot") and (r.get("lum_std") or 0) >= float(J["flat_std"]))
    floor, cap = float(J["blur_threshold"]), float(J.get("blur_cap", 100))
    if len(vals) < 20:
        return min(cap, max(floor, vals[max(0, len(vals) // 20)] if vals else floor))
    pct = vals[int(len(vals) * float(J.get("blur_percentile", 5)) / 100)]
    return min(cap, max(floor, pct))


def find_junk(recs, cfg, led):
    J = cfg["junk"]
    now = C.now_local()
    out = []
    cutoff = blur_cutoff(recs, J)
    burst_extra = set()
    if J.get("burst_extras"):
        for g in burst_groups(recs):
            if len(g) > 1 and any(x.get("burst_selected") or x.get("burst_key") for x in g):
                for x in g:
                    if not (x.get("burst_selected") or x.get("burst_key")):
                        burst_extra.add(x["id"])
    skipped_fav = 0
    for r in recs:
        reasons = []
        sc = r.get("score") or {}
        if r["kind"] == "photo":
            if J.get("screenshots") and r.get("screenshot"):
                age = (now - r["_dt"]).days if r["_dt"] else 9999
                if age >= int(J.get("screenshot_min_age_days", 0)):
                    reasons.append(("screenshot", "high"))
            hit = next((l for l in r["_labels"] for j in J.get("labels", []) if j in l), None)
            if hit:
                reasons.append((f"document-like: {hit}", "medium"))
            w, h = r.get("w") or 0, r.get("h") or 0
            small_px = bool(w and h and max(w, h) < int(J["min_px"]))
            small_bytes = bool(r.get("bytes") and r["bytes"] < int(J["min_bytes"]) and (not w or max(w, h) < 1000))
            if small_px or small_bytes:
                reasons.append(("tiny", "high"))
            if r.get("lum_mean") is not None and not r.get("screenshot"):
                if r["lum_mean"] < J["dark_mean"] and r["lum_std"] < J["flat_std"]:
                    reasons.append(("near-black", "high"))
                elif r["lum_mean"] > J["bright_mean"] and r["lum_std"] < J["flat_std"]:
                    reasons.append(("near-white", "high"))
            if (r.get("blur") is not None and r["blur"] < cutoff and not r.get("screenshot") and not hit
                    and (r.get("lum_std") or 0) >= float(J["flat_std"]) and sc.get("sharp", 0) < 0.5):
                reasons.append(("blurry", "medium"))
            if sc.get("failure") is not None and sc["failure"] >= float(J["failure_score"]):
                reasons.append((f"photos failure score {sc['failure']:.2f}", "medium"))
            if r["id"] in burst_extra:
                reasons.append(("burst extra", "medium"))
        else:
            if J.get("screen_recordings") and r.get("screen_recording"):
                reasons.append(("screen recording", "medium"))
        if reasons and r.get("favorite"):
            skipped_fav += 1
            continue
        if reasons:
            conf = "high" if any(c == "high" for _, c in reasons) else "medium"
            out.append({"id": r["id"], "reasons": [x for x, _ in reasons], "confidence": conf})
    by_reason = Counter(re.sub(r"[:\s].*$", "", x) for j in out for x in j["reasons"])
    led.add("junk", "COMPLETE", f"{len(out)} candidates; {skipped_fav} favorites left alone; blur cutoff {cutoff:.0f}; " + ", ".join(f"{k} {v}" for k, v in by_reason.most_common()))
    return out


# ----------------------------------------------------------------------------- duplicates

class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


NEAR_MIN_STD = 6.0   # a frame flatter than this has no structure to hash


def _pair_ok(a, b, D):
    if a.get("screenshot") or b.get("screenshot"):
        return None
    if (a.get("lum_std") is not None and a["lum_std"] < NEAR_MIN_STD) or (b.get("lum_std") is not None and b["lum_std"] < NEAR_MIN_STD):
        return None
    if a["kind"] != b["kind"] or a["kind"] == "video":
        return None
    if a["_aspect"] and b["_aspect"] and abs(a["_aspect"] - b["_aspect"]) / max(a["_aspect"], b["_aspect"]) > 0.25:
        return None
    d = C.hamming_hex(a.get("phash"), b.get("phash"))
    if d > int(D["phash_max_distance"]):
        return None
    if C.hamming_hex(a.get("dhash"), b.get("dhash")) > int(D["dhash_max_distance"]):
        return None
    return d


COPY_MARK = re.compile(r"copy|\(\d+\)|whatsapp|-wa\d|resent|\bimage\b|telegram|messenger", re.I)


def keep_rank(r):
    added = C.parse_iso(r.get("date_added"))
    return (bool(r.get("favorite")), bool(r.get("burst_selected") or r.get("burst_key")), r.get("lat") is not None,
            not r.get("missing"), r.get("bytes") or 0, (r.get("w") or 0) * (r.get("h") or 0),
            not COPY_MARK.search(r.get("name") or ""), -(added.timestamp() if added else 0), -len(r.get("name") or ""))


def find_dups(recs, cfg, led, prior=None):
    D = cfg["duplicates"]
    uf = UF()
    dist = {}
    exact_pairs = set()
    by_id = {r["id"]: r for r in recs}

    def mark(a, b, d, exact=False):
        uf.union(a, b)
        key = tuple(sorted((a, b)))
        dist[key] = min(d, dist.get(key, 99))
        if exact:
            exact_pairs.add(key)

    if D.get("use_photos_fingerprint"):
        by_fp = defaultdict(list)
        for r in recs:
            if r.get("fingerprint"):
                by_fp[r["fingerprint"]].append(r["id"])
        for ids in by_fp.values():
            for a, b in zip(ids, ids[1:]):
                mark(a, b, 0, exact=True)
    by_sig = defaultdict(list)
    for r in recs:
        if r.get("phash") and r.get("bytes"):
            by_sig[(r["bytes"], r["phash"], round(r.get("lum_mean") or 0))].append(r["id"])
    for ids in by_sig.values():
        for a, b in zip(ids, ids[1:]):
            mark(a, b, 0, exact=True)

    hashed = [r for r in recs if r.get("phash") and r["kind"] == "photo" and not r.get("screenshot")]
    bands = defaultdict(list)
    for i, r in enumerate(hashed):
        h = int(r["phash"], 16)
        for b in range(8):
            bands[(b, (h >> (8 * b)) & 0xFF)].append(i)
    seen = set()
    for idxs in bands.values():
        if len(idxs) < 2 or len(idxs) > 400:
            continue
        for i, j in combinations(idxs, 2):
            if (i, j) in seen:
                continue
            seen.add((i, j))
            d = _pair_ok(hashed[i], hashed[j], D)
            if d is not None:
                mark(hashed[i]["id"], hashed[j]["id"], d)
    window = float(D["time_window_hours"]) * 3600
    nb = int(D["neighbor_window"])
    timed = sorted((r for r in hashed if r["_ts"]), key=lambda r: r["_ts"])
    for i in range(len(timed)):
        for j in range(i + 1, min(len(timed), i + 1 + nb)):
            if timed[j]["_ts"] - timed[i]["_ts"] > window:
                break
            d = _pair_ok(timed[i], timed[j], D)
            if d is not None:
                mark(timed[i]["id"], timed[j]["id"], d)

    prior_hits = 0
    if prior:
        pbands = defaultdict(list)
        pfp = {}
        for pid, pr in prior.items():
            if pr.get("fingerprint"):
                pfp.setdefault(pr["fingerprint"], pid)
            if pr.get("phash"):
                h = int(pr["phash"], 16)
                for b in range(8):
                    pbands[(b, (h >> (8 * b)) & 0xFF)].append(pid)
        for r in recs:
            if r.get("fingerprint") and r["fingerprint"] in pfp:
                prior_hits += 1
                mark(pfp[r["fingerprint"]], r["id"], 0, exact=True)
                continue
            if not r.get("phash") or r.get("screenshot"):
                continue
            h = int(r["phash"], 16)
            cands = set()
            for b in range(8):
                cands.update(pbands.get((b, (h >> (8 * b)) & 0xFF), ()))
            for pid in cands:
                pr = dict(prior[pid])
                pr.setdefault("kind", "photo")
                pr["_aspect"] = None
                d = _pair_ok(pr, r, D)
                if d is not None:
                    prior_hits += 1
                    mark(pid, r["id"], d)

    members = defaultdict(list)
    for x in list(uf.p):
        members[uf.find(x)].append(x)
    groups = []
    for ids in members.values():
        if len(ids) < 2:
            continue
        inrun = [by_id[i] for i in ids if i in by_id]
        if not inrun:
            continue
        prior_ids = [i for i in ids if i not in by_id]
        if prior_ids:
            keep = prior_ids[0]
            others = [r["id"] for r in inrun]
        else:
            inrun.sort(key=keep_rank, reverse=True)
            keep = inrun[0]["id"]
            others = [r["id"] for r in inrun[1:]]
        pairs = [tuple(sorted((a, b))) for a, b in combinations(ids, 2) if tuple(sorted((a, b))) in dist]
        maxd = max((dist[p] for p in pairs), default=0)
        exact = bool(pairs) and all(p in exact_pairs for p in pairs)
        groups.append({"gid": "", "kind": "exact" if exact else "near", "keep": keep, "others": others,
                       "distance": maxd, "n": len(ids), "prior_keep": bool(prior_ids)})
    groups.sort(key=lambda g: (g["kind"] != "exact", g["distance"], -g["n"],
                               (by_id.get(g["keep"]) or {}).get("date") or "", (by_id.get(g["keep"]) or {}).get("name") or ""))
    for i, g in enumerate(groups):
        g["gid"] = f"d{i+1:05d}"
    n_exact = sum(1 for g in groups if g["kind"] == "exact")
    led.add("duplicates", "COMPLETE", f"{len(groups)} groups ({n_exact} exact, {len(groups)-n_exact} near), {sum(len(g['others']) for g in groups)} photos to review" + (f", {prior_hits} matched earlier runs" if prior else ""))
    return groups


def load_prior(cfg, run_dir, n):
    prior = {}
    for d in C.list_runs(cfg, "inventory.jsonl"):
        if os.path.abspath(d) == os.path.abspath(run_dir):
            continue
        if n <= 0:
            break
        n -= 1
        for r in C.read_jsonl(os.path.join(d, "inventory.jsonl")):
            prior.setdefault(r["id"], {"phash": r.get("phash"), "dhash": r.get("dhash"), "fingerprint": r.get("fingerprint"),
                                       "bytes": r.get("bytes"), "w": r.get("w"), "h": r.get("h"), "run": os.path.basename(d),
                                       "thumb": r.get("thumb"), "name": r.get("name"), "date": r.get("date")})
    return prior


# ----------------------------------------------------------------------------- embeddings (optional refinement)

def ollama_post(url, path, payload, timeout):
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def embed_thumbs(cfg, paths):
    E = cfg["embeddings"]
    items = []
    for p in paths:
        with open(p, "rb") as fh:
            items.append({"image": base64.b64encode(fh.read()).decode("ascii")})
    res = ollama_post(cfg["naming"]["ollama_url"], "/api/embed", {"model": E["model"], "input": items}, E["timeout_seconds"])
    vecs = res.get("embeddings") or []
    if len(vecs) != len(paths):
        raise ValueError(f"embed returned {len(vecs)} vectors for {len(paths)} images")
    return vecs


def cosine(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(x * x for x in b)) or 1.0
    return num / (da * db)


def refine_with_embeddings(groups, recs, cfg, led, status, tdir):
    E = cfg["embeddings"]
    by_id = {r["id"]: r for r in recs}
    near = [g for g in groups if g["kind"] == "near" and not g["prior_keep"]]
    if not near:
        led.add("embeddings", "SKIPPED", "no near-duplicate groups to refine")
        return groups
    probe_path = None
    for g in near:
        r = by_id.get(g["keep"])
        if r and r.get("thumb"):
            probe_path = os.path.join(tdir, r["thumb"])
            break
    try:
        embed_thumbs(cfg, [probe_path])
    except Exception as err:
        led.add("embeddings", "BLOCKED", f"{E['model']} via Ollama did not return an image embedding ({str(err)[:120]}); perceptual hashes only")
        return groups
    vec = {}
    pending = []
    for g in near:
        for i in [g["keep"]] + g["others"]:
            r = by_id.get(i)
            if r and r.get("thumb") and i not in vec:
                pending.append(i)
    for k in range(0, len(pending), 16):
        chunk = pending[k:k + 16]
        try:
            vs = embed_thumbs(cfg, [os.path.join(tdir, by_id[i]["thumb"]) for i in chunk])
        except Exception as err:
            led.add("embeddings", "PARTIAL", f"stopped after {k} images: {str(err)[:120]}")
            break
        for i, v in zip(chunk, vs):
            vec[i] = v
        status.update(phase="embeddings", done=min(k + 16, len(pending)), total=len(pending))
    split = 0
    out = []
    for g in groups:
        if g not in near or g["keep"] not in vec:
            out.append(g)
            continue
        kept, dropped = [], []
        for o in g["others"]:
            if o in vec and cosine(vec[g["keep"]], vec[o]) < float(E["min_cosine"]):
                dropped.append(o)
            else:
                kept.append(o)
        if dropped:
            split += len(dropped)
            g["dropped_by_embedding"] = dropped
        g["others"] = kept
        g["n"] = 1 + len(kept)
        if kept:
            out.append(g)
    led.add("embeddings", "COMPLETE", f"{len(vec)} images embedded with {E['model']}; {split} weak matches removed from near groups")
    return out


# ----------------------------------------------------------------------------- events

def build_events(recs, cfg, led):
    E = cfg["events"]
    gap = float(E["gap_hours"]) * 3600
    jump = float(E["location_jump_km"])
    dated = sorted((r for r in recs if r["_ts"]), key=lambda r: r["_ts"])
    undated = [r for r in recs if not r["_ts"]]
    events = []
    cur = []
    last_gps = None

    def flush():
        if cur:
            events.append(list(cur))
        cur.clear()

    for r in dated:
        if cur:
            dt = r["_ts"] - cur[-1]["_ts"]
            far = False
            if r.get("lat") is not None and last_gps and dt > 3600:
                far = C.haversine_km(last_gps[0], last_gps[1], r["lat"], r["lon"]) > jump
            if dt > gap or far:
                flush()
                last_gps = None
        cur.append(r)
        if r.get("lat") is not None:
            last_gps = (r["lat"], r["lon"])
    flush()

    min_n = int(E["min_event_photos"])
    buckets = {}
    final = []
    for ev in events:
        if len(ev) < min_n and E.get("small_event_bucket") == "month":
            key = ev[0]["_local"].strftime("%Y-%m")
            buckets.setdefault(key, []).extend(ev)
        else:
            final.append({"recs": ev, "bucket": False})
    for key in sorted(buckets):
        final.append({"recs": sorted(buckets[key], key=lambda r: r["_ts"]), "bucket": True, "month": key})
    if undated:
        final.append({"recs": undated, "bucket": True, "month": "undated"})
    final.sort(key=lambda e: (e["recs"][0]["_ts"] or 0))
    out = []
    for i, e in enumerate(final):
        rs = e["recs"]
        labels = Counter(l for r in rs for l in r["_labels"][:6])
        persons = Counter(p for r in rs for p in (r.get("persons") or []))
        start = rs[0]["_local"]
        end = rs[-1]["_local"]
        out.append({
            "eid": f"e{i+1:04d}", "ids": [r["id"] for r in rs],
            "start": start.isoformat(timespec="seconds") if start else None,
            "end": end.isoformat(timespec="seconds") if end else None,
            "n": len(rs), "n_videos": sum(1 for r in rs if r["kind"] == "video"),
            "bucket": bool(e["bucket"]), "month": e.get("month"),
            "labels_top": [k for k, _ in labels.most_common(8)],
            "persons_top": [k for k, _ in persons.most_common(5)],
            "home_share": round(sum(1 for r in rs if r.get("home")) / len(rs), 2),
            "favorites": sum(1 for r in rs if r.get("favorite")),
            "place": {}, "name": "", "name_src": "", "title": "",
        })
    n_real = sum(1 for e in out if not e["bucket"])
    led.add("events", "COMPLETE", f"{n_real} events from {len(dated)} dated items (gap {E['gap_hours']}h, jump {E['location_jump_km']}km); {len(out)-n_real} monthly buckets hold the events under {min_n} photos; {len(undated)} undated")
    return out


def tidy_ascii(name):
    """GeoNames ASCII names write a leading thorn as TH (THorlakshoefn)."""
    return re.sub(r"^TH(?=[a-z])", "Th", name or "")


def add_places(events, recs, cfg, led):
    P = cfg["places"]
    by_id = {r["id"]: r for r in recs}
    need_geo = []
    n_photos = n_geo = n_none = 0
    for ev in events:
        rs = [by_id[i] for i in ev["ids"]]
        cities = Counter()
        countries = Counter()
        states = Counter()
        if P.get("use_photos_places"):
            for r in rs:
                pl = r.get("place") or {}
                if pl.get("city"):
                    cities[pl["city"]] += 1
                if pl.get("state"):
                    states[pl["state"]] += 1
                if pl.get("country"):
                    countries[pl["country"]] += 1
        if cities or countries:
            ev["place"] = {"city": (cities.most_common(1) or [("", 0)])[0][0], "state": (states.most_common(1) or [("", 0)])[0][0],
                           "country": (countries.most_common(1) or [("", 0)])[0][0], "src": "photos"}
            n_photos += 1
            continue
        pts = [(r["lat"], r["lon"]) for r in rs if r.get("lat") is not None]
        if pts and P.get("offline_geocoder"):
            lat = statistics.median(p[0] for p in pts)
            lon = statistics.median(p[1] for p in pts)
            need_geo.append((ev, lat, lon))
        else:
            n_none += 1
    if need_geo:
        try:
            import reverse_geocoder as rg
            res = rg.search([(lat, lon) for _, lat, lon in need_geo], mode=1)
            from pt_countries import country_name
            for (ev, lat, lon), hit in zip(need_geo, res):
                ev["place"] = {"city": tidy_ascii(hit.get("name", "")), "state": tidy_ascii(hit.get("admin1", "")),
                               "country": country_name(hit.get("cc", "")), "country_code": hit.get("cc", ""), "src": "geonames"}
                n_geo += 1
        except Exception as err:
            led.add("places", "PARTIAL", f"offline geocoder unavailable ({type(err).__name__}: {str(err)[:80]}); {len(need_geo)} events keep coordinates only")
            n_none += len(need_geo)
            for ev, lat, lon in need_geo:
                ev["place"] = {"city": "", "state": "", "country": "", "lat": round(lat, 4), "lon": round(lon, 4), "src": "gps"}
    led.add("places", "COMPLETE", f"from Photos {n_photos}, from GeoNames {n_geo}, none {n_none}")


# ----------------------------------------------------------------------------- names

def rule_name(ev, cfg):
    if ev["bucket"]:
        return "Undated" if ev.get("month") == "undated" else f"Odds and ends {ev['month']}"
    pl = ev.get("place") or {}
    place = pl.get("city") or pl.get("state") or pl.get("country") or ""
    if ev.get("home_share", 0) >= 0.6 and not place:
        place = cfg["naming"].get("home_label", "Home")
    parts = []
    if place:
        parts.append(place)
    elif ev["labels_top"]:
        parts.append(", ".join(l.title() for l in ev["labels_top"][:2]))
    if ev["persons_top"]:
        parts.append("with " + " and ".join(ev["persons_top"][:2]))
    return C.safe_name(" ".join(parts) or "Photos", 60)


def parse_name(content):
    """The model answers JSON when asked for it, else a line of text, and
    sometimes JSON wrapped in prose or a code fence."""
    text = (content or "").strip()
    m = re.search(r"\{.*?\}", text, re.S)
    if m:
        try:
            v = json.loads(m.group(0)).get("name")
            if v:
                return v
        except ValueError:
            pass
    text = re.sub(r"^```\w*|```$", "", text).strip()
    return text.splitlines()[0] if text else ""


def clean_name(s):
    s = re.sub(r"[\"'`*#_\[\]{}<>|\\/]", " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" .,-:;")
    s = re.sub(r"^(20\d{2}[-/.]\d{1,2}([-/.]\d{1,2})?)\s*", "", s)
    words = s.split()
    if not (1 <= len(words) <= 7):
        return ""
    return " ".join(w if (w.isupper() and len(w) <= 4) else w[:1].upper() + w[1:] for w in words)


SYSTEM = ("You name photo albums. Reply with JSON only: {\"name\": \"...\"}. The name is 2 to 5 words, Title Case, "
          "plain English, no dates, no quotes, no emoji. Name the occasion or the place and activity, like "
          "'Beach Day in Sharm', 'Family Iftar', 'Tundra Brake Job', 'Walk Around Old Cairo'. "
          "If the evidence is thin, name the place and the main subject. Never invent a person or an occasion the evidence does not support.")


def event_prompt(ev):
    pl = ev.get("place") or {}
    start = datetime.fromisoformat(ev["start"]) if ev.get("start") else None
    end = datetime.fromisoformat(ev["end"]) if ev.get("end") else None
    lines = []
    if start:
        lines.append(f"When: {start:%A %Y-%m-%d %H:%M}" + (f" to {end:%A %Y-%m-%d %H:%M}" if end and end.date() != start.date() else (f" to {end:%H:%M}" if end else "")))
    where = ", ".join(x for x in (pl.get("city"), pl.get("state"), pl.get("country")) if x)
    if where:
        lines.append(f"Where: {where}")
    if ev.get("home_share", 0) >= 0.6:
        lines.append("At home: yes")
    lines.append(f"Count: {ev['n']} items, {ev['n_videos']} videos, {ev.get('favorites', 0)} favorites")
    if ev["labels_top"]:
        lines.append("Photos app labels: " + ", ".join(ev["labels_top"]))
    if ev["persons_top"]:
        lines.append("People tagged: " + ", ".join(ev["persons_top"]))
    return "\n".join(lines)


def signature(ev):
    return C.sha256_text(json.dumps([ev.get("start"), ev.get("end"), ev.get("place"), ev["labels_top"], ev["persons_top"], ev["n"]], sort_keys=True))[:24]


NO_FORMAT = {"flag": False}


def chat_name(N, ev):
    """One naming call. Some Ollama runners answer 501 "structured output is
    unavailable" to format=json; the call is then repeated without it, and
    later calls skip it from the start."""
    payload = {
        "model": N["model"], "stream": False, "think": False,
        "options": {"temperature": 0.2, "num_predict": 80},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": event_prompt(ev)}],
    }
    if not NO_FORMAT["flag"]:
        payload["format"] = "json"
    try:
        return ollama_post(N["ollama_url"], "/api/chat", payload, N["timeout_seconds"])
    except urllib.error.HTTPError as err:
        body = ""
        try:
            body = err.read().decode("utf-8", "replace")
        except Exception:
            pass
        if "format" in payload and (err.code == 501 or "structured output" in body.lower() or "format" in body.lower()):
            NO_FORMAT["flag"] = True
            payload.pop("format", None)
            return ollama_post(N["ollama_url"], "/api/chat", payload, N["timeout_seconds"])
        raise


def name_events(events, cfg, led, status, no_llm):
    N = cfg["naming"]
    cache_path = os.path.join(cfg["run_root"], "names_cache.json")
    cache = C.read_json(cache_path, {}) or {}
    n_llm = n_rule = n_cache = 0
    llm_ok = bool(N.get("enabled")) and not no_llm
    blocked = ""
    todo = [e for e in events if not e["bucket"]]
    if llm_ok and len(todo) > int(N.get("max_events", 1500)):
        blocked = f"{len(todo)} events exceed naming.max_events {N['max_events']}; rule names used"
        llm_ok = False
    for k, ev in enumerate(events):
        ev["name_rule"] = rule_name(ev, cfg)
        if ev["bucket"]:
            ev["name"], ev["name_src"] = ev["name_rule"], "rule"
        else:
            sig = signature(ev)
            if sig in cache and cache[sig].get("name"):
                ev["name"], ev["name_src"] = cache[sig]["name"], "cache"
                n_cache += 1
            elif llm_ok:
                try:
                    res = chat_name(N, ev)
                    content = (res.get("message") or {}).get("content") or ""
                    name = clean_name(parse_name(content))
                    if name:
                        ev["name"], ev["name_src"] = name, "ollama"
                        cache[sig] = {"name": name, "model": N["model"], "at": C.iso(C.now_local())}
                        n_llm += 1
                        if n_llm % 10 == 0:
                            C.write_json(cache_path, cache)
                    else:
                        ev["name"], ev["name_src"] = ev["name_rule"], "rule"
                        n_rule += 1
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as err:
                    blocked = f"Ollama at {N['ollama_url']} with {N['model']}: {str(err)[:120]}; rule names used from event {ev['eid']}"
                    llm_ok = False
                    ev["name"], ev["name_src"] = ev["name_rule"], "rule"
                    n_rule += 1
            else:
                ev["name"], ev["name_src"] = ev["name_rule"], "rule"
                n_rule += 1
        start = ev.get("start")
        prefix = start[:10] if start else (ev.get("month") or "undated")
        ev["title"] = C.safe_name(f"{prefix} {ev['name']}", 90)
        if k % 5 == 0:
            status.update(phase="naming", done=k, total=len(events), msg=f"ollama {n_llm}, cache {n_cache}, rule {n_rule}")
    C.write_json(cache_path, cache)
    led.add("naming", "BLOCKED" if blocked and n_llm == 0 else ("PARTIAL" if blocked else "COMPLETE"),
            (blocked + "; " if blocked else "") + f"ollama {n_llm}, cached {n_cache}, rule {n_rule}")


# ----------------------------------------------------------------------------- main

def run_plan(args, cfg):
    run_dir = args.run_dir
    inv_path = os.path.join(run_dir, "inventory.jsonl")
    if not os.path.exists(inv_path):
        print(f"ERROR: no inventory.jsonl in {run_dir}; run pt_scan.py first", file=sys.stderr)
        return 5
    status = C.Status(os.path.join(run_dir, "plan.status.json"), phase="loading")
    led = C.Ledger()
    t0 = time.monotonic()
    try:
        recs = [prep(r) for r in C.read_jsonl(inv_path)]
        if not args.include_applied:
            import pt_apply
            placed = set()
            for d in C.list_runs(cfg, "apply.log.jsonl"):
                if os.path.abspath(d) != os.path.abspath(run_dir):
                    placed |= pt_apply.placed_ids(d)
            if placed:
                before = len(recs)
                recs = [r for r in recs if r["id"] not in placed]
                led.add("already organised", "COMPLETE", f"{before - len(recs)} items are in albums or folders from earlier applies and are left out (--include-applied overrides)")
        status.update(phase="junk", total=len(recs), force=True)
        junk = find_junk(recs, cfg, led)
        status.update(phase="duplicates", force=True)
        prior = load_prior(cfg, run_dir, int(cfg["watch"].get("compare_prior_runs", 3))) if args.compare_prior else None
        dups = find_dups(recs, cfg, led, prior)
        if cfg["embeddings"].get("enabled") and not args.no_embed:
            dups = refine_with_embeddings(dups, recs, cfg, led, status, C.thumbs_dir(cfg))
        else:
            led.add("embeddings", "SKIPPED", "embeddings.enabled is false" if not args.no_embed else "--no-embed")
        status.update(phase="events", force=True)
        events = build_events(recs, cfg, led)
        status.update(phase="places", force=True)
        add_places(events, recs, cfg, led)
        status.update(phase="naming", total=len(events), force=True)
        name_events(events, cfg, led, status, args.no_llm)
    except Exception as err:
        status.finish(False, f"{type(err).__name__}: {err}")
        print(f"ERROR: plan failed: {type(err).__name__}: {err}", file=sys.stderr)
        raise
    prior_refs = {}
    if prior:
        for g in dups:
            if g["prior_keep"] and g["keep"] in prior:
                prior_refs[g["keep"]] = prior[g["keep"]]
    junk_ids = {j["id"] for j in junk}
    dup_other_ids = {o for g in dups for o in g["others"]}
    plan = {
        "created_at": C.iso(C.now_local()), "run_dir": run_dir, "mode": cfg["source"]["mode"],
        "seconds": round(time.monotonic() - t0),
        "counts": {"items": len(recs), "junk": len(junk), "dup_groups": len(dups), "dup_photos": len(dup_other_ids),
                   "events": sum(1 for e in events if not e["bucket"]), "buckets": sum(1 for e in events if e["bucket"]),
                   "both_junk_and_dup": len(junk_ids & dup_other_ids)},
        "settings": {"events": cfg["events"], "junk": cfg["junk"], "duplicates": cfg["duplicates"], "naming": {k: v for k, v in cfg["naming"].items()}},
        "junk": junk, "dups": dups, "events": events, "prior_refs": prior_refs, "ledger": led.rows,
    }
    for ev in events:
        ev.pop("recs", None)
    C.write_json(os.path.join(run_dir, "plan.json"), plan)
    status.finish(True, "plan written", result=plan["counts"])
    c = plan["counts"]
    names = Counter(e["name_src"] for e in events if not e["bucket"])
    print(f"PLAN={os.path.join(run_dir, 'plan.json')}")
    print(f"RUN_DIR={run_dir}")
    print(f"SUMMARY items={c['items']} events={c['events']} buckets={c['buckets']} junk={c['junk']} dup_groups={c['dup_groups']} dup_photos={c['dup_photos']} names=" + ",".join(f"{k}:{v}" for k, v in names.items()))
    sample = [e["title"] for e in events if not e["bucket"]][:8]
    if sample:
        print("SAMPLE_EVENTS: " + " | ".join(sample))
    print("LEDGER:")
    for line in led.lines():
        print("  " + line)
    print(f"NEXT=python3 {os.path.join(C.HERE, 'pt_review.py')} serve --run-dir {run_dir} --background")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--run-dir")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--compare-prior", action="store_true")
    ap.add_argument("--include-applied", action="store_true", help="also plan items an earlier run already put in albums")
    ap.add_argument("--background", action="store_true")
    ap.add_argument("--wait", metavar="RUN_DIR")
    ap.add_argument("--seconds", type=int, default=110)
    args = ap.parse_args(argv)
    if args.wait:
        data, rc = C.wait_status(os.path.join(C.expand(args.wait), "plan.status.json"), args.seconds, "plan")
        if rc == 0:
            print(f"RUN_DIR={C.expand(args.wait)}")
            print(f"NEXT=python3 {os.path.join(C.HERE, 'pt_review.py')} serve --run-dir {C.expand(args.wait)} --background")
        elif rc == 3:
            print(f"NEXT=python3 {os.path.abspath(__file__)} --wait {C.expand(args.wait)} --seconds {args.seconds}")
        return rc
    cfg = C.load_config(args.config)
    args.run_dir = C.resolve_run_dir(cfg, args, "inventory.jsonl")
    if args.background:
        extra = [a for a in (argv if argv is not None else sys.argv[1:]) if a != "--background"]
        if "--run-dir" in extra:
            i = extra.index("--run-dir")
            del extra[i:i + 2]
        return C.background_launch(os.path.abspath(__file__), args.run_dir, extra, "plan.status.json", "plan.log")
    return run_plan(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
