import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from relisted import server
from relisted.config import Settings
from relisted.photos import PhotoScore
from relisted.recalls import normalise
from relisted.serp import SerpClient

FIXTURES = Path(__file__).parent / "fixtures"
HEADERS = {"X-Relisted": "1"}
WALKER = "https://www.cpsc.gov/s3fs-public/bwalk-1.jpg"


@pytest.fixture
def client():
    server._status.update(at=0.0, value=None)
    server._candidates["value"] = None
    return TestClient(server.app)


@pytest.fixture(scope="module")
def recalls():
    raw = json.loads((FIXTURES / "cpsc_sample.json").read_text(encoding="utf-8"))
    return [normalise(r) for r in raw]


@pytest.fixture
def live(monkeypatch, tmp_path, recalls):
    """Live mode with every outside effect replaced: no network, no real files, no credits."""
    settings = Settings(api_key="test-key", replay=False, max_credits=10, data_dir=tmp_path / "data")
    walker = json.loads((FIXTURES / "walker_exact.json").read_text(encoding="utf-8"))
    saved: dict = {}
    listing = PhotoScore(url=WALKER, caption="", border_white=0.98, width=300, height=270)
    lab = PhotoScore(url="https://cpsc.test/lab.jpg", caption="", border_white=0.1, width=300, height=270)
    monkeypatch.setattr(server, "load_settings", lambda: settings)
    monkeypatch.setattr(server, "fetch", lambda: recalls)
    monkeypatch.setattr(server, "best_photo", lambda r: listing if r.recall_id == "10901" else lab)
    monkeypatch.setattr("relisted.hunt.best_photo", lambda r: listing if r.recall_id == "10901" else lab)
    monkeypatch.setattr(SerpClient, "_live", lambda self, params: walker)
    monkeypatch.setattr(server.store, "load", lambda: {"trails": dict(saved.get("trails", {}))})
    monkeypatch.setattr(
        server.store, "save", lambda trails, credits: saved.update(trails=trails, credits=credits)
    )
    monkeypatch.setattr(server.publish, "publish_trail", lambda trail, settings: trail)
    monkeypatch.setattr(server.stats, "write", lambda trails, ledger: saved.update(stats_written=len(trails)))
    return saved


def test_replay_mode_reports_itself(client):
    assert client.get("/api/status").json() == {"mode": "replay", "searches_left": None}
    assert client.get("/api/candidates").json() == []


def test_replay_mode_refuses_a_live_search(client):
    response = client.post("/api/search/10901", headers=HEADERS)
    assert response.status_code == 409
    assert "SERPAPI_API_KEY" in response.json()["detail"]


def test_a_search_without_the_header_is_refused(client, live):
    assert client.post("/api/search/10901").status_code == 403


def test_the_site_is_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "Relisted" in page.text
    assert page.headers["cache-control"] == "no-cache"


def test_live_status_shows_searches_left(client, live, monkeypatch):
    monkeypatch.setattr(server, "account_status", lambda settings: {"searches_left": 203})
    assert client.get("/api/status").json() == {"mode": "live", "searches_left": 203}


def test_live_search_pays_one_search_and_saves_the_trail(client, live):
    response = client.post("/api/search/10901", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["credits_used"] == 1
    assert body["store_listings"] >= 40
    assert body["url"] == "recall.html?id=10901"
    assert "10901" in live["trails"] and live["credits"] == 1
    assert live["stats_written"] == 1  # stats.json is rewritten with the new trail


def test_the_same_search_twice_is_paid_once(client, live):
    assert client.post("/api/search/10901", headers=HEADERS).json()["credits_used"] == 1
    assert client.post("/api/search/10901", headers=HEADERS).json()["credits_used"] == 0


def test_unknown_recall_is_a_404(client, live):
    assert client.post("/api/search/nope", headers=HEADERS).status_code == 404


def test_a_recall_with_only_lab_photos_is_refused_before_any_search(client, live):
    response = client.post("/api/search/10893", headers=HEADERS)
    assert response.status_code == 422
    assert "listing-style photo" in response.json()["detail"]
    assert "trails" not in live


def test_candidates_are_unsearched_recalls_with_listing_style_photos(client, live):
    assert [c["recall_id"] for c in client.get("/api/candidates").json()] == ["10901"]
    client.post("/api/search/10901", headers=HEADERS)
    assert client.get("/api/candidates").json() == []  # now searched


def test_the_count_drops_at_once_after_a_paid_search(client, live, monkeypatch):
    calls = []
    monkeypatch.setattr(server, "account_status", lambda settings: calls.append(1) or {"searches_left": 203})
    assert client.get("/api/status").json()["searches_left"] == 203
    client.post("/api/search/10901", headers=HEADERS)
    assert client.get("/api/status").json()["searches_left"] == 202
    assert len(calls) == 1  # the new count came from local arithmetic, not a second account call
