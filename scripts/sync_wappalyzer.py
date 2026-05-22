#!/usr/bin/env python3
"""
sync_wappalyzer.py
==================
Pulls the open-source Wappalyzer technology fingerprints from the maintained
community fork (MIT license) and merges them into StackCado's signatures.json.

Custom StackCado entries (id-prefixed with "sc-" or marked with "_custom": true)
are preserved untouched.

This script is safe to run repeatedly. It is intended to run weekly via GitHub
Actions (.github/workflows/sync-wappalyzer.yml).
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNATURES_FILE = REPO_ROOT / "signatures.json"

# Community-maintained Wappalyzer fork. We use a single combined index file
# rather than per-letter shards to keep the script simple.
WAPPALYZER_INDEX = (
    "https://raw.githubusercontent.com/enthec/webappanalyzer/main/src/technologies/_.json"
)
WAPPALYZER_LETTERS = "abcdefghijklmnopqrstuvwxyz"
WAPPALYZER_LETTER_TPL = (
    "https://raw.githubusercontent.com/enthec/webappanalyzer/main/src/technologies/{letter}.json"
)
WAPPALYZER_CATEGORIES = (
    "https://raw.githubusercontent.com/enthec/webappanalyzer/main/src/categories.json"
)

REQUEST_TIMEOUT = 30


def fetch_json(url: str) -> dict:
    print(f"Fetching {url}", flush=True)
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def load_existing() -> dict:
    if not SIGNATURES_FILE.exists():
        return {
            "schema_version": "1.0.0",
            "last_generated": str(date.today()),
            "_doc": "Auto-merged from Wappalyzer + custom StackCado entries.",
            "tools": {},
        }
    return json.loads(SIGNATURES_FILE.read_text(encoding="utf-8"))


def normalize_pattern(p):
    if isinstance(p, str):
        return p.split(r"\;")[0]
    return None


def normalize_entry(name: str, raw: dict, categories_map: dict) -> dict:
    cats = []
    for cid in raw.get("cats", []):
        c = categories_map.get(str(cid)) or {}
        if c.get("name"):
            cats.append(c["name"])
    category = cats[0] if cats else "Other"

    domains = []
    for w in raw.get("website", []) if isinstance(raw.get("website"), list) else [raw.get("website")]:
        if not w:
            continue
        m = re.search(r"https?://([^/]+)/?", w)
        if m:
            domains.append(m.group(1).lower())

    scripts_src = raw.get("scriptSrc") or raw.get("script") or []
    if isinstance(scripts_src, str):
        scripts_src = [scripts_src]
    scripts = [normalize_pattern(s) for s in scripts_src if normalize_pattern(s)]

    cookies = list((raw.get("cookies") or {}).keys())

    return {
        "name": name,
        "category": category,
        "domains": domains,
        "scripts": scripts,
        "cookies": cookies,
        "_source": "wappalyzer",
    }


def main() -> int:
    existing = load_existing()
    existing_tools = existing.get("tools", {})
    custom_entries = {
        k: v for k, v in existing_tools.items()
        if v.get("_custom") is True or k.startswith("sc-") or v.get("_source") != "wappalyzer"
    }

    categories_map = fetch_json(WAPPALYZER_CATEGORIES)

    merged = {}
    for letter in WAPPALYZER_LETTERS + "_":
        url = WAPPALYZER_LETTER_TPL.format(letter=letter)
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"Skip {url}: {e}", flush=True)
            continue
        for tech_name, raw in data.items():
            slug = slugify(tech_name)
            if not slug or slug in custom_entries:
                continue
            try:
                merged[slug] = normalize_entry(tech_name, raw, categories_map)
            except Exception as e:
                print(f"Skip entry {tech_name}: {e}", flush=True)

    final = dict(custom_entries)
    final.update(merged)

    out = {
        "schema_version": existing.get("schema_version", "1.0.0"),
        "last_generated": str(date.today()),
        "_doc": existing.get(
            "_doc",
            "Auto-merged from Wappalyzer (MIT license) + custom StackCado entries.",
        ),
        "tools": final,
    }

    SIGNATURES_FILE.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(final)} signatures to {SIGNATURES_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
