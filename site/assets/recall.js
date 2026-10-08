import {
  LOAD_ERROR,
  cleanPrice,
  countryName,
  el,
  fmtDate,
  frame,
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
        "This search",
        "One Google Lens search through SerpApi. ",
        trail.raw_json && el("a", { href: trail.raw_json }, "Read the raw result"),
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
    ? `${plural(listings, "store listing")} in ${plural(countries, "country", "countries")}`
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
    el("td", { class: "thumb-cell" }, frame(m.thumbnail, "", "thumb")),
    el(
      "td",
      {},
      el("a", { class: "listing-title", href: safeUrl(m.link), ...external }, m.title || m.link),
      el("span", { class: "row-sub" }, m.source),
    ),
    el("td", { class: "num" }, cleanPrice(m.price)),
  );
}

function listingTable(matches, label) {
  return el(
    "div",
    { class: "table-wrap", tabindex: "0", role: "region", "aria-label": label },
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
        "Lens found no store listing for this photo in this search. That does not mean the product is gone: " +
          "Lens only finds pages that carry this one photo.",
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
    [k.spam, "copies of the listing on unrelated sites"],
    [k.news, "news stories"],
    [k.social, "social posts"],
    [k.store_page, "store category pages"],
    [k.other, "other pages that are not listings"],
  ]
    .filter(([count]) => count)
    .map(([count, what]) => `${count.toLocaleString("en")} ${what}`);
  const holder = document.getElementById("left-out");
  if (!parts.length) return holder.replaceChildren();
  holder.replaceChildren(
    el("h3", { class: "subtitle" }, "What we left out"),
    el(
      "p",
      { class: "note" },
      `Of the ${matchCount(trail)} pages Lens matched, these are not counted as store listings: ${parts.join(", ")}. ` +
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
    renderIndia(trail);
    renderListings(trail);
    renderLeftOut(trail);
    document.getElementById("snapshot").textContent = snapshotNote(doc);
  }
} catch (error) {
  console.error(error);
  showError(LOAD_ERROR);
}
