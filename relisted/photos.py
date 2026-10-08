"""Recall photos: download, tell seller listing photos from lab photos, fingerprint.

Google Lens finds exact copies of a seller's listing photo across hundreds of stores.
A photo CPSC staff took on a lab table has no copies to find. Listing photos almost
always sit on a plain white background, so the share of near-white pixels around the
border is a cheap, free way to pick the right photo before spending a search.
"""

from __future__ import annotations

import hashlib
import io
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .config import Settings, load_settings

USER_AGENT = "Mozilla/5.0 (Relisted research tool)"
LISTING_THRESHOLD = 0.70


@dataclass
class PhotoScore:
    url: str
    caption: str
    border_white: float
    width: int
    height: int

    @property
    def listing_style(self) -> bool:
        return self.border_white >= LISTING_THRESHOLD


def local_path(url: str, settings: Settings) -> Path:
    suffix = Path(url.split("?", 1)[0]).suffix.lower() or ".img"
    name = hashlib.sha256(url.encode()).hexdigest()[:16] + suffix
    return settings.data_dir / "photos" / name


def download(url: str, settings: Settings | None = None) -> bytes:
    settings = settings or load_settings()
    path = local_path(url, settings)
    if path.exists():
        return path.read_bytes()
    safe_url = urllib.parse.quote(url, safe=":/?&=%#+~")  # CPSC file names sometimes contain spaces
    req = urllib.request.Request(safe_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def open_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.seek(0)  # first frame of a GIF
    return img.convert("RGB")


def border_white(img: Image.Image, band: float = 0.06, level: int = 232) -> float:
    """Share of pixels in the outer border band that are near white."""
    small = img.resize((120, 120))
    w, h = small.size
    b = max(1, int(w * band))
    px = small.load()
    total = white = 0
    for y in range(h):
        for x in range(w):
            if b <= x < w - b and b <= y < h - b:
                continue
            r, g, bl = px[x, y]
            total += 1
            if r >= level and g >= level and bl >= level:
                white += 1
    return white / total if total else 0.0


def score(url: str, caption: str = "", settings: Settings | None = None) -> PhotoScore:
    img = open_image(download(url, settings))
    return PhotoScore(url, caption, round(border_white(img), 3), *img.size)
