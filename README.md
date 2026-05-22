# stackcado-data

Public, version-controlled data files for the **StackCado** Chrome extension.

## What lives here

| File | Purpose | How it updates |
| --- | --- | --- |
| `signatures.json` | Detection fingerprints (CMS, frameworks, hosting, CRM, analytics, payments, etc.). | Auto-synced weekly from the open-source [Wappalyzer fork](https://github.com/enthec/webappanalyzer) (MIT). Custom StackCado entries are preserved. |
| `pricing.json` | Verified per-tier pricing for tracked SaaS tools, with `last_verified` date and a `pricing_url` source link. | Manually verified. A weekly GitHub Action opens an Issue listing any entry older than 30 days. |
| `reviews.json` | Mapping from tool id → in-depth review URL on [HighTicketDeals.com](https://highticketdeals.com), plus a recommended alternative. | Manually edited when you publish a new review. |
| `index.html` | Tiny landing page for the GitHub Pages site. | n/a |

## Public URL (after enabling GitHub Pages)

```
https://rodwanmostafa.github.io/stackcado-data/signatures.json
https://rodwanmostafa.github.io/stackcado-data/pricing.json
https://rodwanmostafa.github.io/stackcado-data/reviews.json
```

The Chrome extension fetches these with a 24-hour local cache, so even if the
repo is briefly unreachable the extension keeps working.

## Setup (5 minutes)

1. Create a new public GitHub repo named `stackcado-data` under your
   `rodwanmostafa` account.
2. Push the files in this folder to that repo.
3. In GitHub: **Settings → Pages → Source = "Deploy from branch" → Branch = `main` / `(root)`**.
4. Wait ~1 minute and confirm `https://rodwanmostafa.github.io/stackcado-data/`
   loads the landing page.
5. Done. The two GitHub Actions will start running on their weekly schedule.

## How to update prices (10 min/week)

1. Open the GitHub Issue titled "Weekly price verification".
2. For each tool listed: click the `pricing_url`, confirm or update the price,
   bump `last_verified` to today's date in `pricing.json`.
3. Commit. The change is live in your extension within 24 h (or instantly for
   any user who clicks the StackCado refresh button).

## How to add a new review

1. Publish your in-depth review on `https://highticketdeals.com/reviews/<slug>/`.
2. Open `reviews.json`, find the tool id (e.g. `mailchimp`).
3. Set `has_review: true`, `review_url: "https://highticketdeals.com/reviews/<slug>/"`.
4. Commit. Live in &le; 24 hours.

## License

MIT for StackCado-authored content. Wappalyzer signatures retain their MIT
license from the upstream project.
