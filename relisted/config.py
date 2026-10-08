"""Paths and settings, read once from the environment and .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    replay: bool
    max_credits: int
    data_dir: Path

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def ledger_path(self) -> Path:
        return self.data_dir / "ledger.jsonl"

    @property
    def mode(self) -> str:
        return "replay" if self.replay else "live"


def load_settings() -> Settings:
    env = {**_read_dotenv(ROOT / ".env"), **os.environ}
    key = env.get("SERPAPI_API_KEY") or None
    if key == "paste_your_key_here":
        key = None
    replay = key is None or env.get("RELISTED_REPLAY", "0") == "1"
    return Settings(
        api_key=key,
        replay=replay,
        max_credits=int(env.get("RELISTED_MAX_CREDITS", "10")),
        data_dir=Path(env.get("RELISTED_DATA_DIR", ROOT / "data")),
    )
