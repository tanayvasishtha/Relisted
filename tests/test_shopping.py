import json

from relisted import publish, shopping, stats
from relisted.config import Settings
from relisted.serp import SerpClient, cache_key

RESULTS = {
    "shopping_results": [
        {"title": "Novanest Pull String Teether", "source": "Flipkart"},
        {"title": "AiTuiTui pull string toy", "source": "amazon.in"},
        {"title": "Funblast Pull String Toy", "source": "Flipkart"},
        {"title": None, "source": None},
    ]
}


def test_the_search_is_google_shopping_in_india():
    assert shopping.shopping_params("AiTuiTui Pull String Teething Toys") == {
        "engine": "google_shopping",
        "q": "AiTuiTui Pull String Teething Toys",
        "gl": "in",
        "hl": "en",
    }


def test_only_distinctive_names_are_counted():
    from relisted.classify import countable_brand

    assert countable_brand("AiTuiTui") == "AiTuiTui"
    assert countable_brand("Magnetic") is None  # an ordinary word proves nothing
    assert countable_brand("GM") is None  # too short
    assert countable_brand(None) is None


def test_grouped_results_are_counted_too():
    data = {
        "shopping_results": [{"title": "Battery pack", "source": "Flipkart"}],
        "categorized_shopping_results": [
            {"title": "Popular", "shopping_results": [{"title": "EEMB 3.7V battery", "source": "amazon.in"}]}
        ],
    }
    summary = shopping.summarize(data, "EEMB Lithium Battery Packs", "EEMB")
    assert summary["results"] == 2 and summary["titled_with_name"] == 1


def test_summary_counts_results_stores_and_titles_with_the_name():
    summary = shopping.summarize(RESULTS, "AiTuiTui Pull String Teething Toys", "AiTuiTui")
    assert summary["results"] == 4
    assert summary["stores"][0] == ("Flipkart", 2)
    assert ("Unknown store", 1) in summary["stores"]
    assert summary["titled_with_name"] == 1  # case does not matter
    assert summary["search_key"] == cache_key(shopping.shopping_params("AiTuiTui Pull String Teething Toys"))


def test_a_store_written_two_ways_is_one_store():
    results = [{"source": "Amazon.in"}, {"source": "amazon.in"}, {"source": "Flipkart"}]
    assert shopping.store_counts(results) == [("Amazon.in", 2), ("Flipkart", 1)]


def test_an_ordinary_brand_word_is_not_counted():
    summary = shopping.summarize(RESULTS, "Magnetic Chess Games", "Magnetic")
    assert summary["name"] is None and summary["titled_with_name"] is None


def test_an_error_payload_is_zero_results():
    assert (
        shopping.summarize({"error": "Google hasn't returned any results"}, "X Toy", "Xyzzy")["results"] == 0
    )


def test_check_replays_a_recorded_search_and_keeps_the_summary_on_the_trail(tmp_path):
    settings = Settings(api_key=None, replay=True, max_credits=0, data_dir=tmp_path / "data")
    client = SerpClient(settings=settings)
    params = shopping.shopping_params("AiTuiTui Pull String Teething Toys")
    client.path_for(params).parent.mkdir(parents=True)
    client.path_for(params).write_text(json.dumps(RESULTS), encoding="utf-8")
    trail = {"recall": {"product": "AiTuiTui Pull String Teething Toys"}, "recalled_brand": "AiTuiTui"}

    shopping.check(trail, client)

    assert trail["india_shopping"]["results"] == 4 and client.credits_used == 0


def test_publish_copies_the_raw_shopping_result(tmp_path, monkeypatch):
    settings = Settings(api_key=None, replay=True, max_credits=0, data_dir=tmp_path / "data")
    settings.cache_dir.mkdir(parents=True)
    (settings.cache_dir / "google_shopping_abc.json").write_text(json.dumps(RESULTS), encoding="utf-8")
    monkeypatch.setattr(publish, "download", lambda url, settings=None: _png())
    trail = {
        "recall": {"recall_id": "7"},
        "recall_photo_url": "https://cpsc.test/p.png",
        "search_key": "google_lens_none",
        "selling": [],
        "india": [],
        "india_shopping": {"search_key": "google_shopping_abc"},
    }
    publish.publish_trail(trail, settings, tmp_path / "site")
    assert trail["india_shopping"]["raw_json"] == "data/raw/google_shopping_abc.json"


def test_stats_count_name_searches(tmp_path):
    def trail(recall_id, name, titled):
        return {
            "recall": {
                "recall_id": recall_id,
                "product": "P",
                "date": "2026-01-29",
                "risk": "r",
                "kids": True,
                "marketplace": True,
            },
            "matches_total": 10,
            "matches_capped": False,
            "kinds": {},
            "countries": [],
            "stores": 1,
            "recalled_brand": name,
            "recalled_brand_listings": 0,
            "selling": [{"domain": "a.test"}],
            "india": [],
            "india_shopping": {"results": 40, "name": name, "titled_with_name": titled},
        }

    numbers = stats.compute(
        {"a": trail("a", "Aaa", 0), "b": trail("b", "Bbb", 3), "c": trail("c", None, None)},
        tmp_path / "none.jsonl",
    )
    assert numbers["shopping_searches"] == 3 and numbers["shopping_results"] == 120
    assert numbers["shopping_names_counted"] == 2 and numbers["shopping_names_found_in_no_result"] == 1


def _png() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()
