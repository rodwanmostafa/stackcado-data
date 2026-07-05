# CLAUDE.md — stackcado-data

**PUBLIC repo** — data backend for the StackCado Chrome extension
([stackcado-extension](https://github.com/rodwanmostafa/stackcado-extension), private).
Served to every installed extension via GitHub Pages:
`https://rodwanmostafa.github.io/stackcado-data/`. Committing here IS deploying.

## Files

- `signatures.json` — tech-detection fingerprints (synced from the MIT
  webappanalyzer fork; custom StackCado entries preserved)
- `pricing.json` — per-tier SaaS pricing with `last_verified` + `pricing_url`
- `reviews.json` — tool id → highticketdeals.com review URL + recommended alternative
- `index.html` — GitHub Pages landing page

## Automation (GitHub Actions, no secrets)

| Workflow | Schedule | Does |
|---|---|---|
| `sync-reviews` | daily 05:00 | Pulls new review URLs from the highticketdeals.com sitemap |
| `sync-wappalyzer` | Mon 06:00 | Re-syncs detection signatures from the upstream fork |
| `verify-prices` | Mon 06:30 | Opens an Issue listing pricing entries >30 days stale |
| `auto-verify-prices` | Mon 07:00 | Automated price re-verification |

## Hard rules

- **Never commit secrets — this repo is public by design.** No tokens in
  workflows either (none are needed).
- **Never break the JSON schemas.** Deployed extensions parse these files with a
  1-day cache; changes must be additive/backward-compatible. Coordinate any
  breaking change with an extension release and a transition period.
- Custom StackCado signature entries must survive the weekly wappalyzer sync —
  the sync script preserves them; don't bypass it with manual overwrites.

## Standards

Follow rodwan-os: https://github.com/rodwanmostafa/rodwan-os
