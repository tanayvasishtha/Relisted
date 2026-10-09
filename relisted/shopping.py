"""Search by name: what Google Shopping India shows for a recalled product's name.

Lens answers "where is this photo?". This answers the question a parent or an official would ask
first: search the product's name in India, and see whether any result carries the recalled brand.
One Google Shopping search per recall, through the same cached and capped client.
"""

from __future__ import annotations

from collections import Counter

from .classify import countable_brand
from .serp import SerpClient, cache_key


def shopping_params(product: str) -> dict:
    return {"engine": "google_shopping", "q": product, "gl": "in", "hl": "en"}


def all_results(data: dict) -> list[dict]:
    """The main list plus the grouped lists Google sometimes shows above it."""
    grouped = [
        r for group in data.get("categorized_shopping_results", []) for r in group.get("shopping_results", [])
    ]
    return data.get("shopping_results", []) + grouped


def store_counts(results: list[dict]) -> list[tuple[str, int]]:
    """Results per store, most first. Google writes some stores two ways (Amazon.in, amazon.in)."""
    counts: Counter[str] = Counter()
    spelling: dict[str, str] = {}
    for result in results:
        source = result.get("source") or "Unknown store"
        spelling.setdefault(source.lower(), source)
        counts[source.lower()] += 1
    return [(spelling[key], n) for key, n in counts.most_common()]


def summarize(data: dict, product: str, brand: str | None) -> dict:
    results = all_results(data)
    name = countable_brand(brand)
    titled = sum(1 for r in results if name and name.lower() in (r.get("title") or "").lower())
    return {
        "query": product,
        "search_key": cache_key(shopping_params(product)),
        "results": len(results),
        "stores": store_counts(results),
        "name": name,
        "titled_with_name": titled if name else None,
    }


def check(trail: dict, client: SerpClient) -> dict:
    """One Google Shopping India search for the recall's product name. The summary is kept on the trail."""
    product = trail["recall"]["product"]
    summary = summarize(client.search(shopping_params(product)), product, trail.get("recalled_brand"))
    trail["india_shopping"] = summary
    return summary
