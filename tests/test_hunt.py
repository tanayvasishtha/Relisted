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
    assert not trail.matches_capped
    assert trail.status == "ok"
    assert len(trail.selling) >= 40
    assert trail.stores >= 30
    assert sum(trail.kinds.values()) == 375
    assert trail.kinds["spam"] > trail.kinds["listing"]


def test_a_full_page_of_matches_is_flagged_as_capped(walker_recall):
    photo = PhotoScore(url=WALKER_URL, caption="", border_white=0.98, width=300, height=270)
    full = {
        "exact_matches": [{"title": f"Walker {i}", "link": f"https://shop{i}.test/p/{i}"} for i in range(400)]
    }
    assert build_trail(walker_recall, photo, full).matches_capped
    assert not build_trail(
        walker_recall, photo, {"exact_matches": full["exact_matches"][:399]}
    ).matches_capped


def test_recorded_walker_search_stays_valid(trail):
    """The 375-match response was recorded under this key. Changing the key scheme would waste a credit."""
    assert trail.search_key == "google_lens_708c4db3fe6e4fba"
    assert cache_key(lens_params(WALKER_URL)) == trail.search_key


def test_india_hits_are_stores_that_sell_in_india(trail):
    domains = {m["domain"] for m in trail.india}
    assert "ubuy.co.in" in domains
    assert all(m["india"] and m["country"] == "IN" for m in trail.india)


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
        ("Little Rawr Silicone Toys", None),  # an ordinary word cannot name a brand
        ("Magnetic Chess Games", None),
        ("GM Gumili Oil Bottles", None),  # too short to tell apart from other words
        ("1-K Kerosene Heater Fluid", None),
        ("Male-to-Male Extension Cords", None),  # a description, not a brand
        ("Member's Mark Pajama Sets", None),  # "Members" is an ordinary word
        ("", None),
    ],
)
def test_recalled_brand(product, brand, walker_recall):
    assert recalled_brand(replace(walker_recall, product=product)) == brand


def test_rebuild_sorts_a_saved_trail_again_from_its_recording(tmp_path, walker_recall, trail):
    from relisted.config import Settings
    from relisted.hunt import rebuild
    from relisted.serp import SerpClient

    client = SerpClient(settings=Settings(api_key=None, replay=True, max_credits=0, data_dir=tmp_path))
    recording = client.path_for(lens_params(WALKER_URL))
    recording.parent.mkdir(parents=True)
    recording.write_text((FIXTURES / "walker_exact.json").read_text(encoding="utf-8"), encoding="utf-8")

    again = rebuild(trail.to_dict(), client)

    assert again.to_dict() == trail.to_dict() and client.credits_used == 0
