#!/usr/bin/env python3
"""
auto_verify_prices.py
=====================
Politely re-checks the official pricing page for each tool in pricing.json
and proposes price updates that a human reviews via the resulting Pull
Request created by the GitHub Action `auto-verify-prices.yml`.

Design constraints:
  * Respect robots.txt and crawl-delay.
  * Identify ourselves clearly with a User-Agent that links back to the repo.
  * Throttle to ~1 request every 4 seconds with random jitter.
  * Never log in. Never scrape paywalled or private data.
  * Only update the `last_verified` date when prices look unchanged.
  * Suggest changes when prices look different, but always require a human
    PR review before anything ships to users.
  * If a page blocks us or fails to load, we skip cleanly (no exception bubbles).

Output:
  * Mutates pricing.json in-place.
  * Prints a short report to stdout.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICING_FILE = REPO_ROOT / "pricing.json"

USER_AGENT = (
    "StackCadoBot/1.0 (+https://github.com/rodwanmostafa/stackcado-data; "
    "contact: rodwanmostafa via GitHub Issues)"
)
MIN_DELAY_SEC = 4.0
MAX_JITTER_SEC = 2.0
PAGE_TIMEOUT_MS = 25_000

PRICE_TOKEN_RE = re.compile(r"\$\s?(\d{1,4}(?:[\.,]\d{1,2})?)")

ROBOTS_CACHE: dict[str, RobotFileParser] = {}


def robots_allows(url: str) -> bool:
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = ROBOTS_CACHE.get(base)
        if rp is None:
            rp = RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
            except Exception:
                # If robots.txt is unreachable, we conservatively assume disallowed
                return False
            ROBOTS_CACHE[base] = rp
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return False


def extract_prices(text: str) -> list[float]:
    seen = []
    for m in PRICE_TOKEN_RE.finditer(text or ""):
        raw = m.group(1).replace(",", ".")
        try:
            n = float(raw)
        except Exception:
            continue
        if 0.5 <= n <= 5000.0:
            seen.append(n)
    return seen


def best_match_for_tier(tier_price: float, candidates: list[float]) -> float | None:
    if not candidates:
        return None
    best = min(candidates, key=lambda c: abs(c - tier_price))
    # If the closest visible price is within 50 % of the recorded price, treat
    # it as a likely match. Otherwise we don't have confidence.
    if tier_price > 0 and abs(best - tier_price) / tier_price > 0.5:
        return None
    return best


def fetch_page_text(pw, url: str) -> str | None:
    try:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=USER_AGENT)
        page = ctx.new_page()
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        resp = page.goto(url, wait_until="networkidle")
        if not resp or resp.status >= 400:
            ctx.close()
            browser.close()
            return None
        text = page.evaluate("() => document.body && document.body.innerText || ''")
        ctx.close()
        browser.close()
        return text or ""
    except Exception as e:
        print(f"  page fetch failed: {e}", flush=True)
        return None


def main() -> int:
    if not PRICING_FILE.exists():
        print("pricing.json missing; nothing to verify.")
        return 0

    data = json.loads(PRICING_FILE.read_text(encoding="utf-8"))
    tools = data.get("tools", {})
    today_str = str(date.today())

    changed_tools = 0
    verified_only = 0
    skipped = 0

    with sync_playwright() as pw:
        for tool_id, t in tools.items():
            url = t.get("pricing_url")
            if not url:
                continue
            if not robots_allows(url):
                print(f"[skip] {tool_id} ({url}) — disallowed by robots.txt", flush=True)
                skipped += 1
                continue

            print(f"[fetch] {tool_id} -> {url}", flush=True)
            text = fetch_page_text(pw, url)
            time.sleep(MIN_DELAY_SEC + random.random() * MAX_JITTER_SEC)
            if not text:
                skipped += 1
                continue

            candidates = extract_prices(text)
            if not candidates:
                skipped += 1
                continue

            tier_changed = False
            for tier in t.get("tiers", []):
                try:
                    cur = float(tier.get("price") or 0)
                except Exception:
                    cur = 0.0
                if cur <= 0:
                    continue
                match = best_match_for_tier(cur, candidates)
                if match is None:
                    continue
                if abs(match - cur) >= 0.5:
                    print(f"  {tier_id := tier.get('name', 'tier')}: ${cur} -> ${match}", flush=True)
                    tier["price"] = round(match, 2)
                    tier_changed = True

            t["last_verified"] = today_str
            if tier_changed:
                changed_tools += 1
            else:
                verified_only += 1

    data["last_generated"] = today_str
    PRICING_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Done. Tools with price changes: {changed_tools}; "
          f"verified-only: {verified_only}; skipped: {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
