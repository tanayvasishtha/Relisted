"""US CPSC recalls: fetch (free public API, no key) and normalise."""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Settings, load_settings

CPSC_URL = "https://www.saferproducts.gov/RestWebServices/Recall?format=json&RecallDateStart={start}"

SOLD_ON = re.compile(r"Sold (?:Exclusively )?on ([A-Za-z][A-Za-z .]+?)(?: by ([^;:]+?))?\s*(?:;|$)", re.I)
KIDS = re.compile(
    r"\b(infant|baby|babies|child|children|toddler|kid|crib|stroller|walker|teeth|teething|toy|toys|"
    r"lounger|nursing pillow|bassinet|high ?chair|bath seat|doll|pacifier|rattle)\b",
    re.I,
)
FIRE = re.compile(r"\b(fire|burn|battery|batteries|power bank|charger|lithium|electrocution|shock)\b", re.I)


@dataclass
class Photo:
    url: str
    caption: str


@dataclass
class Recall:
    recall_id: str
    number: str
    date: str
    title: str
    url: str
    product: str
    risk: str
    standard: str | None
    units: str
    sold_on: str | None
    seller: str | None
    countries: list[str] = field(default_factory=list)
    photos: list[Photo] = field(default_factory=list)

    @property
    def kids(self) -> bool:
        return bool(KIDS.search(f"{self.title} {self.product}"))

    @property
    def fire(self) -> bool:
        return bool(FIRE.search(self.title))

    @property
    def marketplace(self) -> bool:
        return self.sold_on is not None

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(kids=self.kids, fire=self.fire, marketplace=self.marketplace)
        return d


STORE_NAMES = {
    "amazon": "Amazon",
    "amazon.com": "Amazon",
    "walmart": "Walmart",
    "walmart.com": "Walmart",
    "temu": "Temu",
    "tiktok shop": "TikTok Shop",
    "ebay": "eBay",
    "target": "Target",
    "etsy": "Etsy",
    "shein": "Shein",
}


def store_name(raw: str) -> str:
    """Canonical store name for the text after 'Sold on' in a recall title."""
    clean = raw.strip().rstrip(".")
    return STORE_NAMES.get(clean.lower(), clean)


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:].lower()


def title_parts(title: str) -> tuple[str, str | None]:
    """The risk and the standard violated, as the recall's own title states them.

    CPSC's long hazard paragraph is not used: some records carry another recall's text.
    The teething-toy recall 10579, for one, holds the hair-serum paragraph of recall 10578.
    """
    segments = [s.strip() for s in title.split(";")]
    due = re.search(r"\bDue to\s+(.+)$", segments[0], re.I)
    violated = next((s for s in segments[1:] if re.match(r"Violates?\s", s, re.I)), None)
    risk = sentence_case(due.group(1)) if due else ""
    standard = sentence_case(re.sub(r"^Violates?\s+", "", violated, flags=re.I)) if violated else None
    return risk, standard


def normalise(raw: dict) -> Recall:
    title = (raw.get("Title") or "").strip()
    products = raw.get("Products") or [{}]
    sold = SOLD_ON.search(title)
    risk, standard = title_parts(title)
    return Recall(
        recall_id=str(raw.get("RecallID")),
        number=str(raw.get("RecallNumber") or ""),
        date=(raw.get("RecallDate") or "")[:10],
        title=title,
        url=raw.get("URL") or "",
        product=(products[0].get("Name") or "").strip(),
        risk=risk,
        standard=standard,
        units=(products[0].get("NumberOfUnits") or "").strip(),
        sold_on=store_name(sold.group(1)) if sold else None,
        seller=sold.group(2).strip() if sold and sold.group(2) else None,
        countries=[c.get("Country", "") for c in raw.get("ManufacturerCountries") or [] if c.get("Country")],
        photos=[
            Photo(i["URL"], (i.get("Caption") or "").strip()) for i in raw.get("Images") or [] if i.get("URL")
        ],
    )


def raw_path(settings: Settings, start: str) -> Path:
    return (
        settings.raw_dir / f"cpsc_{start[:4]}.json"
        if start.endswith("-01-01")
        else settings.raw_dir / f"cpsc_{start}.json"
    )


def fetch(start: str = "2026-01-01", settings: Settings | None = None, refresh: bool = False) -> list[Recall]:
    """Recalls announced on or after `start`. Cached on disk; the CPSC API is free either way."""
    settings = settings or load_settings()
    path = raw_path(settings, start)
    if refresh or not path.exists():
        with urllib.request.urlopen(CPSC_URL.format(start=start), timeout=90) as resp:
            data = json.load(resp)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    recalls = [normalise(r) for r in data]
    return sorted(recalls, key=lambda r: (r.date, r.recall_id), reverse=True)


def priority(recall: Recall) -> int:
    """Higher means more likely to be relisted by marketplace sellers and worth a search."""
    score = 0
    if recall.marketplace:
        score += 3
    if recall.kids:
        score += 2
    if recall.fire:
        score += 1
    if recall.photos:
        score += 1
    return score
