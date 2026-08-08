#!/usr/bin/env python3
"""Verify that an article's paper citations match the extracted paper package.

Checks figure references, section references, numeric data anchors, and
paper metadata (title terms / year / arXiv or DOI link).

Usage:
    python3 verify_paper.py {article}.md --assets output/paper-assets/
    python3 verify_paper.py {article}.md --assets output/paper-assets/ --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FIGURE_REF_RE = re.compile(r"(?:图|Figure|Fig\.)\s*(\d+)")
SECTION_REF_RE = re.compile(r"第\s*(\d+(?:\.\d+)*)\s*节|Section\s+(\d+(?:\.\d+)*)")
NUMBER_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(ms|s|ns|μs|us|GHz|MHz|kHz|Hz|GB/s|MB/s|GB|MB|KB|TB|PB|%|倍|W|V|A)"
)
ARXIV_LINK_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/\d{4}\.\d{4,5}", re.I)
DOI_LINK_RE = re.compile(r"doi\.org/[^\s)]+|doi:\s*10\.\d+", re.I)


def load_paper_text(assets_dir: Path) -> str:
    """Concatenate all extracted chapter texts + abstract for data-anchor search."""
    parts = []
    text_dir = assets_dir / "text"
    if text_dir.is_dir():
        for f in sorted(text_dir.glob("*.txt")):
            parts.append(f.read_text(encoding="utf-8"))
    paper_json = assets_dir / "paper.json"
    if paper_json.exists():
        data = json.loads(paper_json.read_text(encoding="utf-8"))
        if data.get("abstract"):
            parts.append(data["abstract"])
    return "\n".join(parts)


def number_exists(full_text: str, value: float, unit: str, tolerance: float = 0.05) -> bool:
    lo, hi = value * (1 - tolerance), value * (1 + tolerance)
    pattern = re.compile(rf"(\d+(?:\.\d+)?)\s*{re.escape(unit)}\b")
    for m in pattern.finditer(full_text):
        try:
            n = float(m.group(1))
        except ValueError:
            continue
        if lo <= n <= hi:
            return True
    return False


def section_matches(num: str, chapter_title: str) -> bool:
    m = re.match(r"(\d+(?:\.\d+)*)", chapter_title.lower())
    return bool(m) and num == m.group(1)


def verify_paper(article_path: Path, assets_dir: Path) -> dict:
    article_text = article_path.read_text(encoding="utf-8")
    paper_path = assets_dir / "paper.json"
    if not paper_path.exists():
        return {
            "figures": [],
            "sections": [],
            "data_anchors": [],
            "metadata": {"status": "not_found", "issues": ["paper.json missing"]},
        }
    paper = json.loads(paper_path.read_text(encoding="utf-8"))
    full_text = load_paper_text(assets_dir)

    figure_numbers = {f["number"] for f in paper["figures"]}
    chapter_titles = [c["title"].lower() for c in paper["chapters"]]

    figures = []
    for m in FIGURE_REF_RE.finditer(article_text):
        n = int(m.group(1))
        figures.append(
            {"ref": m.group(0), "number": n,
             "status": "verified" if n in figure_numbers else "not_found"}
        )

    sections = []
    chapter_numbers = {str(i + 1) for i in range(len(chapter_titles))}
    for m in SECTION_REF_RE.finditer(article_text):
        num = m.group(1) or m.group(2)
        found = any(section_matches(num, t) for t in chapter_titles) or num in chapter_numbers
        sections.append(
            {"ref": m.group(0), "section": num,
             "status": "verified" if found else "needs_human_check"}
        )

    data_anchors = []
    for m in NUMBER_UNIT_RE.finditer(article_text):
        value, unit = float(m.group(1)), m.group(2)
        data_anchors.append(
            {"value": m.group(0),
             "status": "verified" if number_exists(full_text, value, unit) else "needs_human_check"}
        )
    data_anchors = data_anchors[:20]

    issues = []
    body_no_urls = re.sub(r"https?://\S+", "", article_text)
    latin_words = [
        w for w in re.findall(r"[A-Za-z]{4,}", body_no_urls)
        if w.lower() not in ("arxiv", "doi")
    ]
    title = paper.get("title") or ""
    title_terms = [t for t in re.findall(r"[A-Za-z]{4,}", title) if t.lower() not in ("with", "from", "the")]
    if latin_words and title_terms and not any(t.lower() in article_text.lower() for t in title_terms):
        issues.append("paper title terms not found in article")
    year = paper.get("year")
    if year and str(year) not in article_text:
        issues.append(f"paper year {year} not found in article")
    if not ARXIV_LINK_RE.search(article_text) and not DOI_LINK_RE.search(article_text):
        issues.append("no arXiv/DOI link in article")
    if latin_words and paper.get("authors"):
        surnames = [a.split()[-1].lower() for a in paper["authors"][:3]]
        if not any(s in article_text.lower() for s in surnames):
            issues.append("no author surname found in article")
    metadata = {"status": "verified" if not issues else "not_found", "issues": issues}

    return {
        "figures": figures,
        "sections": sections,
        "data_anchors": data_anchors,
        "metadata": metadata,
    }


def print_report(report: dict) -> int:
    not_found = 0
    print("== Paper citation verification ==")
    for key in ("figures", "sections"):
        for item in report[key]:
            print(f"  {key}: {item['ref']} -> {item['status']}")
            if item["status"] == "not_found":
                not_found += 1
    for item in report["data_anchors"]:
        print(f"  data: {item['value']} -> {item['status']}")
    meta = report["metadata"]
    print(f"  metadata -> {meta['status']}: {'; '.join(meta['issues']) or 'ok'}")
    if meta["status"] == "not_found":
        not_found += 1
    if not_found:
        print(f"FAIL: {not_found} item(s) not verified. Fix before Step 6.")
        return 1
    print("PASS: all paper citations verified.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Verify article citations against a paper package")
    parser.add_argument("path", help="Markdown article path")
    parser.add_argument("--assets", default="output/paper-assets", help="Paper assets dir")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    args = parser.parse_args()

    report = verify_paper(Path(args.path), Path(args.assets))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    sys.exit(print_report(report))


if __name__ == "__main__":
    main()
