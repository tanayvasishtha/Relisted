import pytest

from relisted.classify import (
    brand_aliases,
    brand_of,
    classify,
    country_of,
    domain_of,
    kind_of,
    product_terms,
)


def kind(title: str, link: str, price: str | None = None) -> str:
    return kind_of(title, link, domain_of(link), bool(price))


@pytest.mark.parametrize(
    "title, link, expected",
    [
        ("Baby Walker with Wheels", "https://www.amazon.co.uk/Baby-Walker/dp/B0ABC123/ref=x", "listing"),
        (
            "White Baby Walkers for sale - eBay",
            "https://www.ebay.com/b/White-Baby-Walkers/134282/bn_1",
            "store_page",
        ),
        ("Baby Walker | Ubuy", "https://www.ubuy.co.in/product/PFF7P9LOW-baby-walker", "listing"),
        (
            "ベビー用セーフティグッズ Uuoeebb ベビーウォーカー",
            "https://accuwisesolutions.in/pin/2b15a9071528",
            "spam",
        ),
        (
            "Wnttmt Baby Walkers Recalled Due to Risk",
            "https://www.cpsc.gov/Recalls/2026/Wnttmt-Baby-Walkers",
            "news",
        ),
        ("#Recall: Wnttmt Baby Walkers", "https://www.facebook.com/USCPSC/posts/recall-wnttmt", "social"),
        (
            "Wnttmt Baby Walkers recalled due to risk",
            "https://myparistexas.com/wnttmt-baby-walkers-recalled",
            "news",
        ),
        (
            "Baby Walker Adjustable Height",
            "https://oman.whizzcart.com/products/baby-walker-adjustable",
            "shop",
        ),
        ("Rocky Top Baby", "https://rockytopbaby.com/", "other"),
    ],
)
def test_kind_of(title, link, expected):
    assert kind(title, link) == expected


@pytest.mark.parametrize(
    "link", ["https://www.fedex.com/en-us/home", "https://www.wix.com/shop", "https://box.com/x"]
)
def test_domains_that_merely_contain_x_com_are_not_social(link):
    assert kind("Walker", link) != "social"


def test_store_names_match_whole_domain_labels_only():
    assert kind("Walker", "https://afternoon-tea.com/dp/123") != "listing"  # contains "noon", is not noon.com
    assert kind("Walker", "https://targetshoes.com/p/1") != "listing"


@pytest.mark.parametrize(
    "domain, country",
    [
        ("amazon.co.uk", "GB"),
        ("jp.mercari.com", "JP"),
        ("desertcart.in", "IN"),
        ("ubuy.co.in", "IN"),
        ("flipkart.com", "IN"),
        ("ebay.com", "US"),
        ("us.shein.com", "US"),
        ("amazon.com.mx", "MX"),
        ("ubuy.com.bo", "BO"),
        ("rockytopbaby.com", "XX"),  # a .com that does not say where it sells
        ("babybouncer.biz", "XX"),
        ("x.io", "XX"),
    ],
)
def test_country_of(domain, country):
    assert country_of(domain) == country


@pytest.mark.parametrize(
    "title, brand",
    [
        ("【Uuoeebb】ベビーウォーカー 折りたたみ", "Uuoeebb"),
        ("uuoeebb ベビーウォーカー K1018", "Uuoeebb"),
        ("PRVAETU Foldable Baby Walker with Wheels", "PRVAETU"),
        ("ABIOSER - Andador de bebé de altura ajustable", "ABIOSER"),
        ("Baby Walker Foldable With 6 Adjustable Heights", None),
        ("Las ruedas multifuncion", None),
        ("2026 Walker", None),
    ],
)
def test_brand_of(title, brand):
    assert brand_of(title) == brand


def test_product_terms_include_singular_and_plural():
    terms = product_terms("Wnttmt Baby Walkers")
    assert {"walker", "walkers", "wnttmt"} <= terms
    assert "baby" not in terms


def test_india_flag_needs_an_indian_store_that_sells():
    sells = classify(
        {"title": "Idealforce Baby Walker", "link": "https://www.ubuy.co.in/product/PFF7P9LOW-x"}
    )
    spam = classify({"title": "ベビーウォーカー", "link": "https://accuwisesolutions.in/pin/2b15a9071528"})
    assert sells.india and sells.selling
    assert not spam.india and spam.kind == "spam"


def test_unknown_shop_about_something_else_is_not_a_listing():
    item = {
        "title": "Dilex AHK 90 Degree Inside Corner Metal Tile Edging",
        "link": "https://brauns-bestattungen.de/shop/item/12",
        "price": {"value": "$12.64"},
    }
    assert classify(item).kind == "shop"
    assert classify(item, product_terms("Wnttmt Baby Walkers")).kind == "other"


def test_brand_aliases_count_copies_and_live_listings():
    def match(title, link):
        return classify({"title": title, "link": link})

    matches = [
        match("Uuoeebb Baby Walker", "https://www.amazon.de/dp/B0AAAAAAAA"),
        match("Uuoeebb Baby Walker", "https://jp.mercari.com/item/m1"),
        match("Uuoeebb ベビー", "https://scraper.example/pin/aabbccddee"),
        match("Zorbo Baby Walker", "https://www.ebay.com/itm/1"),
    ]
    aliases = brand_aliases(matches, recalled_brand="Wnttmt")
    assert aliases == [{"name": "Uuoeebb", "copies": 3, "live_listings": 2, "recalled": False}]
