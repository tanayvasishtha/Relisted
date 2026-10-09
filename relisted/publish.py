"""Make a trail self-contained for the static site.

For each trail this copies the recorded SerpApi response next to the site, saves small local
thumbnails so pages never hotlink Google. Everything here is free: no SerpApi call is made.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from .config import ROOT, Settings, load_settings
from .photos import USER_AGENT, download, open_image
from .serp import strip_tokens

SITE = ROOT / "site"
THUMB_WIDTH = 360
RECALL_WIDTH = 900
WORKERS = 8
# Fields of search_metadata that point at SerpApi's archive of the search. They add nothing for a reader.
ARCHIVE_FIELDS = ("json_endpoint", "markdown_endpoint", "raw_html_file", "prettify_html_file")


def thumb_path(url: str) -> str:
    return f"thumbs/{hashlib.sha256(url.encode()).hexdigest()[:16]}.jpg"


def save_jpeg(img: Image.Image, dest: Path, width: int) -> Image.Image:
    small = img.copy()
    small.thumbnail((width, width * 2))
    dest.parent.mkdir(parents=True, exist_ok=True)
    small.save(dest, "JPEG", quality=80, optimize=True)
    return small


def fetch_image(url: str) -> Image.Image | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=10) as resp:
            return open_image(resp.read())
    except (OSError, ValueError):
        return None  # unreachable or not an image: the page shows a plain tile instead


def load_thumbnail(src: str, site: Path) -> Image.Image | None:
    dest = site / thumb_path(src)
    if dest.exists():
        return Image.open(dest).convert("RGB")
    img = fetch_image(src)
    return save_jpeg(img, dest, THUMB_WIDTH) if img else None


def copy_raw(search_key: str, settings: Settings, site: Path) -> str | None:
    """Publish a recorded SerpApi response, minus the links into SerpApi's private archive."""
    source = settings.cache_dir / f"{search_key}.json"
    if not source.exists():
        return None
    data = strip_tokens(json.loads(source.read_text(encoding="utf-8")))
    for name in ARCHIVE_FIELDS:
        data.get("search_metadata", {}).pop(name, None)
    relative = f"data/raw/{search_key}.json"
    (site / relative).parent.mkdir(parents=True, exist_ok=True)
    (site / relative).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return relative


def publish_trail(trail: dict, settings: Settings | None = None, site: Path = SITE) -> dict:
    """Fill in recall_photo_local, raw_json and, per match, the local thumbnail."""
    settings = settings or load_settings()
    recall_img = open_image(download(trail["recall_photo_url"], settings))
    relative = f"thumbs/recall-{trail['recall']['recall_id']}.jpg"
    save_jpeg(recall_img, site / relative, RECALL_WIDTH)
    trail["recall_photo_local"] = relative
    trail["raw_json"] = copy_raw(trail["search_key"], settings, site)
    if trail.get("india_shopping"):
        shopping = trail["india_shopping"]
        shopping["raw_json"] = copy_raw(shopping["search_key"], settings, site)

    matches = trail["selling"] + trail["india"]
    sources = {m.get("thumbnail_src") or m.get("thumbnail") for m in matches} - {None}
    with ThreadPoolExecutor(WORKERS) as pool:
        images = dict(zip(sources, pool.map(lambda s: load_thumbnail(s, site), sources), strict=True))
    for match in matches:
        src = match.get("thumbnail_src") or match.get("thumbnail")
        match.update(thumbnail_src=src, thumbnail=thumb_path(src) if images.get(src) else None)
    return trail


def publish_all(trails: dict[str, dict], settings: Settings | None = None, site: Path = SITE) -> dict:
    settings = settings or load_settings()
    for trail in trails.values():
        publish_trail(trail, settings, site)
    return trails
