"""From one recall to its trail: every page Lens matches to its listing photo, sorted into evidence.

This is the only module that spends SerpApi credits. A recall with a seller-style
photo costs one Lens search. A recall with only lab photos is skipped by default:
no store uses those photos, so Lens can only return other products that look similar.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from urllib.parse import quote

from .classify import NOT_A_BRAND, Match, classify, product_terms
from .photos import PhotoScore, score
from .recalls import Recall
from .serp import SerpClient, cache_key

# Lens returns at most this many exact matches for one photo, with no way to page further.
LENS_MATCH_LIMIT = 400


@dataclass
class Trail:
    recall: dict
    photo: dict
    recall_photo_url: str
    search_key: str
    matches_total: int
    matches_capped: bool
    kinds: dict[str, int]
    countries: list[tuple[str, int]]
    stores: int
    recalled_brand: str | None
    recalled_brand_listings: int
    selling: list[dict] = field(default_factory=list)
    india: list[dict] = field(default_factory=list)
    status: str = "ok"
    raw_json: str | None = None
    recall_photo_local: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def best_photo(recall: Recall) -> PhotoScore | None:
    scored = []
    for photo in recall.photos[:4]:
        try:
            scored.append(score(photo.url, photo.caption))
        except (OSError, ValueError):
            continue  # unreachable, malformed or unreadable image: try the next one
    return max(scored, key=lambda s: s.border_white, default=None)


def lens_params(photo_url: str) -> dict:
    # CPSC file names sometimes contain spaces; quote them without touching URLs that are already clean.
    return {"engine": "google_lens", "url": quote(photo_url, safe=":/?&=%#+~"), "type": "exact_matches"}


def recalled_brand(recall: Recall) -> str | None:
    """The brand as CPSC writes it: the first word of the product name, unless it is a generic word."""
    first = re.sub(r"[^A-Za-z0-9]", "", recall.product.split()[0]) if recall.product.split() else ""
    return first if first[:1].isalpha() and first.lower() not in NOT_A_BRAND else None


def build_trail(recall: Recall, photo: PhotoScore, data: dict) -> Trail:
    terms = product_terms(recall.product)
    matches: list[Match] = [classify(item, terms) for item in data.get("exact_matches", [])]
    selling = [m for m in matches if m.selling]
    brand = recalled_brand(recall)
    params = lens_params(photo.url)
    return Trail(
        recall=recall.to_dict(),
        photo=asdict(photo) | {"listing_style": photo.listing_style},
        recall_photo_url=photo.url,
        search_key=cache_key(params),
        matches_total=len(matches),
        matches_capped=len(matches) >= LENS_MATCH_LIMIT,
        kinds=dict(Counter(m.kind for m in matches)),
        countries=Counter(m.country for m in selling).most_common(),
        stores=len({m.domain for m in selling}),
        recalled_brand=brand,
        recalled_brand_listings=sum(1 for m in selling if brand and brand.lower() in m.title.lower()),
        selling=[asdict(m) | {"india": m.india} for m in selling],
        india=[asdict(m) | {"india": True} for m in matches if m.india],
        status="ok" if matches else "no_copies",
    )


def hunt(recall: Recall, client: SerpClient, photo: PhotoScore | None = None) -> Trail | None:
    """One Lens search for the recall's best listing-style photo. None if it only has lab photos."""
    photo = photo or best_photo(recall)
    if photo is None or not photo.listing_style:
        return None
    return build_trail(recall, photo, client.search(lens_params(photo.url)))
