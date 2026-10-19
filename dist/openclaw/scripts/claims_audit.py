#!/usr/bin/env python3
"""Cross-check a draft's factual claims against the source ledger.

Extracts the load-bearing claims from an article — numbers with units,
bare decimal measurements, and quoted statements — then checks each one
against the evidence text recorded in ``<article>.sources.yaml``
(excerpt/note fields) and, optionally, against extracted paper text
(``--paper-assets``).

This goes beyond the source ledger itself: the ledger records where
material came from; this script verifies the draft actually stays inside
that evidence. It is advisory by design (exit 0 even with unsupported
claims) because a human decides whether an unsupported claim is a
missing source or a fabrication; ``--strict`` turns it into a gate.

Matching rules
--------------
- Normalize both sides: NFKC, unit aliases (毫秒→ms, 微秒→us, 纳秒→ns,
  秒→s, 千兆赫→GHz, ...), whitespace stripped, lowercased.
- A number claim with a unit is ``supported`` when number+unit appears in
  evidence, ``weak`` when only the number (with boundary) appears, else
  ``unsupported``.
- A bare decimal claim (e.g. FID 4.62) is ``supported`` when the number
  appears with boundaries in evidence, else ``unsupported``.
- A quote is ``supported`` when the full normalized sentence appears in
  evidence, ``weak`` when any 4-character window does, else
  ``unsupported``.

Usage:
    python3 scripts/claims_audit.py output/article.md --json
    python3 scripts/claims_audit.py output/article.md --paper-assets output/paper-assets/ --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

UNITS = [
    "GB/s", "MB/s", "KB/s", "req/s",
    "TFLOPS", "GFLOPS", "TOPS", "FLOPS", "IOPS",
    "Gbps", "Mbps",
    "GHz", "MHz", "kHz", "Hz",
    "ms", "µs", "μs", "us", "ns", "ps",
    "QPS", "qps", "fps", "FPS",
    "KB", "MB", "GB", "TB", "PB",
    "W", "mW", "kW", "mV", "V", "mA", "A",
    "毫秒", "微秒", "纳秒", "秒",
    "%", "％", "倍", "核",
]
_UNITS_ALT = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))

_NUM_UNIT_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNITS_ALT})")
# ASCII-only boundary classes: Unicode \w matches CJK, which would hide
# claims written without spaces around them (the common Chinese case).
_BARE_DECIMAL_RE = re.compile(r"(?<![0-9A-Za-z_./@-])(\d+\.\d+)(?![0-9A-Za-z.])")

_QUOTE_PATTERNS = [
    re.compile(r"「([^」\n]{8,120})」"),
    re.compile(r"“([^”\n]{8,120})”"),
    re.compile(r'"([^"\n]{8,120})"'),
]

_UNIT_ALIASES = [
    ("毫秒", "ms"), ("微秒", "us"), ("纳秒", "ns"), ("千兆赫", "GHz"),
    ("兆赫", "MHz"), ("千赫", "kHz"), ("吉字节", "GB"), ("兆字节", "MB"),
    ("千字节", "KB"), ("百分比", "%"), ("秒", "s"),
]

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_BLOCK_MATH_RE = re.compile(r"\$\$[\s\S]*?\$\$")
_INLINE_MATH_RE = re.compile(r"\$[^$\n]+\$")


def normalize(text: str) -> str:
    """NFKC + unit aliases + whitespace-strip + lowercase."""
    s = unicodedata.normalize("NFKC", text)
    for alias, canonical in _UNIT_ALIASES:
        s = s.replace(alias, canonical)
    return re.sub(r"\s+", "", s).lower()


def _blank(text: str, start: int, end: int) -> None:
    """Blank out text[start:end] in-place (list of chars), keeping newlines."""
    for i in range(start, end):
        if text[i] != "\n":
            text[i] = " "


def _strip_non_prose(text: str) -> str:
    """Replace code fences/inline code/math with spaces (positions kept)."""
    buf = list(text)
    for pattern in (_CODE_FENCE_RE, _BLOCK_MATH_RE, _INLINE_CODE_RE, _INLINE_MATH_RE):
        for m in pattern.finditer(text):
            # Guard: a span may already have been blanked by an outer pattern.
            _blank(buf, m.start(), m.end())
    return "".join(buf)


def extract_claims(text: str) -> list[dict]:
    """Extract number and quote claims with 1-based line numbers."""
    prose = _strip_non_prose(text)
    prose = unicodedata.normalize("NFKC", prose)
    claims: list[dict] = []

    unit_spans: list[tuple[int, int]] = []
    for m in _NUM_UNIT_RE.finditer(prose):
        unit_spans.append((m.start(), m.end()))
        claims.append({
            "type": "number",
            "text": m.group(0),
            "line": prose.count("\n", 0, m.start()) + 1,
        })
    for m in _BARE_DECIMAL_RE.finditer(prose):
        if any(s <= m.start() < e for s, e in unit_spans):
            continue
        claims.append({
            "type": "number",
            "text": m.group(0),
            "line": prose.count("\n", 0, m.start()) + 1,
        })
    for pattern in _QUOTE_PATTERNS:
        for m in pattern.finditer(prose):
            claims.append({
                "type": "quote",
                "text": m.group(1),
                "line": prose.count("\n", 0, m.start()) + 1,
            })
    return claims


def _load_evidence(article: Path, sources_path: Path | None,
                   paper_assets: Path | None) -> list[tuple[str, str]]:
    """Return [(evidence_id, normalized_text), ...]."""
    if sources_path is None:
        sources_path = article.with_suffix(".sources.yaml")
    evidence: list[tuple[str, str]] = []
    if sources_path and Path(sources_path).exists():
        data = yaml.safe_load(Path(sources_path).read_text(encoding="utf-8"))
        if data is None:
            sources: list = []
        elif isinstance(data, dict):
            sources = data.get("sources") or []
            if not isinstance(sources, list):
                raise ValueError(
                    f"malformed sources file {sources_path}: 'sources' must be a list"
                )
        else:
            raise ValueError(
                f"malformed sources file {sources_path}: not a YAML mapping"
            )
        for s in sources:
            if not isinstance(s, dict):
                raise ValueError(
                    f"malformed sources file {sources_path}: entries must be mappings"
                )
            text = f"{s.get('excerpt', '')} {s.get('note', '')}".strip()
            evidence.append((s.get("id", s.get("url", "?")), normalize(text)))
    if paper_assets:
        base = Path(paper_assets)
        chunks = []
        for f in sorted(base.rglob("*.txt")):
            try:
                chunks.append(f.read_text(encoding="utf-8"))
            except OSError:
                continue
        if chunks:
            evidence.append(("paper-assets", normalize(" ".join(chunks))))
    return evidence


def _match_number(claim_text: str, evidence: list[tuple[str, str]]):
    key = normalize(claim_text)
    m = re.match(r"[\d.]+", key)
    number = m.group(0) if m else key
    for eid, text in evidence:
        if key and key in text:
            return "supported", eid
        if re.search(rf"(?<!\d){re.escape(number)}(?!\d)", text):
            return "weak", eid
    return "unsupported", None


def _match_quote(quote: str, evidence: list[tuple[str, str]]):
    key = normalize(quote)
    for eid, text in evidence:
        if len(key) >= 8 and key in text:
            return "supported", eid
        if len(key) >= 4:
            for i in range(len(key) - 3):
                if key[i:i + 4] in text:
                    return "weak", eid
    return "unsupported", None


def audit(article: Path, sources_path: Path | None = None,
          paper_assets: Path | None = None) -> dict:
    text = Path(article).read_text(encoding="utf-8")
    claims = extract_claims(text)
    evidence = _load_evidence(Path(article), sources_path, paper_assets)

    if sources_path is None:
        resolved = Path(article).with_suffix(".sources.yaml")
    else:
        resolved = Path(sources_path)
    ledger_missing = not resolved.exists() and not paper_assets

    for claim in claims:
        if claim["type"] == "number":
            status, eid = _match_number(claim["text"], evidence)
        else:
            status, eid = _match_quote(claim["text"], evidence)
        claim["status"] = status
        claim["evidence"] = eid

    summary = {
        "total": len(claims),
        "supported": sum(1 for c in claims if c["status"] == "supported"),
        "weak": sum(1 for c in claims if c["status"] == "weak"),
        "unsupported": sum(1 for c in claims if c["status"] == "unsupported"),
    }
    return {
        "claims": claims,
        "summary": summary,
        "ledger_missing": ledger_missing,
        "ledger_path": str(resolved),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GzhWrite claims audit")
    ap.add_argument("article")
    ap.add_argument("--sources", default=None,
                    help="sources.yaml (default: <article>.sources.yaml)")
    ap.add_argument("--paper-assets", default=None,
                    help="paper asset dir; text/*.txt becomes evidence")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when any claim is unsupported")
    args = ap.parse_args(argv)

    try:
        report = audit(
            Path(args.article),
            sources_path=Path(args.sources) if args.sources else None,
            paper_assets=Path(args.paper_assets) if args.paper_assets else None,
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"claims_audit error: {exc}", file=sys.stderr)
        return 1

    if report.get("ledger_missing"):
        print(
            f"提示：未找到来源台账 {report['ledger_path']}——所有声明按 unsupported 处理。"
            "先跑 source_ledger.py add 登记素材，再重新核验。",
            file=sys.stderr,
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        marks = {"supported": "OK ", "weak": "WEAK", "unsupported": "MISS"}
        for c in report["claims"]:
            ev = f" <- {c['evidence']}" if c["evidence"] else ""
            print(f"[{marks[c['status']]}] L{c['line']:<4} {c['text']}{ev}")
        s = report["summary"]
        print(f"\ntotal {s['total']} | supported {s['supported']} | "
              f"weak {s['weak']} | unsupported {s['unsupported']}")

    if args.strict and report["summary"]["unsupported"] > 0:
        print(f"claims audit: {report['summary']['unsupported']} unsupported claim(s)",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
