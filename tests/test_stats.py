import json

from relisted import stats


def trail(
    recall_id,
    listings,
    *,
    india=0,
    matches=100,
    spam=40,
    brand_hits=0,
    kids=True,
    marketplace=True,
    countries=None,
):
    return {
        "recall": {
            "recall_id": recall_id,
            "product": f"Product {recall_id}",
            "date": "2026-08-06",
            "risk": "Risk of choking",
            "kids": kids,
            "marketplace": marketplace,
        },
        "matches_total": matches,
        "matches_capped": matches >= 400,
        "kinds": {"spam": spam, "listing": listings},
        "countries": countries or [["US", 3], ["GB", 2], ["XX", 5]],
        "stores": listings,
        "recalled_brand": "Orig",
        "recalled_brand_listings": brand_hits,
        "selling": [{"domain": f"store{i}.test"} for i in range(listings)],
        "india": [{"domain": "ubuy.co.in"}] * india,
    }


def test_compute_from_known_trails(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text('{"a": 1}\n{"a": 2}\n\n{"a": 3}\n', encoding="utf-8")
    trails = {
        "1": trail("1", 6, india=2, matches=375, spam=181),
        "2": trail("2", 1, matches=50),
        "3": trail("3", 0, matches=10, spam=0),
        "4": trail("4", 4, countries=[["DE", 1], ["XX", 3]]),
    }
    numbers = stats.compute(trails, ledger)

    assert numbers["recalls_checked"] == 4
    assert numbers["searches_paid_total"] == 3  # blank lines do not count
    assert numbers["pages_matched"] == 375 + 50 + 10 + 100
    assert numbers["live_listings"] == 6 + 1 + 0 + 4
    assert numbers["recalls_with_listings"] == 3
    assert numbers["recalls_with_three_or_more"] == 2
    assert numbers["recalls_sold_in_india"] == 1 and numbers["india_listings"] == 2
    assert numbers["countries"] == 3  # US, GB, DE; the unknown country is not a country
    assert numbers["spam_pages_filtered"] == 181 + 40 + 0 + 40


def test_headline_prefers_childrens_marketplace_recalls_without_the_recalled_name(tmp_path):
    trails = {
        "big": trail("big", 200, kids=False),  # most listings, but not a children's product
        "own": trail("own", 150, brand_hits=9),  # the recalled name is still on listings
        "fit": trail("fit", 90, india=2),
        "small": trail("small", 10),
    }
    top = stats.compute(trails, tmp_path / "none.jsonl")["headline"]
    assert top["recall_id"] == "fit"
    assert top["live_listings"] == 90 and top["india_listings"] == 2
    assert top["countries"] == 2 and top["listings_titled_with_recalled_brand"] == 0
    assert top["matches_capped"] is False


def test_headline_falls_back_to_the_most_listings(tmp_path):
    trails = {"a": trail("a", 3, kids=False), "b": trail("b", 7, kids=False)}
    assert stats.compute(trails, tmp_path / "none.jsonl")["headline"]["recall_id"] == "b"


def test_no_trails_is_not_an_error(tmp_path):
    numbers = stats.compute({}, tmp_path / "none.jsonl")
    assert numbers["recalls_checked"] == 0 and numbers["countries"] == 0 and numbers["headline"] is None


def test_write_saves_json(tmp_path):
    path = tmp_path / "out" / "stats.json"
    stats.write({"1": trail("1", 3)}, tmp_path / "none.jsonl", path)
    assert json.loads(path.read_text(encoding="utf-8"))["recalls_checked"] == 1
