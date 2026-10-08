// Shared helpers: load the saved results, build DOM safely, format what the pages show.
// Third-party text (listing titles, store names) is only ever added as text, never as HTML.

async function getJson(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${path} answered ${response.status}`);
  return response.json();
}

export async function loadData() {
  const [doc, stats] = await Promise.all([getJson("data/trails.json"), getJson("data/stats.json")]);
  return { doc, stats, trails: Object.values(doc.trails) };
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value === false || value == null) continue;
    if (name === "class") node.className = value;
    else node.setAttribute(name, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function showError(message) {
  const main = document.querySelector("main");
  main.replaceChildren(
    el(
      "div",
      { class: "wrap" },
      el("p", { class: "error", role: "alert" }, message),
      el("p", { class: "actions" }, el("a", { class: "button button-plain", href: "index.html" }, "See all recalls")),
    ),
  );
}

export const LOAD_ERROR =
  "Could not load the results file (data/trails.json). If you are running locally, run relisted sweep first.";

export function safeUrl(url) {
  return /^https?:\/\//i.test(url || "") ? url : "#";
}

const regions = new Intl.DisplayNames(["en"], { type: "region" });

export function countryName(code) {
  if (code === "XX") return "Country not shown";
  try {
    return regions.of(code) || code;
  } catch {
    return code;
  }
}

export function plural(count, word, many = `${word}s`) {
  return `${count.toLocaleString("en")} ${count === 1 ? word : many}`;
}

const asDate = (iso) => new Date(`${iso.slice(0, 10)}T00:00:00`);

export function fmtDate(iso) {
  return asDate(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function monthName(iso) {
  return asDate(iso).toLocaleDateString("en-GB", { month: "long" });
}

export function cleanPrice(price) {
  return price ? price.replace(/\*$/, "") : "";
}

export function realCountries(trail) {
  return trail.countries.filter(([code]) => code !== "XX");
}

export function matchCount(trail) {
  return trail.matches_capped ? `${trail.matches_total}+` : String(trail.matches_total);
}

// A square image on the light wash. If the thumbnail is missing the tile says so.
export function frame(src, alt, className) {
  if (!src) return el("span", { class: `frame frame-empty ${className}` }, "No image");
  return el("span", { class: `frame ${className}` }, el("img", { src, alt, loading: "lazy", width: 240, height: 240 }));
}

export function recallLink(trail) {
  return `recall.html?id=${encodeURIComponent(trail.recall.recall_id)}`;
}

export function snapshotNote(doc) {
  return doc.generated_at ? `Results snapshot: ${fmtDate(doc.generated_at)}.` : "";
}
