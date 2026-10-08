from relisted import store


def trail(recall_id: str, listings: int) -> dict:
    return {"recall": {"recall_id": recall_id}, "selling": [{}] * listings}


def test_save_orders_trails_by_listings_and_load_reads_them_back(tmp_path):
    path = tmp_path / "data" / "trails.json"
    store.save({"1": trail("1", 2), "2": trail("2", 9)}, credits_spent=3, path=path)
    doc = store.load(path)
    assert list(doc["trails"]) == ["2", "1"]
    assert doc["credits_spent_this_run"] == 3
    assert doc["lens_searches"] == 2
    assert not list(path.parent.glob("*.tmp"))


def test_load_of_a_missing_file_is_empty(tmp_path):
    assert store.load(tmp_path / "nope.json") == {"generated_at": None, "trails": {}}
