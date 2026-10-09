import {
  LOAD_ERROR,
  cleanPrice,
  countryName,
  el,
  fmtDate,
  frame,
  listingsAndCountries,
  loadData,
  matchCount,
  monthName,
  plural,
  realCountries,
  recallLink,
  safeUrl,
  showError,
  snapshotNote,
} from "./data.js";

const TILES = 18;

// One tile per country first, India always shown, so the sheet shows how far the product has spread.
function pickListings(trail, count) {
  const withImage = trail.selling.filter((m) => m.thumbnail);
  const picked = [];
  const take = (m) => picked.length < count && !picked.includes(m) && picked.push(m);
  withImage.filter((m) => m.india).slice(0, 2).forEach(take);
  const seen = new Set();
  for (const m of withImage) {
    if (!seen.has(m.country)) {
      seen.add(m.country);
      take(m);
    }
  }
  withImage.forEach(take);
  return picked;
}

function caption(index, ...lines) {
  const [first, ...rest] = lines.filter(Boolean);
  return el(
    "p",
    { class: "tile-cap", style: `--i:${index}` },
    el("strong", {}, first),
    rest.map((line) => el("span", {}, line)),
  );
}

function recallTile(trail) {
  const r = trail.recall;
  return el(
    "li",
    { class: "tile tile-recall" },
    el(
      "a",
      { class: "tile-link frame", href: safeUrl(r.url), target: "_blank", rel: "noopener noreferrer" },
      el("img", { src: trail.recall_photo_local, alt: `Recall notice photo of ${r.product}`, width: 240, height: 240 }),
    ),
    caption(0, "The recall notice", "cpsc.gov", fmtDate(r.date)),
  );
}

// The country leads when the address shows one; otherwise the store name does, since it often names the country.
function tileLines(m) {
  const price = cleanPrice(m.price);
  return m.country === "XX" ? [m.source, price] : [countryName(m.country), m.source, price];
}

function listingTile(m, index) {
  return el(
    "li",
    { class: "tile" },
    el(
      "a",
      { class: "tile-link frame", href: safeUrl(m.link), target: "_blank", rel: "noopener noreferrer" },
      el("img", {
        src: m.thumbnail,
        alt: `Listing photo on ${m.source}, titled ${m.title}`,
        width: 240,
        height: 240,
      }),
    ),
    caption(index, ...tileLines(m, index)),
  );
}

// The one animated moment: captions appear one after another once the pictures are in.
function revealCaptions(sheet) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  sheet.classList.add("is-pending");
  const images = [...sheet.querySelectorAll("img")].slice(0, TILES);
  const ready = Promise.all(images.map((img) => img.decode().catch(() => null)));
  const timeout = new Promise((resolve) => setTimeout(resolve, 1500));
  Promise.race([ready, timeout]).then(() => {
    sheet.classList.replace("is-pending", "is-revealing");
  });
}

function renderHero(stats, trail) {
  const h = stats.headline;
  document.getElementById("hero-title").textContent =
    `Recalled in ${monthName(h.date)}. Still listed in ${h.countries} countries.`;
  const matches = h.matches_capped ? `${h.matches} or more` : `${h.matches}`;
  const shop = h.india_shopping;
  const unnamedInIndia = shop && shop.name && shop.results && shop.titled_with_name === 0;
  const lede = document.getElementById("hero-lede");
  lede.replaceChildren(
    el(
      "p",
      { class: "lede" },
      `${h.product} was recalled by the US Consumer Product Safety Commission on ${fmtDate(h.date)}. ` +
        `The notice gives the reason as "${h.risk}".`,
    ),
    el(
      "p",
      { class: "lede" },
      `One Google Lens search on the recall photo matched ${matches} pages, including ` +
        `${plural(h.live_listings, "store listing")} on ${plural(h.stores, "store")}. ` +
        (h.india_listings ? `${plural(h.india_listings, "listing")} sit on stores that sell in India. ` : "") +
        (h.recalled_brand && h.listings_titled_with_recalled_brand === 0
          ? `No listing title uses the name ${h.recalled_brand}. `
          : "") +
        (unnamedInIndia
          ? `Google Shopping India shows ${shop.results} results for the product, and none carries that name either.`
          : ""),
    ),
    el(
      "p",
      { class: "actions" },
      el("a", { class: "button", href: recallLink(trail) }, "See every listing"),
      el("a", { class: "button button-plain", href: "method.html" }, "How we found them"),
    ),
  );
  const tiles = pickListings(trail, TILES - 1);
  const sheet = document.getElementById("sheet");
  sheet.replaceChildren(recallTile(trail), ...tiles.map((m, i) => listingTile(m, i + 1)));
  revealCaptions(sheet);
}

function indiaCell(trail) {
  if (!trail.india.length) return el("span", { class: "none" }, "None found");
  return el("span", { class: "tag" }, plural(trail.india.length, "listing"));
}

// Phones hide the number columns; this line under the name carries the same counts.
function rowMeta(trail) {
  return el(
    "span",
    { class: "row-meta" },
    trail.selling.length ? listingsAndCountries(trail) : "No store listings",
    trail.india.length ? [" ", el("span", { class: "tag" }, `${trail.india.length} on India stores`)] : null,
  );
}

function recallRow(trail) {
  const r = trail.recall;
  const listings = trail.selling.length;
  return el(
    "tr",
    {},
    el("td", { class: "thumb-cell" }, frame(trail.recall_photo_local, "", "thumb")),
    el(
      "td",
      {},
      el("a", { class: "product-link", href: recallLink(trail) }, r.product),
      r.sold_on && el("span", { class: "row-sub" }, `Sold on ${r.sold_on}`),
      rowMeta(trail),
    ),
    el("td", { class: "secondary" }, fmtDate(r.date)),
    el(
      "td",
      { class: "num secondary" },
      listings ? listings.toLocaleString("en") : el("span", { class: "none" }, "None"),
    ),
    el(
      "td",
      { class: "num secondary" },
      !listings ? "" : realCountries(trail).length || el("span", { class: "none" }, "Not shown"),
    ),
    el("td", { class: "secondary" }, indiaCell(trail)),
  );
}

function tableHead() {
  return el(
    "thead",
    {},
    el(
      "tr",
      {},
      el("th", { scope: "col" }, el("span", { class: "visually-hidden" }, "Photo")),
      el("th", { scope: "col" }, "Recalled product"),
      el("th", { scope: "col", class: "secondary" }, "Recalled"),
      el("th", { scope: "col", class: "num secondary" }, "Store listings"),
      el("th", { scope: "col", class: "num secondary" }, "Countries"),
      el("th", { scope: "col", class: "secondary" }, "On India stores"),
    ),
  );
}

function recallTable(trails, label) {
  return el(
    "div",
    { class: "table-wrap", tabindex: "0", role: "region", "aria-label": label },
    el("table", { class: "data" }, tableHead(), el("tbody", {}, ...trails.map(recallRow))),
  );
}

function renderTable(stats, trails) {
  document.getElementById("table-intro").textContent =
    `${plural(stats.recalls_checked, "recall")} from 2026, one Google Lens search each. ` +
    `${stats.recalls_with_listings} of them have store listings. ` +
    "Plain-looking products, such as pool drain covers, also match other brands. " +
    "Open a recall to compare the photos.";
  const sorted = [...trails].sort((a, b) => b.selling.length - a.selling.length);
  const found = sorted.filter((t) => t.selling.length);
  const empty = sorted.filter((t) => !t.selling.length);
  const holder = document.getElementById("recall-tables");
  holder.replaceChildren(recallTable(found, "Recalls with store listings"));
  if (empty.length) {
    holder.append(
      el(
        "details",
        { class: "empty-group" },
        el("summary", {}, `${plural(empty.length, "recall")} returned no store listings`),
        recallTable(empty, "Recalls with no store listings"),
      ),
    );
  }
}

function renderFooter(doc) {
  document.getElementById("snapshot").textContent = snapshotNote(doc);
}

try {
  const { doc, stats, trails } = await loadData();
  const trail = trails.find((t) => t.recall.recall_id === stats.headline.recall_id);
  renderHero(stats, trail);
  renderTable(stats, trails);
  renderFooter(doc);
  document.title = `Relisted: ${matchCount(trail)} pages match one recalled product`;
} catch (error) {
  console.error(error);
  showError(LOAD_ERROR);
}
