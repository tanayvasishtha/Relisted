import { loadData, plural, snapshotNote } from "./data.js";

try {
  const { doc, stats } = await loadData();
  document.getElementById("usage").textContent =
    `The results on this site come from ${plural(stats.recalls_checked, "Lens search", "Lens searches")}. ` +
    `With the test searches before them, ${stats.searches_paid_total} SerpApi searches were paid for in total.`;
  document.getElementById("snapshot").textContent = snapshotNote(doc);
} catch (error) {
  console.error(error); // the method text stands without the numbers
}
