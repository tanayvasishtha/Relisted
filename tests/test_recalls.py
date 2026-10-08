import json
from pathlib import Path

import pytest

from relisted.recalls import SOLD_ON, normalise, priority, store_name

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def sample():
    raw = json.loads((FIXTURES / "cpsc_sample.json").read_text(encoding="utf-8"))
    return {str(r["RecallID"]): normalise(r) for r in raw}


def test_normalise_walker(sample):
    walker = sample["10901"]
    assert walker.product.startswith("Wnttmt Baby Walkers")
    assert walker.date == "2026-08-06"
    assert walker.sold_on == "Amazon"
    assert walker.seller == "WURUI.BABY"
    assert walker.kids and walker.marketplace and not walker.fire
    assert len(walker.photos) == 2
    assert walker.photos[0].url.startswith("https://www.cpsc.gov/")


def test_store_name_is_canonical(sample):
    assert sample["10857"].sold_on == "Walmart"  # the title says Walmart.com


def test_target_exclusive_is_not_a_marketplace_recall(sample):
    target = sample["10976"]
    assert target.sold_on is None
    assert not target.marketplace


@pytest.mark.parametrize(
    "title, store, seller",
    [
        ("Dressers Recalled; Sold on Amazon by Chenyuanhui", "Amazon", "Chenyuanhui"),
        ("Power Banks Recalled; Sold Exclusively on Amazon.com", "Amazon", None),
        ("Helmets Recalled; Sold on Temu by Foubeaka and Geniuss", "Temu", "Foubeaka and Geniuss"),
        ("Baby Gyms Recalled; Sold on TikTok Shop", "TikTok Shop", None),
        ("Toys Recalled; Sold on Walmart.com by Wonder Stone Toys", "Walmart", "Wonder Stone Toys"),
    ],
)
def test_sold_on_parsing(title, store, seller):
    match = SOLD_ON.search(title)
    assert match is not None
    assert store_name(match.group(1)) == store
    assert (match.group(2) or None) == seller


def test_priority_puts_marketplace_children_recalls_first(sample):
    ranked = sorted(sample.values(), key=priority, reverse=True)
    assert ranked[-1].recall_id == "10976"
    assert priority(sample["10901"]) > priority(sample["10976"])
