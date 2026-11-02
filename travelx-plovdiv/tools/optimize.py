"""Regenerates every optimized image in assets/ from the originals in _src/.

    python tools/optimize.py

Originals come straight out of the Figma file (jU9aCfQEVgYWraDz0FAXWD, node
5973:9), pulled 2026-09-23. The topic tiles and award cards arrive with their
titles and buttons baked into the bitmap — they are used as delivered, never
cropped, so the page lays them out at their own aspect ratios.

Photos -> AVIF at two widths plus a JPEG fallback. Logos -> trimmed WebP at
~3x their largest display height. Press logos are one-colour white, as on the
board. The Факти logo only exists in Figma as five loose letter vectors; it is
reassembled here.
"""
import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "_src", ROOT / "assets"
OUT.mkdir(exist_ok=True)
SIZES = {}  # name -> (w, h), printed at the end for the HTML width/height attributes


def resize_w(im, w):
    return im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def resize_h(im, h):
    return im if im.height <= h else im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def trim(im):
    a = im.getchannel("A")
    box = a.point(lambda v: 255 if v > 8 else 0).getbbox()
    return im.crop(box) if box else im


def save(im, name, **kw):
    p = OUT / name
    fmt = {"avif": "AVIF", "webp": "WEBP", "jpg": "JPEG"}[name.rsplit(".", 1)[1]]
    if fmt == "JPEG":
        im = im.convert("RGB")
    im.save(p, fmt, **kw)
    SIZES[name] = im.size
    print(f"{name:34} {im.width:>5}x{im.height:<5} {p.stat().st_size / 1024:6.1f} KB")


def photo(im, stem, widths, fallback_w, q=55):
    """AVIF per width (never upscaled; files are named by their real width, so
    srcset descriptors stay honest) plus one JPEG fallback."""
    im = im.convert("RGB")
    for w in sorted({min(w, im.width) for w in widths}):
        save(resize_w(im, w), f"{stem}-{w}.avif", quality=q, speed=4)
    save(resize_w(im, fallback_w), f"{stem}.jpg", quality=78, optimize=True, progressive=True)


def white(im):
    """One-colour white logo: keep the alpha, paint every pixel white."""
    im = im.convert("RGBA")
    out = Image.new("RGBA", im.size, (255, 255, 255, 0))
    out.putalpha(im.getchannel("A"))
    return out


# ── hero ──────────────────────────────────────────────────────────
hero = Image.open(SRC / "hero-plovdiv.jpg").convert("RGB")
for w in (960, 1600):
    save(resize_w(hero, w), f"hero-{w}.avif", quality=52, speed=4)
save(resize_w(hero, 1600), "hero-1600.jpg", quality=78, optimize=True, progressive=True)
big = resize_w(hero, 1200)
top = min(max(round(big.height * 0.40 - 315), 0), big.height - 630)
save(big.crop((0, top, 1200, top + 630)), "og.jpg", quality=82, optimize=True, progressive=True)

# ── topics + awards (text baked in: never crop) ───────────────────
for stem in ("common-voice", "getting-here", "buy-bulgaria", "events", "sun-ski",
             "flavours", "place-to-stay", "ai", "data", "traveller"):
    photo(Image.open(SRC / f"topic-{stem}.png"), f"topic-{stem}", (480, 960), 800)

for stem in ("culinary", "heritage", "municipality", "destination", "event",
             "spa", "wine", "alternative", "sports"):   # last four: 3x exports, 2026-09-25
    photo(Image.open(SRC / f"award-{stem}.png"), f"award-{stem}", (360, 640), 560)

# ── promo: the board's banner is one composite. The theatre half,
#    clear of the baked headline, becomes the live panel's photo. ──
promo = Image.open(SRC / "promo-composite.png").convert("RGB")
plate = promo.crop((900, 0, 2458, promo.height))
photo(plate, "promo-plovdiv", (800, 1400), 1200)

# ── logos ─────────────────────────────────────────────────────────
save(resize_h(trim(Image.open(SRC / "logo-travelx.png").convert("RGBA")), 120), "logo-travelx.webp", quality=92, method=6)
for src, h in (("org-plovdiv-crest", 150), ("org-visit-plovdiv", 110),
               ("org-urbo-studio", 110), ("org-digital4", 110)):
    save(resize_h(trim(Image.open(SRC / f"{src}.png").convert("RGBA")), h), f"{src}.webp", quality=92, method=6)

for src in ("travelradar", "travelnews", "flagman", "sofia24", "moreto", "focus"):
    im = white(trim(Image.open(SRC / f"press-{src}.png").convert("RGBA")))
    save(resize_h(im, 108), f"press-{src}.webp", quality=90, method=6)

for src in ("lider", "economic"):
    (OUT / f"press-{src}.svg").write_text((SRC / f"press-{src}.svg").read_text(encoding="utf-8"), encoding="utf-8")

# Факти: ф а к т и. Letters share a baseline at y=28.39 (к carries the
# ascender, ф's speech-bubble tail is the descender).
parts = [(5, 0.00, 8.0), (6, 30.83, 7.6), (1, 53.40, 0.0), (3, 78.16, 8.0), (4, 113.54, 7.9)]
body = []
for n, x, y in parts:
    svg = (SRC / f"fakti-part-{n}.svg").read_text(encoding="utf-8")
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    inner = re.sub(r'\bid="([^"]+)"', rf'id="f{n}-\1"', inner).replace("url(#", f"url(#f{n}-")
    body.append(f'<g transform="translate({x} {y})">{inner}</g>')
(OUT / "press-fakti.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 134.02 33.67" width="134" height="34">'
    + "".join(body) + "</svg>", encoding="utf-8")
print("press-fakti.svg                    (assembled)")

(OUT / "partner-urbo-city.svg").write_text((SRC / "partner-urbo-city.svg").read_text(encoding="utf-8"), encoding="utf-8")

total = sum(p.stat().st_size for p in OUT.glob("*") if p.is_file())
print(f"assets/ total (top level): {total / 1024:.0f} KB")
