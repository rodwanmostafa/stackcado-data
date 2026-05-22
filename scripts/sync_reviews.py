#!/usr/bin/env python3
"""
sync_reviews.py
===============
Crawls the WordPress sitemap of HighTicketDeals.com (or any blog), finds
new review/compare posts, and merges them into reviews.json.

The script is conservative by design:
  - Only ADDS new entries. It NEVER overwrites existing reviews, summaries,
    or alternatives. You stay in control of curation.
  - Tool id is inferred from the URL slug. If a slug already maps to a known
    signature id in signatures.json, the entry is linked correctly.
  - Tool id collisions are skipped to avoid clobbering existing entries.

Environment variables:
  BLOG_BASE_URL       e.g. https://highticketdeals.com
  BLOG_SITEMAP_URLS   comma-separated list of candidate sitemap URLs

Output: writes back to /reviews.json at repo root.
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEWS_FILE = REPO_ROOT / "reviews.json"
SIGNATURES_FILE = REPO_ROOT / "signatures.json"

BLOG_BASE_URL = os.environ.get("BLOG_BASE_URL", "https://highticketdeals.com").rstrip("/")
SITEMAP_CANDIDATES = [
    u.strip() for u in os.environ.get(
        "BLOG_SITEMAP_URLS",
        f"{BLOG_BASE_URL}/sitemap.xml,{BLOG_BASE_URL}/sitemap_index.xml,{BLOG_BASE_URL}/post-sitemap.xml",
    ).split(",") if u.strip()
]

REVIEW_PATH_PATTERNS = (
    re.compile(r"^/reviews/(?P<slug>[^/?#]+)/?$"),
    re.compile(r"^/compare/(?P<slug>[^/?#]+)/?$"),
    re.compile(r"^/review/(?P<slug>[^/?#]+)/?$"),
)

REQUEST_TIMEOUT = 20
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": "StackCadoBot/1.0 (+https://github.com/rodwanmostafa/stackcado-data)"
        })
        if r.status_code == 200 and r.text.strip():
            return r.text
    except Exception as e:
        print(f"fetch failed for {url}: {e}", flush=True)
    return None


def parse_sitemap(xml_text: str) -> list[str]:
    """Return a list of all <loc> URLs from a sitemap or sitemap index."""
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"sitemap parse error: {e}", flush=True)
        return urls

    tag = root.tag.lower()
    if tag.endswith("sitemapindex"):
        for sm in root.findall("sm:sitemap", NS):
            loc = sm.find("sm:loc", NS)
            if loc is not None and loc.text:
                child_xml = fetch(loc.text.strip())
                if child_xml:
                    urls.extend(parse_sitemap(child_xml))
    elif tag.endswith("urlset"):
        for u in root.findall("sm:url", NS):
            loc = u.find("sm:loc", NS)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
    return urls


def collect_blog_urls() -> list[str]:
    seen = set()
    all_urls: list[str] = []
    for sm_url in SITEMAP_CANDIDATES:
        xml_text = fetch(sm_url)
        if not xml_text:
            continue
        for u in parse_sitemap(xml_text):
            if u in seen:
                continue
            seen.add(u)
            all_urls.append(u)
    return all_urls


def slug_from_url(url: str) -> tuple[str | None, str]:
    """Returns (kind, slug) where kind is 'review' or 'compare' or None."""
    try:
        path = urlparse(url).path
    except Exception:
        return None, ""
    for pat in REVIEW_PATH_PATTERNS:
        m = pat.match(path)
        if m:
            kind = "compare" if "/compare/" in path else "review"
            return kind, m.group("slug").lower()
    return None, ""


def load_json(p: Path, default: dict) -> dict:
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> int:
    reviews = load_json(REVIEWS_FILE, {
        "schema_version": "1.0.0",
        "last_generated": str(date.today()),
        "blog_base_url": BLOG_BASE_URL,
        "tools": {},
    })
    signatures = load_json(SIGNATURES_FILE, {"tools": {}})

    known_review_urls = {
        (v.get("review_url") or "").rstrip("/")
        for v in (reviews.get("tools") or {}).values()
        if v.get("review_url")
    }
    sig_ids = set((signatures.get("tools") or {}).keys())

    urls = collect_blog_urls()
    print(f"Found {len(urls)} URLs in sitemap(s).", flush=True)

    added = 0
    tools = reviews.setdefault("tools", {})

    for url in urls:
        kind, slug = slug_from_url(url)
        if not slug:
            continue
        url_norm = url.rstrip("/")
        if url_norm in known_review_urls:
            continue

        # The slug for a comparison post like "mailchimp-vs-convertkit" should
        # link to the *primary* tool id ("mailchimp"). For pure review posts
        # the slug is typically the tool id directly.
        if kind == "compare":
            primary = slug.split("-vs-")[0]
        else:
            primary = slug

        # Prefer a known signature id if it matches exactly.
        tool_id = primary if primary in sig_ids else primary

        if tool_id in tools:
            # Do not overwrite; only fill missing fields.
            entry = tools[tool_id]
            if not entry.get("review_url"):
                entry["review_url"] = url_norm + "/"
                entry["has_review"] = True
                added += 1
                print(f"linked existing tool '{tool_id}' to {url_norm}/", flush=True)
            continue

        tools[tool_id] = {
            "name": primary.replace("-", " ").title(),
            "has_review": True,
            "review_url": url_norm + "/",
            "summary": "",
            "alternative": None,
            "_auto_added": True,
            "_added_on": str(date.today()),
        }
        added += 1
        print(f"added new tool '{tool_id}' from {url_norm}/", flush=True)

    reviews["last_generated"] = str(date.today())
    REVIEWS_FILE.write_text(
        json.dumps(reviews, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {REVIEWS_FILE} (added {added} new entries).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
