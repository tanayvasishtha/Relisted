"""Deterministic rules that turn raw Lens matches into evidence.

Each match is labelled as a store listing, a store category page, an unverified
shop, news or social coverage, or spam (hijacked SEO pages that copy listings).
No model is involved: every label comes from the domain, the URL path and the title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

# Known marketplaces and retailers, keyed by their domain label, with the URL shape of one product page.
STORES: dict[str, re.Pattern[str]] = {
    "amazon": re.compile(r"/dp/|/gp/product/"),
    "ebay": re.compile(r"/itm/"),
    "walmart": re.compile(r"/ip/"),
    "shein": re.compile(r"-p-\d+|/[A-Za-z0-9-]{20,}"),
    "temu": re.compile(r"-g-\d+"),
    "aliexpress": re.compile(r"/item/"),
    "etsy": re.compile(r"/listing/"),
    "mercari": re.compile(r"/item/"),
    "mercadolibre": re.compile(r"ML[A-Z]-?\d+|/p/"),
    "ubuy": re.compile(r"/product[a-z]{0,3}/"),
    "dhgate": re.compile(r"/product/|/goods/"),
    "desertcart": re.compile(r"/products/"),
    "flipkart": re.compile(r"/p/"),
    "meesho": re.compile(r"/p/"),
    "firstcry": re.compile(r"/\d{5,}"),
    "snapdeal": re.compile(r"/product/"),
    "indiamart": re.compile(r"/proddetail/"),
    "jiomart": re.compile(r"/p/"),
    "bedbathandbeyond": re.compile(r"/[A-Za-z0-9-]{15,}"),
    "target": re.compile(r"/-/A-\d+"),
    "wayfair": re.compile(r"\.html"),
    "pacifiko": re.compile(r"/compras-en-linea/"),
    "jumia": re.compile(r"\.html"),
    "noon": re.compile(r"/p/"),
    "lazada": re.compile(r"-i\d+"),
    "shopee": re.compile(r"-i\.\d+"),
    "offerup": re.compile(r"/item/"),
    "karrotmarket": re.compile(r"/"),
    "kmart": re.compile(r"/product/"),
    "argos": re.compile(r"/product/"),
    "babylist": re.compile(r"/gp/"),
    "tiktok": re.compile(r"/shop/pdp/"),
}

# Stores that sell in India, whatever their top-level domain.
INDIAN_STORES = frozenset(
    "flipkart meesho firstcry myntra snapdeal jiomart indiamart tatacliq ajio nykaa shopsy babyhug hopscotch "
    "limeroad paytmmall bigbasket blinkit zepto".split()
)

NEWS_DOMAINS = (
    "cpsc.gov saferproducts.gov recalls.gov canada.ca gc.ca accc.gov.au productsafety.gov.au usatoday.com "
    "people.com yahoo.com aol.com msn.com consumerreports.org consumeraffairs.com parents.com babycenter.com "
    "recallseeker.com cnn.com bbc.com bbc.co.uk nbcnews.com cbsnews.com foxnews.com govdelivery.com "
    "buttondown.com which.co.uk"
).split()
NEWS_TOKEN = re.compile(r"(^|[.-])(news|times|herald|tribune|gazette|radio|press)([.-]|$)")
RECALL_WORDS = re.compile(r"\brecall(?:ed|s)?\b|safety (?:alert|notice|warning)", re.I)
SOCIAL_DOMAINS = (
    "facebook.com instagram.com twitter.com x.com reddit.com youtube.com pinterest.com threads.net "
    "linkedin.com"
).split()

# URL shapes used by hijacked domains that republish scraped marketplace listings.
SPAM_PATH = re.compile(
    r"\?productSearch|/pin/[0-9a-f]{6,}|\?goods/|[?&](?:h|r|c)=\d{6,}|/details/[0-9a-f]{6,}|/ajax/|\?shop/|"
    r"/shopdetail/|/product/category/\d+|/dp/a\d+|/category/item/|/listing/[a-z0-9-]+-p\d{8,}|"
    r"/product-similar-image/|pictureSearch|manufacturer-site|[?&][a-z]=\d{10,}|\d{13,}",
    re.I,
)
CJK = re.compile("[぀-ヿ㐀-鿿가-힯]")
CJK_TLDS = frozenset({"jp", "cn", "kr", "tw", "hk"})
PRODUCT_PATH = re.compile(r"/products?/|/item/|/p/|/dp/|/itm/|/listing/|\.html", re.I)

UNKNOWN_COUNTRY = "XX"
# Stores whose .com site is a US storefront. Any other .com says nothing about where it sells.
US_STORES = frozenset(
    "amazon ebay walmart target etsy wayfair offerup bedbathandbeyond kmart babylist".split()
)
# Two-letter domain endings that are used as generic names, not countries.
GENERIC_CC = frozenset(
    "io ai tv me cc ly to fm ws la tk ml ga cf gq pw sh vc gg ac ms nu so st su tf gl gs mn bz sx".split()
)
# Country subdomains used by marketplaces, such as jp.mercari.com and us.shein.com.
COUNTRY_SUBDOMAINS = frozenset({"jp", "us", "uk", "in", "de", "fr", "it", "es", "mx", "br", "ca", "au"})
ISO_FIX = {"uk": "GB"}

# Words that are not a brand when they open a recalled product's name.
NOT_A_BRAND = frozenset(
    "a an the new baby babies infant kids kid child children toddler boy girl adult".split()
)


@dataclass
class Match:
    title: str
    link: str
    source: str
    domain: str
    kind: str  # listing | store_page | shop | news | social | spam | other
    country: str
    price: str | None
    thumbnail: str | None

    @property
    def india(self) -> bool:
        """A product page on a known store that sells in India. Unknown shops never count."""
        return self.country == "IN" and self.kind == "listing"

    @property
    def selling(self) -> bool:
        return self.kind in {"listing", "shop"}


def domain_of(link: str) -> str:
    host = (urlparse(link).hostname or "").lower()
    return host.removeprefix("www.")


def path_of(link: str) -> str:
    parsed = urlparse(link)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def _is_domain(domain: str, names: list[str]) -> bool:
    return any(domain == n or domain.endswith(f".{n}") for n in names)


def country_of(domain: str) -> str:
    """ISO country code for a store domain, or XX when the domain does not say."""
    labels = domain.split(".")
    if any(label in INDIAN_STORES for label in labels):
        return "IN"
    if len(labels) > 2 and labels[0] in COUNTRY_SUBDOMAINS:
        return ISO_FIX.get(labels[0], labels[0].upper())
    tld = labels[-1]
    if len(tld) == 2 and tld not in GENERIC_CC:
        return ISO_FIX.get(tld, tld.upper())
    return "US" if US_STORES & set(labels) else UNKNOWN_COUNTRY


def store_name(domain: str) -> str | None:
    """The known store whose name is a whole label of this domain (amazon in amazon.co.uk)."""
    labels = set(domain.split("."))
    return next((name for name in STORES if name in labels), None)


def kind_of(title: str, link: str, domain: str, has_price: bool) -> str:
    path = path_of(link)
    if _is_domain(domain, SOCIAL_DOMAINS):
        return "social"
    if _is_domain(domain, NEWS_DOMAINS) or NEWS_TOKEN.search(domain):
        return "news"
    if store := store_name(domain):
        return "listing" if STORES[store].search(path) else "store_page"
    if RECALL_WORDS.search(title):
        return "news"
    if SPAM_PATH.search(path) or (CJK.search(title) and domain.rsplit(".", 1)[-1] not in CJK_TLDS):
        return "spam"
    if has_price or PRODUCT_PATH.search(path):
        return "shop"
    return "other"


def product_terms(product: str) -> set[str]:
    """Nouns from the recalled product name, singular and plural, used to keep unknown shops honest."""
    filler = {
        "baby",
        "babies",
        "infant",
        "kids",
        "child",
        "children",
        "toddler",
        "with",
        "sets",
        "pack",
        "recalled",
    }
    words = {w for w in re.findall(r"[a-z]{4,}", product.lower()) if w not in filler}
    return words | {w[:-1] for w in words if w.endswith("s")} | {w + "s" for w in words}


def classify(item: dict, terms: set[str] | None = None) -> Match:
    title = item.get("title") or ""
    link = item.get("link") or ""
    domain = domain_of(link)
    price = item.get("price")
    price_text = price.get("value") if isinstance(price, dict) else price
    kind = kind_of(title, link, domain, bool(price_text))
    if kind == "shop" and terms and not any(t in title.lower() for t in terms):
        kind = "other"  # an unknown site whose page is about something else entirely
    return Match(
        title=title,
        link=link,
        source=item.get("source") or domain,
        domain=domain,
        kind=kind,
        country=country_of(domain),
        price=price_text,
        thumbnail=item.get("thumbnail"),
    )
