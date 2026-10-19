#!/usr/bin/env python3
"""Per-article source ledger for the GzhWrite pipeline.

Every factual material gathered in Step 3.2 gets one entry in
``<article>.sources.yaml`` next to the article. The ``excerpt`` field is
the load-bearing one: it records the actual supporting text (quote or
number-with-unit context, ≤200 chars) so that ``claims_audit.py`` can
later check the draft's numeric claims and quotes against real evidence
instead of against a URL string.

Usage:
    python3 scripts/source_ledger.py add --article output/x.md \\
        --url https://example.com/a --title "报道" --date 2026-10-19 \\
        --excerpt "延迟从 12.4 ms 降到 9.8 ms" --verified
    python3 scripts/source_ledger.py list --article output/x.md --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def ledger_path(article: Path) -> Path:
    """``<dir>/<stem>.sources.yaml`` next to the article."""
    article = Path(article)
    return article.with_suffix(".sources.yaml")


def load_sources(article: Path) -> list[dict]:
    path = ledger_path(article)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise ValueError(f"malformed ledger: {path}")
    return data["sources"]


def _save_sources(article: Path, sources: list[dict]) -> None:
    ledger_path(article).write_text(
        yaml.safe_dump({"sources": sources}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def add_source(article: Path, url: str, title: str = "", date: str = "",
               note: str = "", excerpt: str = "", verified: bool = False) -> dict:
    """Add (or update, keyed by URL) one source; return the entry."""
    sources = load_sources(article)
    existing = next((s for s in sources if s.get("url") == url), None)
    if existing is not None:
        if title:
            existing["title"] = title
        if date:
            existing["date"] = date
        if note:
            existing["note"] = note
        if excerpt:
            existing["excerpt"] = excerpt
        if verified:
            existing["verified"] = True
        _save_sources(article, sources)
        return existing

    entry = {
        "id": f"src{len(sources) + 1}",
        "url": url,
        "title": title,
        "date": date,
        "verified": bool(verified),
        "note": note,
        "excerpt": excerpt,
    }
    sources.append(entry)
    _save_sources(article, sources)
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GzhWrite per-article source ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add or update a source (deduped by URL)")
    p_add.add_argument("--article", required=True)
    p_add.add_argument("--url", required=True)
    p_add.add_argument("--title", default="")
    p_add.add_argument("--date", default="")
    p_add.add_argument("--note", default="")
    p_add.add_argument("--excerpt", default="")
    p_add.add_argument("--verified", action="store_true")
    p_add.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="list the ledger")
    p_list.add_argument("--article", required=True)
    p_list.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    article = Path(args.article)

    try:
        if args.cmd == "add":
            entry = add_source(
                article, url=args.url, title=args.title, date=args.date,
                note=args.note, excerpt=args.excerpt, verified=args.verified,
            )
            if args.json:
                print(json.dumps(entry, ensure_ascii=False, indent=2))
            else:
                print(f"{entry['id']}: {entry['url']}")
        elif args.cmd == "list":
            sources = load_sources(article)
            if args.json:
                print(json.dumps(sources, ensure_ascii=False, indent=2))
            else:
                for s in sources:
                    flag = "verified" if s.get("verified") else "unverified"
                    print(f"{s['id']}  [{flag}]  {s.get('title') or s['url']}")
    except (ValueError, OSError) as exc:
        print(f"source_ledger error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
