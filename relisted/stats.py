"""The numbers shown on the site, in the README and in the video, computed from the saved results.

Nothing here is typed by hand: trails.json holds what Lens returned and how it was sorted,
and ledger.jsonl holds every SerpApi search that was paid for.
"""

from __future__ import annotations

import json
from pathlib import Path

from .classify import UNKNOWN_COUNTRY
from .store import TRAILS_PATH

STATS_PATH = TRAILS_PATH.parent / "stats.json"


def count_searches(ledger_path: Path) -> int:
    if not ledger_path.exists():
        return 0
    return sum(1 for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip())


def countries(trail: dict) -> set[str]:
    return {code for code, _ in trail["countries"] if code != UNKNOWN_COUNTRY}


def headline(trails: list[dict]) -> dict | None:
    """The recall the home page leads with.

    Children's products sold by marketplace sellers, whose own name appears on none of the listings
    that Lens matched to the recall photo, ranked by how many store listings those matches include.
    If no recall fits, the one with the most listings overall.
    """
    if not trails:
        return None
    fits = [
        t
        for t in trails
        if t["recall"]["kids"] and t["recall"]["marketplace"] and t["recalled_brand_listings"] == 0
    ]
    top = max(fits or trails, key=lambda t: len(t["selling"]))
    return {
        "recall_id": top["recall"]["recall_id"],
        "product": top["recall"]["product"],
        "date": top["recall"]["date"],
        "risk": top["recall"]["risk"],
        "matches": top["matches_total"],
        "matches_capped": top["matches_capped"],
        "live_listings": len(top["selling"]),
        "stores": top["stores"],
        "countries": len(countries(top)),
        "india_listings": len(top["india"]),
        "recalled_brand": top["recalled_brand"],
        "listings_titled_with_recalled_brand": top["recalled_brand_listings"],
        "india_shopping": top.get("india_shopping"),
    }


def compute(trails: dict[str, dict], ledger_path: Path) -> dict:
    items = list(trails.values())
    selling = [m for t in items for m in t["selling"]]
    checked = [t["india_shopping"] for t in items if t.get("india_shopping")]
    named = [s for s in checked if s["name"]]
    return {
        "recalls_checked": len(items),
        "searches_paid_total": count_searches(ledger_path),
        "pages_matched": sum(t["matches_total"] for t in items),
        "live_listings": len(selling),
        "stores": len({m["domain"] for m in selling}),
        "countries": len(set().union(*(countries(t) for t in items))) if items else 0,
        "recalls_with_listings": sum(1 for t in items if t["selling"]),
        "recalls_with_three_or_more": sum(1 for t in items if len(t["selling"]) >= 3),
        "recalls_sold_in_india": sum(1 for t in items if t["india"]),
        "india_listings": sum(len(t["india"]) for t in items),
        "spam_pages_filtered": sum(t["kinds"].get("spam", 0) for t in items),
        "shopping_searches": len(checked),
        "shopping_results": sum(s["results"] for s in checked),
        "shopping_names_counted": len(named),
        "shopping_names_found_in_no_result": sum(1 for s in named if s["titled_with_name"] == 0),
        "headline": headline(items),
    }


def write(trails: dict[str, dict], ledger_path: Path, path: Path = STATS_PATH) -> dict:
    stats = compute(trails, ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    return stats
