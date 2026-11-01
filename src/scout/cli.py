from __future__ import annotations

import argparse
import logging
import sys

from .config import load_settings

log = logging.getLogger("scout")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="scout", description="A daily research-reading practice.")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("run-daily", help="fetch candidates, rank, write today's picks")
    d.add_argument("--dry-run", action="store_true", help="print picks, write nothing")
    d.add_argument("--no-llm", action="store_true", help="skip LLM calls")
    d.add_argument("--force-want", action="store_true", help="serve a want-queue paper today")
    d.add_argument("--force-essential", action="store_true", help="serve an essential today")

    i = sub.add_parser("ingest-issue", help="turn a GitHub issue (form) into a note / want item")
    i.add_argument("--body-file", required=True, help="path to the issue body (markdown)")
    i.add_argument("--labels", default="", help="comma-separated labels")
    i.add_argument("--title", default="")
    i.add_argument("--dry-run", action="store_true")

    b = sub.add_parser("build-site", help="render the static notebook")
    b.add_argument("--out", default="site_build")

    sub.add_parser("bootstrap", help="print ~20 seed papers for first feedback")
    sub.add_parser("stats", help="print reading stats")

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers", "torch"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = load_settings()

    if args.cmd == "run-daily":
        from .pipeline import run_daily
        return run_daily(settings, dry_run=args.dry_run, no_llm=args.no_llm,
                         force_want=args.force_want, force_essential=args.force_essential)
    if args.cmd == "ingest-issue":
        from .notes.ingest_issue import ingest
        return ingest(settings, body_path=args.body_file, labels=args.labels.split(",") if args.labels else [],
                      title=args.title, dry_run=args.dry_run)
    if args.cmd == "build-site":
        from .site.build import build
        return build(settings, out=args.out)
    if args.cmd == "bootstrap":
        from .pipeline import bootstrap
        return bootstrap(settings)
    if args.cmd == "stats":
        from .notes.stats import print_stats
        return print_stats(settings)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
