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
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import fitz  # PyMuPDF
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


CHAPTER_TITLES = {
    "Introduction", "Background", "Related Work", "Method", "Methods",
    "Approach", "Experiments", "Results", "Discussion", "Conclusion",
    "Conclusions", "Evaluation", "Implementation", "Conclusion and Future Work",
}
CHAPTER_TITLES_LOWER = {t.lower() for t in CHAPTER_TITLES}

FIGURE_CAPTION_RE = re.compile(r"^(?:Figure|Fig\.|图)\s*(\d+)[\.:：]?\s*(.+)$")


@dataclass
class Chapter:
    title: str
    page: int


@dataclass
class Figure:
    number: int
    page: int
    caption: str
    file: str = ""
    extract_failed: bool = False


@dataclass
class PaperPackage:
    source: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    arxiv_id: str = ""
    doi: str = ""
    abstract: str = ""
    chapters: list[Chapter] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    text_dir: str = "text"

    def to_json(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "arxiv_id": self.arxiv_id,
            "doi": self.doi,
            "abstract": self.abstract,
            "chapters": [asdict(c) for c in self.chapters],
            "figures": [asdict(f) for f in self.figures],
            "text_dir": self.text_dir,
        }


def download_pdf(url: str, dest: Path) -> Path:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def extract_pdf(doc: fitz.Document, source: str, images_dir: Path) -> PaperPackage:
    meta = doc.metadata or {}
    pkg = PaperPackage(source=source)
    pkg.title = (meta.get("title") or "").strip()
    pkg.authors = [a.strip() for a in re.split(r"[;,]", meta.get("author") or "") if a.strip()]
    m_year = re.search(r"(\d{4})", meta.get("creationDate") or "")
    pkg.year = int(m_year.group(1)) if m_year else None
    if not pkg.title:
        lines = doc[0].get_text().strip().splitlines()
        pkg.title = lines[0].strip() if lines else ""
    if not pkg.authors:
        lines = [l.strip() for l in doc[0].get_text().splitlines() if l.strip()]
        for line in lines[1:]:
            if _is_junk_author_line(line):
                continue
            cand = [a.strip() for a in re.split(r"[;,]", line) if a.strip()]
            if cand:
                pkg.authors = cand
                break
    pkg.abstract = extract_abstract(doc)
    pkg.chapters = extract_chapters(doc)
    pkg.figures = extract_figures(doc, images_dir)
    return pkg


def extract_abstract(doc: fitz.Document) -> str:
    for page in doc[:3]:
        text = page.get_text()
        m = re.search(r"\bAbstract\b\s*(.+)", text, re.S | re.I)
        if not m:
            continue
        body = m.group(1)
        end = re.search(r"\n\s*\d*\.?\s*(1\s+Introduction|[Ii]ntroduction)", body)
        if end:
            body = body[: end.start()]
        return re.sub(r"\s+", " ", body).strip()
    return ""


def extract_chapters(doc: fitz.Document) -> list[Chapter]:
    chapters, seen = [], set()
    for pno in range(len(doc)):
        for line in doc[pno].get_text().splitlines():
            key = line.strip()
            m = re.match(r"^\d+(?:\.\d+)*\.?\s+(.+)$", key)
            if m:
                key = m.group(1)
            key = re.sub(r"[\s.:;:，。；、]+$", "", key)
            key_lower = key.lower()
            if key_lower in CHAPTER_TITLES_LOWER and key_lower not in seen:
                seen.add(key_lower)
                chapters.append(Chapter(title=key, page=pno + 1))
    return chapters


def _is_junk_author_line(line: str) -> bool:
    """True if a page-1 line cannot plausibly be an author list."""
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", line):
        return True
    if re.match(r"^[-–—.\s\d:]+$", line):
        return True
    norm = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", line)
    lower = re.sub(r"[\s.:;:，。；、]+$", "", norm.strip()).lower()
    if lower in CHAPTER_TITLES_LOWER:
        return True
    if re.match(r"^(abstract|figure|fig\.)", lower):
        return True
    if "arxiv" in lower:
        return True
    return False


def extract_figures(doc: fitz.Document, images_dir: Path) -> list[Figure]:
    figures, assigned_xrefs = [], set()
    for pno in range(len(doc)):
        for line in doc[pno].get_text().splitlines():
            m = FIGURE_CAPTION_RE.match(line.strip())
            if not m:
                continue
            num, caption = int(m.group(1)), m.group(2).strip()
            fig = Figure(number=num, page=pno + 1, caption=caption)
            xref = _pick_image_xref(doc, pno, assigned_xrefs)
            if xref is None:
                fig.extract_failed = True
            else:
                assigned_xrefs.add(xref)
                out = images_dir / f"fig{num}.png"
                if _save_image(doc, xref, out):
                    fig.file = f"images/fig{num}.png"
                else:
                    fig.extract_failed = True
            figures.append(fig)
    return figures


def _pick_image_xref(doc: fitz.Document, pno: int, assigned: set[int]) -> int | None:
    for cand_page in (pno, pno + 1):
        if cand_page >= len(doc):
            break
        for img in doc[cand_page].get_images(full=True):
            xref = img[0]
            if xref not in assigned:
                return xref
    return None


def _save_image(doc: fitz.Document, xref: int, out: Path) -> bool:
    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(str(out))
        return True
    except Exception:
        return False


def write_chapter_texts(doc: fitz.Document, chapters: list[Chapter], text_dir: Path) -> None:
    for i, ch in enumerate(chapters):
        start = ch.page - 1
        end = (chapters[i + 1].page - 1) if i + 1 < len(chapters) else len(doc)
        buf = [doc[pno].get_text() for pno in range(start, end)]
        safe = re.sub(r"[^\w\u4e00-\u9fff-]", "_", ch.title)
        (text_dir / f"{i + 1:02d}-{safe}.txt").write_text("".join(buf), encoding="utf-8")


def write_full_text(doc: fitz.Document, text_dir: Path) -> None:
    """Fallback when no chapters were detected: dump the whole document."""
    text = "".join(doc[pno].get_text() for pno in range(len(doc)))
    (text_dir / "01-full.txt").write_text(text, encoding="utf-8")


def build_package(source: str, out_dir: Path) -> PaperPackage:
    images_dir = out_dir / "images"
    text_dir = out_dir / "text"
    images_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        pdf_path = out_dir / "source.pdf"
        download_pdf(resolve_pdf_url(source), pdf_path)
    else:
        pdf_path = Path(source)

    doc = fitz.open(str(pdf_path))
    try:
        pkg = extract_pdf(doc, str(pdf_path), images_dir)
        write_chapter_texts(doc, pkg.chapters, text_dir)
        if not pkg.chapters:
            write_full_text(doc, text_dir)
    finally:
        doc.close()

    (out_dir / "paper.json").write_text(
        json.dumps(pkg.to_json(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pkg


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
        if args.pick is not None:
            if not 1 <= args.pick <= len(candidates):
                print(f"Pick out of range: {args.pick}", file=sys.stderr)
                sys.exit(1)
            build_package(candidates[args.pick - 1]["pdf_url"], out_dir)
            return
        sys.exit(0)

    if not args.source:
        parser.error("source is required unless --search is given")

    pkg = build_package(args.source, out_dir)
    print(f"Paper: {pkg.title} ({pkg.year})")
    print(f"Chapters: {len(pkg.chapters)}, Figures: {len(pkg.figures)}")
    print(f"Package at: {out_dir}")


if __name__ == "__main__":
    main()
