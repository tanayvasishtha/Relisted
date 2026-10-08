import json
from dataclasses import replace
from pathlib import Path

import pytest

from relisted.hunt import build_trail, lens_params, recalled_brand
from relisted.photos import PhotoScore
from relisted.recalls import normalise
from relisted.serp import cache_key

FIXTURES = Path(__file__).parent / "fixtures"
WALKER_URL = "https://www.cpsc.gov/s3fs-public/bwalk-1.jpg"


@pytest.fixture(scope="module")
def walker_recall():
    raw = json.loads((FIXTURES / "cpsc_sample.json").read_text(encoding="utf-8"))
    return normalise(next(r for r in raw if str(r["RecallID"]) == "10901"))


@pytest.fixture(scope="module")
def trail(walker_recall):
    data = json.loads((FIXTURES / "walker_exact.json").read_text(encoding="utf-8"))
    photo = PhotoScore(url=WALKER_URL, caption="", border_white=0.98, width=300, height=270)
    return build_trail(walker_recall, photo, data)


def test_trail_totals(trail):
    assert trail.matches_total == 375
    assert trail.status == "ok"
    assert len(trail.selling) >= 40
    assert trail.stores >= 30
    assert sum(trail.kinds.values()) == 375
    assert trail.kinds["spam"] > trail.kinds["listing"]


def test_recorded_walker_search_stays_valid(trail):
    """The 375-match response was recorded under this key. Changing the key scheme would waste a credit."""
    assert trail.search_key == "google_lens_708c4db3fe6e4fba"
    assert cache_key(lens_params(WALKER_URL)) == trail.search_key


def test_india_hits_are_stores_that_sell_in_india(trail):
    domains = {m["domain"] for m in trail.india}
    assert "ubuy.co.in" in domains
    assert all(m["india"] and m["country"] == "IN" for m in trail.india)


def test_new_names_found_under_the_recalled_photo(trail):
    top = trail.aliases[0]
    assert top["name"] == "Uuoeebb"
    assert top["copies"] >= 10
    assert top["live_listings"] >= 3
    assert not any(a["recalled"] for a in trail.aliases)


def test_recalled_brand_is_absent_from_the_live_listings(walker_recall, trail):
    assert recalled_brand(walker_recall) == "Wnttmt"
    assert trail.recalled_brand == "Wnttmt"
    assert trail.recalled_brand_listings == 0


def test_countries_are_iso_codes_and_unknowns_are_marked(trail):
    codes = dict(trail.countries)
    assert codes["GB"] >= 3
    assert "UK" not in codes
    assert all(len(code) == 2 for code in codes)


def test_lens_params_quote_spaces_but_leave_clean_urls_alone():
    assert lens_params("https://www.cpsc.gov/a b.png?V=1")["url"] == "https://www.cpsc.gov/a%20b.png?V=1"
    assert lens_params(WALKER_URL)["url"] == WALKER_URL
    assert lens_params(WALKER_URL)["type"] == "exact_matches"


@pytest.mark.parametrize(
    "product, brand",
    [
        ("Wnttmt Baby Walkers", "Wnttmt"),
        ("Baby Bath Seats", None),
        ("Little Rawr Silicone Toys", "Little"),
        ("", None),
    ],
)
def test_recalled_brand(product, brand, walker_recall):
    assert recalled_brand(replace(walker_recall, product=product)) == brand
