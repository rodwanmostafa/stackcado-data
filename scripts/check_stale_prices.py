#!/usr/bin/env python3
"""
check_stale_prices.py
=====================
Reads pricing.json and prints a Markdown report listing every tool whose
`last_verified` date is older than STALE_DAYS days. Used by the weekly
GitHub Action `verify-prices.yml` to upsert a single tracking Issue.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICING_FILE = REPO_ROOT / "pricing.json"
STALE_DAYS = 30


def main() -> int:
    data = json.loads(PRICING_FILE.read_text(encoding="utf-8"))
    tools = data.get("tools", {})
    today = date.today()
    cutoff = today - timedelta(days=STALE_DAYS)

    stale = []
    for tool_id, t in tools.items():
        try:
            lv = datetime.strptime(t.get("last_verified", "1970-01-01"), "%Y-%m-%d").date()
        except Exception:
            lv = date(1970, 1, 1)
        if lv < cutoff:
            stale.append((tool_id, t, lv))

    print(f"# Weekly price verification — {today.isoformat()}")
    print()
    print(f"Tools with prices older than **{STALE_DAYS} days**: **{len(stale)}** of {len(tools)}")
    print()
    print("To update: open `pricing.json` on GitHub, edit the `last_verified` date and any prices that changed, commit. The change goes live in ~30 seconds.")
    print()
    if not stale:
        print("All prices are fresh. No action needed this week.")
        return 0

    print("| Tool | Category | Last verified | Days old | Pricing page |")
    print("| --- | --- | --- | ---: | --- |")
    for tool_id, t, lv in sorted(stale, key=lambda x: x[2]):
        days = (today - lv).days
        print(f"| **{t.get('name', tool_id)}** (`{tool_id}`) | {t.get('category', '')} | {lv.isoformat()} | {days} | [open]({t.get('pricing_url', '#')}) |")

    print()
    print("_Generated automatically by `scripts/check_stale_prices.py`._")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
