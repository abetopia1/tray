#!/usr/bin/env python3
"""Make a folder of synthetic photos with EXIF dates and GPS so the folder
pipeline can be exercised without a real photo. Scenes are random shapes.

  python3 make_fixture.py OUT_DIR
"""
from __future__ import annotations

import os
import random
import shutil
import sys
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFilter

random.seed(7)


def scene(seed, size=(1280, 960)):
    rnd = random.Random(seed)
    img = Image.new("RGB", size, tuple(rnd.randint(40, 220) for _ in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(40):
        x0, y0 = rnd.randint(0, size[0]), rnd.randint(0, size[1])
        x1, y1 = x0 + rnd.randint(40, 400), y0 + rnd.randint(40, 400)
        col = tuple(rnd.randint(0, 255) for _ in range(3))
        (d.ellipse if rnd.random() < 0.5 else d.rectangle)([x0, y0, x1, y1], fill=col)
    for _ in range(6):
        d.line([rnd.randint(0, size[0]), rnd.randint(0, size[1]), rnd.randint(0, size[0]), rnd.randint(0, size[1])], fill=(0, 0, 0), width=3)
    return img


def dms(v):
    v = abs(v)
    d = int(v)
    m = int((v - d) * 60)
    s = round((v - d - m / 60) * 3600, 2)
    return (float(d), float(m), float(s))


def exif_for(dt, lat=None, lon=None, offset="+02:00", camera=("Apple", "iPhone 15")):
    exif = Image.Exif()
    exif[0x010F], exif[0x0110] = camera
    exif[0x0132] = dt.strftime("%Y:%m:%d %H:%M:%S")
    ifd = exif.get_ifd(0x8769)
    ifd[0x9003] = dt.strftime("%Y:%m:%d %H:%M:%S")
    ifd[0x9011] = offset
    if lat is not None:
        gps = exif.get_ifd(0x8825)
        gps[1] = "N" if lat >= 0 else "S"
        gps[2] = dms(lat)
        gps[3] = "E" if lon >= 0 else "W"
        gps[4] = dms(lon)
    return exif.tobytes()


def save(img, path, dt, lat=None, lon=None, quality=88, **kw):
    img.save(path, "JPEG", quality=quality, exif=exif_for(dt, lat, lon, **kw))


def main(out):
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    n = 0
    events = [
        ("sharm", datetime(2024, 5, 10, 8, 0), 27.9158, 34.3300, 12, "+02:00"),
        ("cairo", datetime(2024, 5, 12, 17, 30), 30.0444, 31.2357, 8, "+02:00"),
        ("la_home", datetime(2024, 6, 1, 9, 15), 34.1522, -118.4437, 10, "-07:00"),
        ("tundra", datetime(2024, 6, 15, 14, 0), 34.1600, -118.4500, 6, "-07:00"),
        ("iceland_d1", datetime(2023, 9, 3, 10, 0), 64.1466, -21.9426, 5, "+00:00"),
        ("iceland_d2", datetime(2023, 9, 4, 9, 0), 63.9350, -21.4000, 5, "+00:00"),
        ("iceland_d3", datetime(2023, 9, 5, 11, 0), 64.0400, -16.1800, 5, "+00:00"),
    ]
    for name, start, lat, lon, count, off in events:
        for i in range(count):
            dt = start + timedelta(minutes=18 * i + random.randint(0, 9))
            img = scene(f"{name}-{i}")
            save(img, os.path.join(out, f"IMG_{name}_{i:02d}.jpg"), dt, lat + random.uniform(-0.002, 0.002), lon + random.uniform(-0.002, 0.002), offset=off)
            n += 1
    # exact duplicate (byte copy) and a renamed copy
    shutil.copyfile(os.path.join(out, "IMG_sharm_03.jpg"), os.path.join(out, "IMG_sharm_03 copy.jpg"))
    shutil.copyfile(os.path.join(out, "IMG_cairo_02.jpg"), os.path.join(out, "WhatsApp Image 2024-05-13 at 09.12.44.jpg"))
    # near duplicates: same scene, resized and recompressed, one with a tiny shift
    base = scene("sharm-5")
    near = base.resize((1152, 864)).filter(ImageFilter.GaussianBlur(0.4))
    save(near, os.path.join(out, "IMG_sharm_05_resent.jpg"), datetime(2024, 5, 10, 9, 40), 27.9158, 34.33, quality=60)
    shifted = Image.new("RGB", base.size, (90, 90, 90))
    shifted.paste(base, (4, 3))
    save(shifted, os.path.join(out, "IMG_sharm_05_shift.jpg"), datetime(2024, 5, 10, 9, 41), 27.9158, 34.33, quality=80)
    # junk: screenshots (no camera exif), tiny, black, white, blurry
    for i in range(3):
        img = Image.new("RGB", (1170, 2532), (245, 245, 245))
        d = ImageDraw.Draw(img)
        for y in range(0, 2532, 60):
            d.rectangle([40, y + 10, 1130, y + 40], fill=(200 + i, 200, 210))
        img.save(os.path.join(out, f"Screenshot 2024-03-0{i+1} at 10.1{i}.00.jpg"), "JPEG", quality=85)
    Image.new("RGB", (120, 90), (120, 200, 90)).save(os.path.join(out, "tiny_sticker.jpg"), "JPEG", exif=exif_for(datetime(2024, 4, 2, 12, 0)))
    for i in range(3):
        save(Image.new("RGB", (1280, 960), (random.randint(0, 6),) * 3), os.path.join(out, f"IMG_pocket_{i}.jpg"), datetime(2024, 4, 9, 20, i), 34.15, -118.44, offset="-07:00")
    for i in range(2):
        save(Image.new("RGB", (1280, 960), (250, 250, 250)), os.path.join(out, f"IMG_white_{i}.jpg"), datetime(2024, 4, 9, 21, i), 34.15, -118.44, offset="-07:00")
    for i in range(2):
        save(scene(f"blur-{i}").filter(ImageFilter.GaussianBlur(9)), os.path.join(out, f"IMG_blurry_{i}.jpg"), datetime(2024, 4, 11, 13, i), 34.15, -118.44, offset="-07:00")
    # stragglers: single photos on scattered days, should fold into monthly buckets
    for i, day in enumerate([3, 9, 17, 25]):
        save(scene(f"straggler-{i}"), os.path.join(out, f"IMG_misc_{i}.jpg"), datetime(2024, 2, day, 12, 0), 34.15, -118.44, offset="-07:00")
    # a file without any exif, and a fake video with a date in its name
    scene("noexif").save(os.path.join(out, "forwarded_meme.jpg"), "JPEG", quality=70)
    with open(os.path.join(out, "VID_20240512_183000.mp4"), "wb") as fh:
        fh.write(b"\x00" * 2048)
    # a nested folder, which the scanner must walk
    os.makedirs(os.path.join(out, "2024 Camera Roll"))
    save(scene("nested"), os.path.join(out, "2024 Camera Roll", "IMG_nested.jpg"), datetime(2024, 6, 1, 10, 0), 34.1522, -118.4437, offset="-07:00")
    total = sum(len(f) for _, _, f in os.walk(out))
    print(f"fixture: {total} files in {out}")


if __name__ == "__main__":
    main(sys.argv[1])
