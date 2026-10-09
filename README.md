# Relisted

Relisted takes the photo from a US product recall notice, asks Google Lens through SerpApi which pages carry it, and sorts the answer into store listings by country.

![The Relisted home page: the AiTuiTui recall notice photo beside store listings Google Lens matched to it, captioned by country](docs-img/hero.png)

Live site: https://tanayvasishtha.github.io/Relisted/

## What it found

The AiTuiTui pull-string teething toy was recalled in the US on 29 January 2026. The notice gives the reason as a risk of serious injury or death from choking, and says it was sold on Amazon. One Lens search on the recall photo matched 400 or more pages, including 117 store listings on 52 stores in 25 countries. Two of those listings are on Desertcart India. No listing title uses the name AiTuiTui.

Across the 42 recalls searched:

| | |
|---|---|
| Recalls with store listings | 26 |
| Recalls with three or more listings | 22 |
| Pages Lens matched | 5,141 |
| Store listings | 1,619 on 429 stores |
| Listings on stores that sell in India | 106, across 17 recalls |
| Pages left out as copies on unrelated sites | 742 |

These figures come from `relisted stats`, which reads the saved results. They are a snapshot from 9 October 2026.

## Why this matters

- An OECD sweep of online shops in 21 economies found that 87% of the banned or recalled products it inspected were still available to buy. [OECD](https://www.oecd.org/en/blogs/2026/03/why-consumer-product-safety-matters-more-than-ever-in-a-global-and-digital-marketplace.html)
- India has no single public recall database, and product safety sits with separate regulators. In February 2026 the consumer regulator fined Snapdeal Rs 5 lakh over toys that broke safety standards, and called reliance on sellers' own declarations inadequate. [ETV Bharat](https://www.etvbharat.com/en/business/snapdeal-fined-rs-5-lakh-for-selling-toys-violating-bis-standards-ccpa-enn26021603866)
- Which? found recalled products on Amazon.com, eBay and Wish, and reporting them as a shopper did not get them removed. [Which?](https://www.which.co.uk/news/article/amazon-com-ebay-and-wish-found-selling-dangerous-recalled-products-aDL7U9y1pbxw)

## How it works

1. Recalls. The US Consumer Product Safety Commission publishes its recalls as public JSON. No key and no SerpApi search is needed.
2. Priority. Products sold by marketplace sellers come first, then children's products, then fire and battery hazards.
3. Photo. Seller photos sit on a white backdrop, so Relisted picks the notice photo with the whitest border. Photos taken on a lab table are skipped: no store uses them, so Lens can only return other products that look similar.
4. Search. One Google Lens search through SerpApi, with `type=exact_matches`, on that photo. This is the only step that costs a SerpApi search.
5. Sorting. Rules read each match's address and title and label it a store listing, a shop, a store category page, news, a social post, a copy on an unrelated site, or other. Country comes from the store's address.
6. Trail. For each recall, the listings by country, the stores that sell in India, what was left out, and a link to the raw search result.

Every search is saved the first time it is paid for and never paid for twice. A credit cap stops any command from spending more than `RELISTED_MAX_CREDITS` searches, and `relisted account` shows what is left. Without a key the program replays the saved searches, so the whole demo runs offline.

## How SerpApi is used

The project depends on one engine, `google_lens`, with `type=exact_matches`. For each match it reads `link`, `source`, `title`, `price` and `thumbnail`. No other public source says which store pages carry a given photo, which is what the project needs.

A recall costs one search. The 42 searches behind this site, plus 6 test searches, make 48 paid in total, out of the 250 a month on the free plan. The raw response for each recall is published under `site/data/raw/`, so any count can be checked against what SerpApi returned. Lens returns at most 400 matches for one photo, and the pages say so where a recall reaches that limit.

## Run it

You need Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/tanayvasishtha/Relisted
cd Relisted
uv sync
uv run relisted serve
```

Open http://127.0.0.1:8000. With no key it shows the saved searches. To search live, copy `.env.example` to `.env` and set `SERPAPI_API_KEY`. The home page then lists recalls that have not been searched, each with a button that runs one Lens search and opens the result.

To rebuild the results:

```
uv run relisted candidates   # rank recalls and score their photos, free
uv run relisted sweep        # one Lens search per candidate, up to the credit cap
uv run relisted thumbs       # save thumbnails and raw responses for the site, free
uv run relisted stats        # print the numbers above, free
```

Tests and lint: `uv run pytest` and `uv run ruff check .`. Tests never call SerpApi.

## Limits

- A match is a lead. Lens matches the look of a photo. For a product with a distinctive shape, such as the teething toy, the matches are the same toy. For a plain-looking product, such as a pool drain cover or a coin battery, Lens also returns other brands' products. Compare the listing photo with the recall photo before acting.
- A listing can be out of stock or gone by now. The results are a snapshot.
- The country comes from the store's web address. Ubuy and Desertcart run a separate storefront for each country, which raises country counts. A plain .com address does not say where a shop sells, so those listings are grouped as country not shown.
- A listing counts as sold in India only when it is a product page on a known store that sells there. An unknown shop with a .in address does not count.
- The reason shown for each recall comes from the recall's title. CPSC's long hazard paragraph is not used, because some records carry another recall's text. Recall 10579, the teething toy, holds the paragraph for the hair-serum recall filed just before it.
- Recalls whose notices only have lab photos are not searched, so the sweep undercounts.
- The recalled-name check uses the first word of CPSC's product name.
- The sorting rules can be wrong. A small shop can be filed as a copy, and a copy can pass as a shop.

Nothing here says a seller knew about a recall or did anything wrong. The listings are for a person to review.

## Data and licences

Recall notices are US government public data. Listing pages and thumbnails belong to their stores, and are linked and shown small for identification. The Archivo typeface is under the SIL Open Font License. The code is under the MIT licence.

Built for the SerpApi India Hackathon 2026, Knowledge and Public Interest track.
