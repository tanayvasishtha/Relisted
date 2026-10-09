"""SerpApi access with a record/replay cache and a hard credit cap.

Every live response is written to data/cache as raw JSON, keyed by a hash of the
request parameters. The same request is never paid for twice. With no API key the
client runs in replay mode and serves only what is already recorded.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings, load_settings


class NotRecorded(RuntimeError):
    """Replay mode was asked for a search that was never recorded."""


class BudgetExceeded(RuntimeError):
    """A live search would push this run past its credit cap."""


class SearchFailed(RuntimeError):
    """SerpApi gave no usable answer. Nothing was cached or counted, so the next run tries again."""


TIMEOUT = 90  # seconds; a stalled connection must not hold the live-search lock forever


def redact(text: str, secret: str | None) -> str:
    """Error text from the HTTP layer quotes the request URL, and with it the API key."""
    return text.replace(secret, "***") if secret else text


def strip_tokens(value: Any) -> Any:
    """Drop Google's opaque page tokens and the links that carry them.

    They only fetch another page or a product page. They are not credentials, but secret scanners
    flag them, and nothing here uses them, so they are never written to disk.
    """
    if isinstance(value, dict):
        return {
            k: strip_tokens(v)
            for k, v in value.items()
            if not k.endswith("page_token") and not (isinstance(v, str) and "page_token=" in v)
        }
    if isinstance(value, list):
        return [strip_tokens(v) for v in value]
    return value


def cache_key(params: dict[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return f"{params['engine']}_{hashlib.sha256(blob.encode()).hexdigest()[:16]}"


@dataclass
class SerpClient:
    settings: Settings = field(default_factory=load_settings)
    credits_used: int = 0
    cache_hits: int = 0

    def path_for(self, params: dict[str, Any]) -> Path:
        return self.settings.cache_dir / f"{cache_key(params)}.json"

    def search(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self.path_for(params)
        if path.exists():
            self.cache_hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        if self.settings.replay:
            raise NotRecorded(
                f"No recording for {params.get('engine')} search {cache_key(params)}. "
                "Set SERPAPI_API_KEY in .env to run it live."
            )
        if self.credits_used >= self.settings.max_credits:
            raise BudgetExceeded(
                f"Credit cap of {self.settings.max_credits} reached for this run. "
                "Raise RELISTED_MAX_CREDITS to allow more."
            )
        data = strip_tokens(self._live(params))
        if data.get("search_metadata", {}).get("status") != "Success":
            # A bad key, no searches left or a server error is not an answer: keep nothing, count nothing.
            # "No results" is different: it comes back as Success with an error field, and is kept.
            reason = data.get("error") or "no reason given"
            raise SearchFailed(redact(f"SerpApi could not run the search: {reason}", self.settings.api_key))
        self.credits_used += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        self._log(params, data)
        return data

    def _live(self, params: dict[str, Any]) -> dict[str, Any]:
        import serpapi

        client = serpapi.Client(api_key=self.settings.api_key, timeout=TIMEOUT)
        try:
            return dict(client.search(dict(params)))  # copy: the SDK adds the key to the dict it gets
        except serpapi.HTTPError as exc:
            try:
                return exc.response.json()  # SerpApi explains most failures in a JSON body
            except (AttributeError, ValueError):
                failure: Exception = exc
        except Exception as exc:  # network errors: their text holds the request URL
            failure = exc
        raise SearchFailed(redact(f"SerpApi did not answer: {failure}", self.settings.api_key)) from None

    def _log(self, params: dict[str, Any], data: dict[str, Any]) -> None:
        entry = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "key": cache_key(params),
            "engine": params.get("engine"),
            "params": {k: v for k, v in params.items() if k != "api_key"},
            "status": data.get("search_metadata", {}).get("status"),
            "error": data.get("error"),
        }
        with self.settings.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def account_status(settings: Settings | None = None) -> dict[str, Any]:
    """Searches left this month. The Account API is free and does not use a credit."""
    import urllib.request

    settings = settings or load_settings()
    if not settings.api_key:
        return {"mode": "replay"}
    url = f"https://serpapi.com/account.json?api_key={settings.api_key}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)
    return {
        "plan": data.get("plan_name"),
        "searches_left": data.get("total_searches_left"),
        "used_this_month": data.get("this_month_usage"),
    }
