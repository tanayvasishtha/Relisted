import json

import pytest

from relisted.config import Settings
from relisted.serp import BudgetExceeded, NotRecorded, SerpClient, cache_key

PARAMS = {"engine": "google_lens", "url": "https://example.test/a.jpg", "type": "exact_matches"}
OTHER = {"engine": "google_lens", "url": "https://example.test/b.jpg", "type": "exact_matches"}


def client(tmp_path, *, replay: bool, max_credits: int = 5) -> SerpClient:
    settings = Settings(
        api_key=None if replay else "test-key", replay=replay, max_credits=max_credits, data_dir=tmp_path
    )
    return SerpClient(settings=settings)


def test_cache_key_ignores_parameter_order():
    assert cache_key({"engine": "google_lens", "url": "u"}) == cache_key(
        {"url": "u", "engine": "google_lens"}
    )


def test_replay_serves_a_recorded_search_for_free(tmp_path):
    c = client(tmp_path, replay=True)
    path = c.path_for(PARAMS)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"exact_matches": [1, 2]}), encoding="utf-8")
    assert c.search(PARAMS) == {"exact_matches": [1, 2]}
    assert (c.cache_hits, c.credits_used) == (1, 0)


def test_replay_refuses_a_search_that_was_never_recorded(tmp_path):
    with pytest.raises(NotRecorded, match="SERPAPI_API_KEY"):
        client(tmp_path, replay=True).search(PARAMS)


def test_live_search_is_paid_once_then_cached(tmp_path, monkeypatch):
    calls = []

    def fake_live(self, params):
        calls.append(params["url"])
        return {"search_metadata": {"status": "Success"}, "exact_matches": []}

    monkeypatch.setattr(SerpClient, "_live", fake_live)
    c = client(tmp_path, replay=False)
    c.search(PARAMS)
    c.search(PARAMS)
    assert calls == ["https://example.test/a.jpg"]
    assert (c.credits_used, c.cache_hits) == (1, 1)


def test_credit_cap_stops_the_next_new_search(tmp_path, monkeypatch):
    monkeypatch.setattr(SerpClient, "_live", lambda self, params: {"search_metadata": {"status": "Success"}})
    c = client(tmp_path, replay=False, max_credits=1)
    c.search(PARAMS)
    c.search(PARAMS)  # cached, still allowed
    with pytest.raises(BudgetExceeded, match="cap of 1"):
        c.search(OTHER)
    assert c.credits_used == 1


def test_every_paid_search_is_logged_without_the_key(tmp_path, monkeypatch):
    monkeypatch.setattr(SerpClient, "_live", lambda self, params: {"search_metadata": {"status": "Success"}})
    c = client(tmp_path, replay=False)
    c.search(PARAMS)
    lines = c.settings.ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["engine"] == "google_lens" and entry["status"] == "Success"
    assert "test-key" not in lines[0]


def test_page_tokens_are_never_stored():
    from relisted.serp import strip_tokens

    data = {
        "page_token": "4fPK4Xicz",
        "shopping_results": [
            {
                "title": "Toy",
                "immersive_product_page_token": "J2Lb2Xicb",
                "serpapi_immersive_product_api": "https://serpapi.com/search.json?page_token=J2Lb2Xicb",
                "product_link": "https://www.google.com/shopping/product/1",
            }
        ],
    }
    assert strip_tokens(data) == {
        "shopping_results": [{"title": "Toy", "product_link": "https://www.google.com/shopping/product/1"}]
    }


def test_network_errors_never_show_the_key(tmp_path, monkeypatch):
    import requests
    import serpapi

    from relisted.serp import SearchFailed

    def stalled(self, params=None, **kwargs):
        raise requests.exceptions.ConnectionError(
            "Max retries exceeded with url: /search?api_key=test-key&q=x"
        )

    monkeypatch.setattr(serpapi.Client, "search", stalled)
    c = client(tmp_path, replay=False)
    with pytest.raises(SearchFailed) as failed:
        c.search(PARAMS)
    assert "test-key" not in str(failed.value) and "***" in str(failed.value)
    assert failed.value.__cause__ is None and failed.value.__suppress_context__  # no traceback quoting it
    assert c.credits_used == 0 and not c.path_for(PARAMS).exists()


def test_an_error_reply_is_neither_cached_nor_counted(tmp_path, monkeypatch):
    from relisted.serp import SearchFailed

    reply = {"search_metadata": {"status": "Error"}, "error": "Your account has run out of searches."}
    monkeypatch.setattr(SerpClient, "_live", lambda self, params: reply)
    c = client(tmp_path, replay=False)
    with pytest.raises(SearchFailed, match="run out of searches"):
        c.search(PARAMS)
    assert c.credits_used == 0 and not c.path_for(PARAMS).exists()
    assert not c.settings.ledger_path.exists()  # the next run tries again


def test_no_results_is_a_real_answer_and_is_kept(tmp_path, monkeypatch):
    reply = {"search_metadata": {"status": "Success"}, "error": "Google hasn't returned any results."}
    monkeypatch.setattr(SerpClient, "_live", lambda self, params: reply)
    c = client(tmp_path, replay=False)
    assert c.search(PARAMS) == reply
    assert c.credits_used == 1 and c.path_for(PARAMS).exists()


def test_page_tokens_never_reach_the_cache(tmp_path, monkeypatch):
    reply = {"search_metadata": {"status": "Success"}, "page_token": "4fPK4Xicz", "exact_matches": []}
    monkeypatch.setattr(SerpClient, "_live", lambda self, params: reply)
    c = client(tmp_path, replay=False)
    c.search(PARAMS)
    assert "page_token" not in c.path_for(PARAMS).read_text(encoding="utf-8")
