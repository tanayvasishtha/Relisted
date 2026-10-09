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
  plural,
  realCountries,
  safeUrl,
  showError,
  snapshotNote,
} from "./data.js";

const external = { target: "_blank", rel: "noopener noreferrer" };

function fact(term, ...description) {
  return [el("dt", {}, term), el("dd", {}, ...description)];
}

function renderFacts(trail) {
  const r = trail.recall;
  document.title = `Relisted: ${r.product}`;
  document.getElementById("band").textContent =
    `Recalled ${fmtDate(r.date)} by the US Consumer Product Safety Commission`;
  document.getElementById("recall-photo").replaceChildren(
    el("img", { src: trail.recall_photo_local, alt: `Recall notice photo of ${r.product}`, width: 600, height: 600 }),
  );
  document.getElementById("recall-name").textContent = r.product;
  const sold = r.sold_on ? (r.seller ? `${r.sold_on}, by ${r.seller}` : r.sold_on) : null;
  document.getElementById("facts").replaceChildren(
    ...[
      r.risk && fact("Why it was recalled", r.risk),
      r.standard && fact("Standard CPSC says it violates", r.standard),
      r.units && fact("Units sold in the US", r.units),
      sold && fact("Sold on", sold),
      fact("Recall notice", el("a", { href: safeUrl(r.url), ...external }, `CPSC recall ${r.number}`)),
      fact(
        trail.india_shopping ? "These searches" : "This search",
        trail.india_shopping
          ? "One Google Lens search and one Google Shopping India search, through SerpApi. "
          : "One Google Lens search through SerpApi. ",
        trail.raw_json && el("a", { href: trail.raw_json }, "Read the raw Lens result"),
      ),
    ]
      .filter(Boolean)
      .flat(),
  );
}

function renderCounts(trail) {
  const listings = trail.selling.length;
  const countries = realCountries(trail).length;
  document.getElementById("claim").textContent = listings
    ? listingsAndCountries(trail)
    : "No store listings found in this search";
  const counts = [
    ["Pages Lens matched", matchCount(trail)],
    ["Store listings", listings],
    ["Stores", trail.stores],
    ["Countries", countries],
  ];
  document.getElementById("counts").replaceChildren(
    ...counts.map(([label, value]) => el("div", {}, el("dt", {}, label), el("dd", {}, String(value)))),
  );
}

function listingRow(m) {
  return el(
    "tr",
    {},
    el("td", { class: "thumb-cell" }, frame(m.thumbnail, "", "thumb thumb-large")),
    el(
      "td",
      {},
      el("a", { class: "listing-title", href: safeUrl(m.link), ...external }, m.title || m.link),
      el("span", { class: "row-sub" }, m.source),
    ),
    el("td", { class: "num" }, cleanPrice(m.price)),
  );
}

// Titles wrap, so these tables fit any width and the wrapper needs no tab stop of its own.
function listingTable(matches, label) {
  return el(
    "div",
    { class: "table-wrap" },
    el(
      "table",
      { class: "data" },
      el("caption", { class: "visually-hidden" }, label),
      el(
        "thead",
        { class: "visually-hidden" },
        el("tr", {}, el("th", {}, "Photo"), el("th", {}, "Listing"), el("th", {}, "Price")),
      ),
      el("tbody", {}, ...matches.map(listingRow)),
    ),
  );
}

function listOf(names, most = 3) {
  const shown = names.slice(0, most);
  const rest = names.length - shown.length;
  if (rest > 0) return `${shown.join(", ")} and ${plural(rest, "more store", "more stores")}`;
  return shown.length > 1 ? `${shown.slice(0, -1).join(", ")} and ${shown.at(-1)}` : shown.join("");
}

function nameLine(s) {
  if (s.name == null) return "The name is not counted: the product name does not start with a word that names a brand.";
  if (s.titled_with_name === 0) return `None of them carries the name ${s.name}.`;
  return `${plural(s.titled_with_name, "result")} ${s.titled_with_name === 1 ? "carries" : "carry"} the name ${s.name}.`;
}

// The two questions side by side: what a search for the name shows in India, and what the photo finds.
function renderNameCheck(trail) {
  const holder = document.getElementById("name-check");
  const s = trail.india_shopping;
  if (!s) return holder.replaceChildren();
  const india = trail.india.length;
  holder.replaceChildren(
    el("h3", { class: "subtitle" }, "Search by name, search by photo"),
    el(
      "p",
      { class: "note" },
      el("strong", {}, "Google Shopping India, by name. "),
      s.results
        ? `"${s.query}" shows ${plural(s.results, "result")} from ${listOf(s.stores.map(([name]) => name))}. ${nameLine(s)} `
        : `"${s.query}" shows no results. `,
      s.raw_json && el("a", { href: s.raw_json }, "Read the raw result"),
    ),
    el(
      "p",
      { class: "note" },
      el("strong", {}, "Google Lens, by photo. "),
      india
        ? `${plural(india, "listing")} on stores that sell in India, shown below.`
        : "No listing on a store that sells in India.",
    ),
  );
}

function reportBox(trail) {
  const toy = /\btoys?\b/i.test(trail.recall.product);
  return el(
    "div",
    { class: "report" },
    el("h4", { class: "group-title" }, "Report it in India"),
    el(
      "ul",
      {},
      el(
        "li",
        {},
        "National Consumer Helpline: call 1915, or file a complaint at ",
        el("a", { href: "https://consumerhelpline.gov.in/", ...external }, "consumerhelpline.gov.in"),
        ".",
      ),
      toy &&
        el(
          "li",
          {},
          "Toys for children up to 14 must carry the ISI mark under the Toys (Quality Control) Order, 2020. " +
            "Report one without it through the ",
          el(
            "a",
            { href: "https://www.services.bis.gov.in/php/BIS_2.0/BISBlog/bis-care-app/", ...external },
            "BIS Care app",
          ),
          ".",
        ),
      el("li", {}, "Tell the store as well. Compare the listing photo with the recall photo before you report it."),
    ),
  );
}

function renderIndia(trail) {
  const holder = document.getElementById("india");
  if (!trail.india.length) return holder.replaceChildren();
  holder.replaceChildren(
    el(
      "h3",
      { class: "subtitle" },
      "Stores that sell in India ",
      el("span", { class: "tag" }, plural(trail.india.length, "listing")),
    ),
    listingTable(trail.india, "Listings on stores that sell in India"),
    reportBox(trail),
  );
}

const CSV_COLUMNS = ["country", "store", "title", "price", "link", "on_a_store_that_sells_in_india"];

function csvCell(value) {
  let text = String(value ?? "");
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`; // a spreadsheet must never run a listing title as a formula
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function csvLink(trail) {
  const rows = trail.selling.map((m) => [
    countryName(m.country),
    m.source,
    m.title,
    cleanPrice(m.price),
    m.link,
    m.india ? "yes" : "no",
  ]);
  const text = [CSV_COLUMNS, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿", text], { type: "text/csv;charset=utf-8" }));
  return el(
    "a",
    { class: "button button-plain", href: url, download: `relisted-${trail.recall.recall_id}-listings.csv` },
    "Download the listings (CSV)",
  );
}

// Groups by the country the store's address points to, biggest first; unknown last.
function renderListings(trail) {
  const holder = document.getElementById("listings");
  if (!trail.selling.length) {
    holder.replaceChildren(
      el(
        "p",
        { class: "note" },
        "Lens found no store listing for this photo in this search. The product may still be sold with other photos.",
      ),
    );
    return;
  }
  const groups = new Map();
  for (const m of trail.selling) groups.set(m.country, [...(groups.get(m.country) || []), m]);
  const ordered = [...groups.entries()].sort(
    ([a, listA], [b, listB]) => (a === "XX") - (b === "XX") || listB.length - listA.length,
  );
  holder.replaceChildren(
    el("h3", { class: "subtitle" }, "Every store listing"),
    el("p", { class: "actions csv" }, csvLink(trail)),
    ...ordered.flatMap(([code, matches]) => [
      el(
        "h4",
        { class: "group-title" },
        countryName(code),
        " ",
        el("span", { class: "count" }, matches.length),
      ),
      listingTable(matches, `Listings in ${countryName(code)}`),
    ]),
  );
}

function renderLeftOut(trail) {
  const k = trail.kinds;
  const parts = [
    [k.spam, "copy of the listing on an unrelated site", "copies of the listing on unrelated sites"],
    [k.news, "news story", "news stories"],
    [k.social, "social post", "social posts"],
    [k.store_page, "store category page", "store category pages"],
    [k.other, "other page that is not a listing", "other pages that are not listings"],
  ]
    .filter(([count]) => count)
    .map(([count, one, many]) => plural(count, one, many));
  const holder = document.getElementById("left-out");
  if (!parts.length) return holder.replaceChildren();
  holder.replaceChildren(
    el("h3", { class: "subtitle" }, "What we left out"),
    el(
      "p",
      { class: "note" },
      `Of the ${matchCount(trail)} ${trail.matches_total === 1 ? "page" : "pages"} Lens matched, ` +
        `these are not counted as store listings: ${parts.join(", ")}. ` +
        "They stay in the raw result.",
    ),
  );
}

try {
  const id = new URLSearchParams(location.search).get("id");
  const { doc, trails } = await loadData();
  const trail = trails.find((t) => t.recall.recall_id === id);
  if (!trail) {
    showError(`No recall with the id "${id ?? ""}" in the results.`);
  } else {
    renderFacts(trail);
    renderCounts(trail);
    renderNameCheck(trail);
    renderIndia(trail);
    renderListings(trail);
    renderLeftOut(trail);
    document.getElementById("snapshot").textContent = snapshotNote(doc);
  }
} catch (error) {
  console.error(error);
  showError(LOAD_ERROR);
}
