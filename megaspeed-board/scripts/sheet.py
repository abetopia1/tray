"""Tiles still frames into one contact sheet. Usage: sheet.py out.jpg cols a.jpg b.jpg ..."""
import sys
from PIL import Image

out, cols, files = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
ims = [Image.open(f) for f in files]
w, h = ims[0].size
rows = -(-len(ims) // cols)
sheet = Image.new("RGB", (w * cols, h * rows), "black")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out, quality=88)
