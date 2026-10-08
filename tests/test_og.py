from PIL import Image

from relisted import og


def make_site(tmp_path):
    site = tmp_path / "site"
    (site / "thumbs").mkdir(parents=True)
    Image.new("RGB", (120, 90), "white").save(site / "thumbs" / "a.jpg")
    return site


def listing(country, india=False):
    return {"thumbnail": "thumbs/a.jpg", "country": country, "india": india}


def test_pick_thumbnails_puts_india_first_then_one_listing_per_country():
    trail = {
        "selling": [listing("MX"), listing("MX"), listing("IN", india=True), listing("BR"), listing("MX")]
    }
    assert [m for m in og.pick_thumbnails(trail, 5)] == ["thumbs/a.jpg"] * 3  # India, MX, BR


def test_pick_thumbnails_skips_listings_without_a_picture():
    trail = {"selling": [{"thumbnail": None, "country": "MX", "india": False}, listing("BR")]}
    assert len(og.pick_thumbnails(trail, 5)) == 1


def test_render_draws_a_1200_by_630_preview(tmp_path):
    site = make_site(tmp_path)
    trail = {"recall_photo_local": "thumbs/a.jpg", "selling": [listing("MX"), listing("IN", india=True)]}
    stats = {"headline": {"date": "2026-01-29", "countries": 25}}
    out = og.render(stats, trail, tmp_path / "out" / "og.png", site)
    assert Image.open(out).size == (1200, 630)
