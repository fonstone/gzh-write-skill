#!/usr/bin/env python3
"""Fetch a research paper and build a paper-assets package for tech articles.

Channel A (user-provided):
    python3 fetch_paper.py <pdf-path-or-url> -o output/paper-assets/
Channel B (arXiv search):
    python3 fetch_paper.py --search "LLM speculative decoding" -o output/paper-assets/
    python3 fetch_paper.py --search "LLM speculative decoding" --pick 2 -o output/paper-assets/
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests

ARXIV_API = "https://export.arxiv.org/api/query"
UA = "Mozilla/5.0 (GzhWrite/1.6; paper fetcher)"
TIMEOUT = 30


def resolve_pdf_url(url: str) -> str:
    """Convert arXiv abs page to a direct PDF URL; other URLs pass through."""
    parsed = urlparse(url)
    if "arxiv.org" in parsed.netloc and ("/abs/" in parsed.path or "/pdf/" in parsed.path):
        pdf = url.replace("/abs/", "/pdf/")
        return pdf + ".pdf" if not pdf.endswith(".pdf") else pdf
    return url


def parse_arxiv_feed(feed_xml: str) -> list[dict]:
    """Parse arXiv Atom feed into [{title, year, summary, pdf_url}]."""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(feed_xml)
    entries = []
    for entry in root.findall("a:entry", ns):
        title = re.sub(r"\s+", " ", entry.findtext("a:title", default="", namespaces=ns)).strip()
        summary = re.sub(r"\s+", " ", entry.findtext("a:summary", default="", namespaces=ns)).strip()
        published = entry.findtext("a:published", default="", namespaces=ns)
        year = published[:4] if published else ""
        pdf_url = ""
        for link in entry.findall("a:link", ns):
            href = link.get("href", "")
            if link.get("title") == "pdf" or "/pdf/" in href:
                pdf_url = href
                break
        if not pdf_url:
            first = entry.find("a:link", ns)
            pdf_url = first.get("href", "") if first is not None else ""
        entries.append(
            {"title": title, "year": year, "summary": summary[:120], "pdf_url": pdf_url}
        )
    return entries


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arXiv API and return candidate list."""
    resp = requests.get(
        ARXIV_API,
        params={"search_query": f'all:"{query}"', "start": 0, "max_results": max_results},
        headers={"User-Agent": UA},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return parse_arxiv_feed(resp.text)


def main():
    parser = argparse.ArgumentParser(description="Fetch a paper and build a paper-assets package")
    parser.add_argument("source", nargs="?", help="PDF path or URL")
    parser.add_argument("--search", help="arXiv search keywords (channel B)")
    parser.add_argument("--pick", type=int, help="Pick candidate N from search results (1-based)")
    parser.add_argument("-o", "--output", default="output/paper-assets", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output)

    if args.search:
        try:
            candidates = search_arxiv(args.search)
        except requests.RequestException as exc:
            print(f"arXiv search failed: {exc}", file=sys.stderr)
            sys.exit(1)
        if not candidates:
            print("No arXiv results found.")
            sys.exit(1)
        for i, c in enumerate(candidates, 1):
            print(f"[{i}] {c['title']} ({c['year']})")
            print(f"    {c['summary']}")
            print(f"    {c['pdf_url']}")
        if args.pick:
            if not 1 <= args.pick <= len(candidates):
                print(f"Pick out of range: {args.pick}", file=sys.stderr)
                sys.exit(1)
            build_package(candidates[args.pick - 1]["pdf_url"], out_dir)
            return
        sys.exit(0)

    if not args.source:
        parser.error("source is required unless --search is given")


if __name__ == "__main__":
    main()
