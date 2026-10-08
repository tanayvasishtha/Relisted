"""trails.json: the one file the website reads. Written atomically, keyed by recall id."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .config import ROOT
from .hunt import Trail

TRAILS_PATH = ROOT / "site" / "data" / "trails.json"


def load(path: Path = TRAILS_PATH) -> dict:
    if not path.exists():
        return {"generated_at": None, "trails": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save(trails: dict[str, dict], credits_spent: int, path: Path = TRAILS_PATH) -> dict:
    doc = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "lens_searches": len(trails),
        "credits_spent_this_run": credits_spent,
        "trails": dict(sorted(trails.items(), key=lambda kv: -len(kv[1]["selling"]))),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return doc


def upsert(trail: Trail, credits_spent: int = 0, path: Path = TRAILS_PATH) -> dict:
    doc = load(path)
    trails = doc.get("trails", {})
    trails[trail.recall["recall_id"]] = trail.to_dict()
    return save(trails, credits_spent, path)
