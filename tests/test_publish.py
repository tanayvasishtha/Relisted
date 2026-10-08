import io
import json

from PIL import Image

from relisted import publish
from relisted.config import Settings


def png(colour, size=(120, 90)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def make_trail(search_key: str) -> dict:
    def match(src):
        return {"domain": "shop.test", "thumbnail": src, "kind": "listing", "india": False}

    return {
        "recall": {"recall_id": "42"},
        "recall_photo_url": "https://cpsc.test/photo.png",
        "search_key": search_key,
        "selling": [match("https://img.test/a.jpg"), match("https://img.test/gone.jpg"), match(None)],
        "india": [match("https://img.test/a.jpg")],
    }


def settings_for(tmp_path) -> Settings:
    return Settings(api_key=None, replay=True, max_credits=0, data_dir=tmp_path / "data")


def test_publish_trail_makes_the_trail_self_contained(tmp_path, monkeypatch):
    settings = settings_for(tmp_path)
    site = tmp_path / "site"
    settings.cache_dir.mkdir(parents=True)
    raw = {
        "search_metadata": {"status": "Success", "json_endpoint": "https://serpapi.test/searches/1.json"},
        "exact_matches": [{"title": "x"}],
    }
    (settings.cache_dir / "google_lens_abc.json").write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(publish, "download", lambda url, settings=None: png("white"))
    pictures = {"https://img.test/a.jpg": Image.new("RGB", (800, 600), "grey")}
    monkeypatch.setattr(publish, "fetch_image", pictures.get)

    trail = publish.publish_trail(make_trail("google_lens_abc"), settings, site)

    assert trail["recall_photo_local"] == "thumbs/recall-42.jpg"
    assert (site / "thumbs" / "recall-42.jpg").exists()
    published = json.loads((site / trail["raw_json"]).read_text(encoding="utf-8"))
    assert published["exact_matches"] == [{"title": "x"}]
    assert "json_endpoint" not in published["search_metadata"]

    shown, gone, missing = trail["selling"]
    assert (site / shown["thumbnail"]).exists()
    assert Image.open(site / shown["thumbnail"]).width == publish.THUMB_WIDTH  # downscaled, not copied
    assert gone["thumbnail"] is None and gone["thumbnail_src"] == "https://img.test/gone.jpg"
    assert missing["thumbnail"] is None
    assert trail["india"][0]["thumbnail"] == shown["thumbnail"]


def test_publish_is_repeatable_and_keeps_the_original_thumbnail_url(tmp_path, monkeypatch):
    settings = settings_for(tmp_path)
    site = tmp_path / "site"
    monkeypatch.setattr(publish, "download", lambda url, settings=None: png("white"))
    monkeypatch.setattr(publish, "fetch_image", lambda url: Image.new("RGB", (50, 50), "white"))

    trail = publish.publish_trail(make_trail("missing_key"), settings, site)
    assert trail["raw_json"] is None  # no recording to copy, and no crash
    first = trail["selling"][0]
    assert first["thumbnail_src"] == "https://img.test/a.jpg"

    publish.publish_trail(trail, settings, site)  # second run starts from the rewritten trail
    assert trail["selling"][0]["thumbnail_src"] == "https://img.test/a.jpg"
    assert trail["selling"][0]["thumbnail"] == first["thumbnail"]


def test_thumb_path_is_stable_and_local():
    assert publish.thumb_path("https://img.test/a.jpg") == publish.thumb_path("https://img.test/a.jpg")
    assert publish.thumb_path("https://img.test/a.jpg").startswith("thumbs/")
