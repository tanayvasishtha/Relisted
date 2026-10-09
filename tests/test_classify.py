import pytest

from relisted.classify import (
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
        (
            "15 children have choked on these popular teething toys",
            "https://www.pennlive.com/news/2026/01/15-children-have-choked.html",
            "news",
        ),
        ("Teething toys, a buyer guide", "https://parenting.example/blog/best-teething-toys.html", "news"),
        (
            "EEMB CR1620 Battery India | Ubuy",
            "https://www.ubuy.co.in/productuk/4Y29HM4XS-eemb-cr1620",
            "listing",
        ),
        ("Best Toys For Babies", "https://www.orthomedhospital.in/product/review/19546788041170", "spam"),
        ("Sneakers for Boys", "https://in.dhgate.com/product/sole-soft-sneakers/1111886990.html", "listing"),
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


def test_product_terms_include_singular_and_plural():
    terms = product_terms("Wnttmt Baby Walkers")
    assert {"walker", "walkers", "wnttmt"} <= terms
    assert "baby" not in terms


def test_an_unknown_indian_shop_is_not_counted_as_sold_in_india():
    shop = classify(
        {"title": "malker bike light set", "link": "https://shoptheworld.in/products/malker-bike-light-set"}
    )
    assert shop.kind == "shop" and shop.country == "IN" and not shop.india


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


@pytest.mark.parametrize(
    "domain, country",
    [
        ("brunei.desertcart.com", "BN"),
        ("liberia.ubuy.com", "LR"),
        ("barbabos.ubuy.com", "BB"),  # Ubuy's own spelling
        ("kuwait.whizzcart.com", "KW"),
        ("brunei.example.com", "XX"),  # only stores known to run country storefronts
        ("shop.example.eu", "XX"),  # .eu serves a union, not one country
        ("ar.dhgate.com", "XX"),  # a language subdomain, not a country
    ],
)
def test_country_storefronts_and_non_countries(domain, country):
    assert country_of(domain) == country


def test_a_story_telling_readers_to_stop_using_a_product_is_news():
    title = "If you bought this infant walker on Amazon, stop using it immediately"
    assert kind(title, "https://www.silive.com/news/2026/03/walker.html") == "news"
    assert kind(title, "https://www.silive.com/2026/03/walker.html", price=None) == "news"


def test_a_malformed_link_does_not_crash_the_run():
    match = classify({"title": "Baby Walker", "link": "https://[www.broken.test/item/1"})
    assert match.domain == "" and match.kind in {"other", "shop"}
