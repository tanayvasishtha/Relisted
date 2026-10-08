// Local mode only. Under `relisted serve` this shows a status bar and, on the home page, the recalls
// that have no search yet. On a static host the API does not exist and none of this appears.

import { el, fmtDate, frame, plural } from "./data.js";

async function getJson(path) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

function renderBar(status) {
  const searches =
    status.searches_left == null
      ? ""
      : ` ${plural(status.searches_left, "SerpApi search", "SerpApi searches")} left this month.`;
  const text =
    status.mode === "live"
      ? `Running locally in live mode.${searches}`
      : "Running locally in replay mode: these are saved searches. Put SERPAPI_API_KEY in .env to search live.";
  document
    .getElementById("local-bar")
    .replaceChildren(el("div", { class: "local-bar" }, el("div", { class: "wrap" }, el("p", {}, text))));
}

async function runSearch(button, message, recall) {
  button.disabled = true;
  button.textContent = "Searching Google Lens through SerpApi";
  message.textContent = "";
  try {
    const response = await fetch(`api/search/${encodeURIComponent(recall.recall_id)}`, {
      method: "POST",
      headers: { "X-Relisted": "1" },
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `The search failed (${response.status}).`);
    location.href = body.url;
  } catch (error) {
    button.disabled = false;
    button.textContent = "Search this recall now";
    message.textContent = error.message;
  }
}

function candidateRow(recall, message) {
  const button = el("button", { class: "button", type: "button" }, "Search this recall now");
  button.addEventListener("click", () => runSearch(button, message, recall));
  return el(
    "tr",
    {},
    el("td", { class: "thumb-cell" }, frame(recall.photo, "", "thumb")),
    el(
      "td",
      {},
      el("span", { class: "product-link" }, recall.product),
      recall.sold_on && el("span", { class: "row-sub" }, `Sold on ${recall.sold_on}`),
    ),
    el("td", { class: "secondary" }, fmtDate(recall.date)),
    el("td", {}, button),
  );
}

async function renderCandidates() {
  const section = document.getElementById("live");
  if (!section) return;
  const list = await getJson("api/candidates");
  if (!list || !list.length) return;
  const message = document.getElementById("live-message");
  document.getElementById("candidates").replaceChildren(
    el(
      "div",
      { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Recalls not searched yet" },
      el(
        "table",
        { class: "data" },
        el("caption", { class: "visually-hidden" }, "Recalls not searched yet"),
        el("tbody", {}, ...list.map((recall) => candidateRow(recall, message))),
      ),
    ),
  );
  section.hidden = false;
}

const LOCAL = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
const status = LOCAL ? await getJson("api/status") : null;
if (status) {
  renderBar(status);
  if (status.mode === "live") await renderCandidates();
}
