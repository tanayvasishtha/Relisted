"""The social preview image (site/og.png), drawn from the same stats and thumbnails as the site.

White page, the recall's own photo on an orange label, then listings that Lens matched to it.
The typeface is the site's Archivo, set to its condensed heavy cut.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .config import ROOT
from .photos import open_image

SITE = ROOT / "site"
FONT = SITE / "assets" / "fonts" / "archivo-latin.woff2"
SIZE = (1200, 630)
MARGIN = 56
TILE = 170
GAP = 14
WASH = (242, 242, 242)
SIGNAL = (255, 106, 19)
INK = (0, 0, 0)
MONTHS = "January February March April May June July August September October November December".split()


def font(size: int, weight: int, width: int) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT), size)
    face.set_variation_by_axes([weight, width])  # this font's axes are Weight, then Width
    return face


def tile(path: Path, size: int) -> Image.Image:
    """The picture on the light wash, the way the site shows it: white backdrops disappear into the grey."""
    img = open_image(path.read_bytes())
    img.thumbnail((size, size))
    square = Image.new("RGB", (size, size), "white")
    square.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return ImageChops.multiply(Image.new("RGB", (size, size), WASH), square)


def pick_thumbnails(trail: dict, count: int) -> list[str]:
    """India first, then one listing per country, so the strip shows how far the product has spread."""
    with_image = [m for m in trail["selling"] if m.get("thumbnail")]
    ordered = [m for m in with_image if m["india"]][:1]
    seen: set[str] = set()
    for m in with_image:
        if m["country"] not in seen and m not in ordered:
            seen.add(m["country"])
            ordered.append(m)
    return [m["thumbnail"] for m in ordered[:count]]


def render(stats: dict, trail: dict, out: Path, site: Path = SITE) -> Path:
    head = stats["headline"]
    canvas = Image.new("RGB", SIZE, "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((MARGIN, 34), "Relisted", font=font(40, 900, 62), fill=INK)

    month = MONTHS[int(head["date"][5:7]) - 1]
    face = font(104, 900, 62)
    for i, line in enumerate((f"Recalled in {month}.", f"Still listed in {head['countries']} countries.")):
        draw.text((MARGIN, 92 + i * 98), line, font=face, fill=INK)

    top = SIZE[1] - MARGIN - TILE - 34
    canvas.paste(tile(site / trail["recall_photo_local"], TILE), (MARGIN, top))
    draw.rectangle([MARGIN, top + TILE, MARGIN + TILE, top + TILE + 34], fill=SIGNAL)
    draw.text((MARGIN + 10, top + TILE + 6), "The recall notice", font=font(19, 700, 88), fill=INK)
    for i, thumb in enumerate(pick_thumbnails(trail, 5), start=1):
        canvas.paste(tile(site / thumb, TILE), (MARGIN + i * (TILE + GAP), top))

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG", optimize=True)
    return out
