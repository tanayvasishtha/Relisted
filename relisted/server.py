"""The site plus live Lens search, on this machine only. Run with `relisted serve`.

A live search costs one SerpApi search, so each request carries a cap of one, and a custom header is
required: a web page on another origin cannot send it without a CORS preflight, which this server refuses.
"""

from __future__ import annotations

import dataclasses
import threading
import time
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from serpapi import SerpApiError
from starlette.middleware.base import BaseHTTPMiddleware

from . import publish, stats, store
from .config import ROOT, load_settings
from .hunt import best_photo, hunt
from .recalls import fetch, ranked
from .serp import BudgetExceeded, NotRecorded, SerpClient, account_status

SITE = ROOT / "site"
STATUS_TTL = 60  # seconds the free Account API answer is reused
CANDIDATES = 12

_lock = threading.Lock()  # one search at a time, and trails.json is written by one request at a time
_status: dict[str, Any] = {"at": 0.0, "value": None}
_candidates: dict[str, Any] = {"value": None}  # scoring photos takes a few seconds, so keep the answer


class NoCache(BaseHTTPMiddleware):
    """This is a local tool: always show the latest files."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="Relisted", docs_url=None, redoc_url=None)
app.add_middleware(NoCache)


def require_header(x_relisted: str | None = Header(default=None)) -> None:
    if x_relisted != "1":
        raise HTTPException(403, "Missing the X-Relisted header.")


@app.get("/api/status")
def status() -> dict:
    settings = load_settings()
    if settings.replay:
        return {"mode": "replay", "searches_left": None}
    if time.monotonic() - _status["at"] > STATUS_TTL or _status["value"] is None:
        try:
            _status.update(at=time.monotonic(), value=account_status(settings).get("searches_left"))
        except OSError:
            _status.update(at=time.monotonic(), value=None)  # the count is a courtesy; search still works
    return {"mode": "live", "searches_left": _status["value"]}


@app.get("/api/candidates")
def candidates() -> list[dict]:
    """Recalls with a listing-style photo that no search has covered yet. Live mode only."""
    if load_settings().replay:
        return []
    if _candidates["value"] is not None:
        return _candidates["value"]
    done = set(store.load().get("trails", {}))
    found: list[dict] = []
    for recall in ranked([r for r in fetch() if r.recall_id not in done]):
        photo = best_photo(recall)
        if photo and photo.listing_style:
            found.append(
                {
                    "recall_id": recall.recall_id,
                    "product": recall.product,
                    "date": recall.date,
                    "sold_on": recall.sold_on,
                    "photo": photo.url,
                }
            )
        if len(found) == CANDIDATES:
            break
    _candidates["value"] = found
    return found


@app.post("/api/search/{recall_id}", dependencies=[Depends(require_header)])
def search(recall_id: str) -> dict:
    settings = load_settings()
    if settings.replay:
        raise HTTPException(409, "Live search needs SERPAPI_API_KEY in .env.")
    recall = next((r for r in fetch() if r.recall_id == recall_id), None)
    if recall is None:
        raise HTTPException(404, f"No recall with id {recall_id}.")
    client = SerpClient(settings=dataclasses.replace(settings, max_credits=1))
    with _lock:
        try:
            trail = hunt(recall, client)
        except BudgetExceeded as exc:
            raise HTTPException(429, str(exc)) from exc
        except NotRecorded as exc:
            raise HTTPException(409, str(exc)) from exc
        except SerpApiError as exc:
            raise HTTPException(502, f"SerpApi answered with an error: {exc}") from exc
        if trail is None:
            raise HTTPException(
                422, "This recall has no listing-style photo, so Lens would only find look-alikes."
            )
        done = publish.publish_trail(trail.to_dict(), settings)
        trails = store.load().get("trails", {})
        trails[recall_id] = done
        store.save(trails, client.credits_used)
        stats.write(trails, settings.ledger_path)  # the home page counts must match its table
        _status["at"] = 0.0  # the next status call shows the new count
        _candidates["value"] = None  # this recall is no longer a candidate
    return {
        "recall_id": recall_id,
        "credits_used": client.credits_used,
        "store_listings": len(done["selling"]),
        "url": f"recall.html?id={recall_id}",
    }


app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
