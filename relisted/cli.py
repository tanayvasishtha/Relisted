"""relisted: command line entry point."""

from __future__ import annotations

import argparse
import sys

from . import store
from .hunt import best_photo, hunt
from .recalls import Recall, fetch, priority
from .serp import BudgetExceeded, NotRecorded, SerpClient, account_status


def ranked(args: argparse.Namespace) -> list[Recall]:
    """Recalls worth a search, most promising first: marketplace, kids, fire, newest."""
    pool = [r for r in fetch(args.since) if priority(r) >= args.min_priority]
    return sorted(pool, key=lambda r: (priority(r), r.date), reverse=True)[: args.limit]


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
    """One Lens search per recall with a listing-style photo, up to --max-credits."""
    client = SerpClient()
    print(f"mode: {client.settings.mode}   credit cap: {client.settings.max_credits}")
    doc = store.load()
    trails = doc.get("trails", {})
    for recall in ranked(args):
        try:
            trail = hunt(recall, client)
        except (BudgetExceeded, NotRecorded) as exc:
            print(f"stopped: {exc}")
            break
        if trail is None:
            continue
        trails[recall.recall_id] = trail.to_dict()
        print(
            f"{recall.recall_id:>6} {recall.product[:40]:40} copies {trail.matches_total:4}  "
            f"selling {len(trail.selling):3}  names {len(trail.aliases):2}  india {len(trail.india)}"
        )
    store.save(trails, client.credits_used)
    print(f"\nsearches paid this run: {client.credits_used}   served from cache: {client.cache_hits}")


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
        p.add_argument("--min-priority", type=int, default=6)
        p.set_defaults(func=fn)

    sub.add_parser("account", help="searches left this month (free)").set_defaults(func=cmd_account)
    serve = sub.add_parser("serve", help="run the website locally with live checks")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
