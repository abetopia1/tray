"""Generates tileable cork, paper and grain textures into public/."""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

out = sys.argv[1]
rng = np.random.default_rng(7)


def tile_noise(n, sigma):
    """Smooth noise that wraps at the edges."""
    a = rng.standard_normal((n, n))
    a = gaussian_filter(a, sigma, mode="wrap")
    return (a - a.min()) / (a.max() - a.min())


def cork(n=1024):
    base = np.array([176, 126, 76], float)
    big = tile_noise(n, 60)[..., None]
    mid = tile_noise(n, 9)[..., None]
    fine = tile_noise(n, 1.6)[..., None]
    img = base * (0.80 + 0.22 * big) * (0.86 + 0.26 * mid) * (0.90 + 0.20 * fine)

    # Dark and light granules give cork its speckle.
    for count, lo, hi, shade in ((2600, 1.2, 4.5, 0.55), (1500, 1.0, 3.5, 1.28), (260, 4, 9, 0.62)):
        mask = np.zeros((n, n))
        ys, xs = rng.integers(0, n, count), rng.integers(0, n, count)
        mask[ys, xs] = 1
        r = rng.uniform(lo, hi)
        mask = gaussian_filter(mask, r, mode="wrap")
        mask = np.clip(mask / (mask.max() * 0.35), 0, 1)[..., None]
        img = img * (1 - mask) + img * shade * mask

    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def paper(n=512, tint=(246, 240, 226)):
    fibre = tile_noise(n, 1.1)[..., None]
    blotch = tile_noise(n, 40)[..., None]
    img = np.array(tint, float) * (0.955 + 0.05 * fibre) * (0.97 + 0.04 * blotch)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def grain(n=512):
    g = rng.normal(128, 26, (n, n))
    a = np.full((n, n), 255)
    rgba = np.stack([g, g, g, a], -1)
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


cork().save(f"{out}/cork.jpg", quality=90)
paper().save(f"{out}/paper.jpg", quality=92)
paper(tint=(226, 196, 140)).save(f"{out}/manila.jpg", quality=92)
grain().save(f"{out}/grain.png")
print("textures written")
