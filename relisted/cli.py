"""relisted: command line entry point."""

from __future__ import annotations

import argparse
import sys

from serpapi import SerpApiError

from . import og, publish, recalls, stats, store
from .config import load_settings
from .hunt import best_photo, hunt
from .recalls import MIN_PRIORITY, Recall, fetch
from .serp import BudgetExceeded, NotRecorded, SerpClient, account_status


def ranked(args: argparse.Namespace) -> list[Recall]:
    return recalls.ranked(fetch(args.since), args.min_priority)[: args.limit]


def cmd_candidates(args: argparse.Namespace) -> None:
    """Rank recalls and score their photos. Free: no SerpApi call."""
    rows = []
    for recall in ranked(args):
        photo = best_photo(recall)
        rows.append((photo.border_white if photo else 0.0, recall))
    rows.sort(key=lambda row: -row[0])
    for white, r in rows:
        flag = "listing" if white >= 0.70 else "lab"
        print(
            f"{white:4.2f} {flag:7} {r.recall_id:>6} {r.date}  {r.product[:48]:48} sold on {r.sold_on or '-'}"
        )
    print(f"\n{sum(1 for w, _ in rows if w >= 0.70)} of {len(rows)} have a listing-style photo")


def cmd_sweep(args: argparse.Namespace) -> None:
    """One Lens search per recall with a listing-style photo, up to RELISTED_MAX_CREDITS."""
    client = SerpClient()
    print(f"mode: {client.settings.mode}   credit cap: {client.settings.max_credits}")
    trails = store.load().get("trails", {})
    for recall in ranked(args):
        try:
            trail = hunt(recall, client)
        except (BudgetExceeded, NotRecorded) as exc:
            print(f"stopped: {exc}")
            break
        except (SerpApiError, OSError) as exc:
            print(f"{recall.recall_id:>6} skipped, search failed: {exc}")
            continue
        if trail is None:
            continue
        trails[recall.recall_id] = trail.to_dict()
        store.save(trails, client.credits_used)  # a crash later in the run loses nothing
        print(
            f"{recall.recall_id:>6} {recall.product[:40]:40} copies {trail.matches_total:4}  "
            f"selling {len(trail.selling):3}  india {len(trail.india)}"
        )
    print(f"\nsearches paid this run: {client.credits_used}   served from cache: {client.cache_hits}")


def cmd_thumbs(_: argparse.Namespace) -> None:
    """Make every trail self-contained: local thumbnails, a copy of the raw response, fingerprints. Free."""
    doc = store.load()
    trails = publish.publish_all(doc.get("trails", {}))
    store.save(trails, doc.get("credits_spent_this_run", 0))
    matches = [m for t in trails.values() for m in t["selling"]]
    shown = sum(1 for m in matches if m["thumbnail"])
    print(f"{len(trails)} trails published; {shown} of {len(matches)} listings have a thumbnail")


def cmd_stats(_: argparse.Namespace) -> None:
    """Print the numbers used on the site and in the README, and write site/data/stats.json. Free."""
    numbers = stats.write(store.load().get("trails", {}), load_settings().ledger_path)
    top = numbers.pop("headline")
    for name, value in numbers.items():
        print(f"{name:42} {value}")
    print("headline:", top)


def cmd_og(_: argparse.Namespace) -> None:
    """Draw the social preview image from the saved results. Free."""
    doc = store.load()
    numbers = stats.compute(doc["trails"], load_settings().ledger_path)
    out = og.render(numbers, doc["trails"][numbers["headline"]["recall_id"]], og.SITE / "og.png")
    print(f"wrote {out}")


def cmd_account(_: argparse.Namespace) -> None:
    print(account_status())


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("relisted.server:app", host="127.0.0.1", port=args.port, reload=False)


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="relisted", description="Find recalled products still on sale under new names."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn, help_text in [
        ("candidates", cmd_candidates, "rank recalls and score their photos (free)"),
        ("sweep", cmd_sweep, "search Lens for each candidate and write site/data/trails.json"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--since", default="2026-01-01")
        p.add_argument("--limit", type=int, default=60)
        p.add_argument("--min-priority", type=int, default=MIN_PRIORITY)
        p.set_defaults(func=fn)

    sub.add_parser("thumbs", help="save thumbnails and raw responses for the site (free)").set_defaults(
        func=cmd_thumbs
    )
    sub.add_parser("stats", help="print the numbers for the README and write stats.json (free)").set_defaults(
        func=cmd_stats
    )
    sub.add_parser("og", help="draw the social preview image (free)").set_defaults(func=cmd_og)
    sub.add_parser("account", help="searches left this month (free)").set_defaults(func=cmd_account)
    serve = sub.add_parser("serve", help="run the website locally with live checks")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
