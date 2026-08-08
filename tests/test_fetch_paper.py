"""Tests for fetch_paper.py arXiv search mode (channel B)."""

import requests

from fetch_paper import parse_arxiv_feed, resolve_pdf_url, search_arxiv

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Speculative Decoding with LLMs</title>
    <published>2024-05-01T00:00:00Z</published>
    <summary>We reduce latency by drafting tokens in parallel.</summary>
    <link href="https://arxiv.org/abs/2405.00001" rel="alternate"/>
    <link href="https://arxiv.org/pdf/2405.00001" title="pdf"/>
  </entry>
</feed>"""


def test_resolve_pdf_url():
    assert resolve_pdf_url("https://arxiv.org/abs/2405.00001") == "https://arxiv.org/pdf/2405.00001.pdf"
    assert resolve_pdf_url("https://arxiv.org/pdf/2405.00001") == "https://arxiv.org/pdf/2405.00001.pdf"
    assert resolve_pdf_url("https://example.com/paper.pdf") == "https://example.com/paper.pdf"


def test_parse_arxiv_feed():
    entries = parse_arxiv_feed(FEED)
    assert len(entries) == 1
    assert entries[0]["title"] == "Speculative Decoding with LLMs"
    assert entries[0]["year"] == "2024"
    assert entries[0]["pdf_url"] == "https://arxiv.org/pdf/2405.00001"
    assert "drafting tokens" in entries[0]["summary"]


def test_search_arxiv_uses_api(monkeypatch):
    captured = {}

    class FakeResp:
        text = FEED

        def raise_for_status(self):
            pass

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResp()

    monkeypatch.setattr(requests, "get", fake_get)
    entries = search_arxiv("speculative decoding")
    assert len(entries) == 1
    assert "arxiv.org" in captured["url"]
    assert "speculative decoding" in captured["params"]["search_query"]
