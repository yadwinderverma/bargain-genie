# Bargain Hunter

Finds Australian deals on a watchlist and sends the ones worth buying to Slack. A GitHub Action runs it twice a day.

```
OzBargain RSS + Google Shopping (Serper)
        |
        v
Drop deals already alerted or already rejected
        |
        v
Gemini scores each deal against the watchlist
        |
        v
Live page check: price still holds, and the item is in stock
        |
        v
Slack, then the cache is updated
```

OzBargain is the reliable source. Shopping results are a backstop for the same products at trusted Australian retailers.

## Setup

1. Fork the repository.
2. Create a Slack incoming webhook: [api.slack.com/apps](https://api.slack.com/apps), then Incoming Webhooks, then add it to a channel.
3. Add these repository secrets (**Settings, Secrets and variables, Actions**):

| Secret | Where it comes from |
|---|---|
| `SERPER_API_KEY` | [serper.dev](https://serper.dev). Free tier is 2,500 searches a month. |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `SLACK_WEBHOOK_URL` | The webhook from step 2 |

4. Open the Actions tab and enable workflows if GitHub asks.
5. Run **Bargain Hunter** once by hand to confirm the webhook and the keys.

Install and run locally:

```bash
pip install -r requirements.txt
export SERPER_API_KEY="..."
export GEMINI_API_KEY="..."
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
pytest -q
python main.py
```

## What gets sent

Edit `config.py`. Each query is one product: every keyword has to appear, and a model number such as `2` has to sit next to another keyword in the title. Garden tools are separate queries (lawn mower, leaf blower, line trimmer, whipper snipper).

| Setting | Default | Meaning |
|---|---|---|
| `MIN_DISCOUNT_PERCENT` | 40 | Retailer discount required when there is no OzBargain vote signal |
| `MIN_OZBARGAIN_VOTES` | 10 | Upvotes that can surface an on-watchlist OzBargain deal |
| `OZBARGAIN_MIN_VOTES_TRUSTED` | 5 | Upvotes that mark a deal as community validated |
| `LLM_MIN_SCORE` | 6 | Minimum Gemini score (1-10) |
| `MAX_SLACK_ALERTS_PER_RUN` | 10 | Extra deals wait for the next run |
| `OZBARGAIN_FREEBIES_MIN_VOTES` | 20 | Freebies need more votes, and they still have to match the watchlist |
| `VERIFY_PRICES_LIVE` | True | Fetch the product page before sending |

The schedule in `.github/workflows/bargain_hunt.yml` is UTC. 22:00 and 10:00 UTC are 8am and 8pm in Australian Eastern Standard Time. During daylight saving those runs land an hour later.

## How a deal is judged

*   **OzBargain votes** come from the feed (`votes-pos`), not from the description. The merchant link on the feed is what the price check opens. Slack still links to the OzBargain post.
*   **`$0 C&C` and free shipping** are delivery terms. The product price is the amount in front of that clause.
*   **A handset on a monthly plan** is skipped. The `$0` is the phone on a contract.
*   **Gemini** has to call the discount genuine before an OzBargain vote boost is applied. A failed model call is retried on the next run.
*   **The live check** confirms the price closest to the deal. A cheaper accessory on the same page does not replace it. If the retailer blocks the fetch, the deal is still sent. A confirmed higher price, an out-of-stock page, or a non-public URL is dropped.
*   **Officeworks** is flagged as cheapest only when another trusted retailer has a price as well.
*   **The cache** records a deal after Slack accepts it, or after a real rejection. A failed webhook leaves the deal open. A later price at least 5% lower is scored again. Rows from older runs have no status and stay settled for their remaining cache life (`CACHE_MAX_AGE_DAYS`, default 7).

## Layout

```
.github/workflows/bargain_hunt.yml   schedule, tests, then the hunt
config.py                            watchlist and thresholds
main.py                              one run
src/fetchers/ozbargain.py            RSS
src/fetchers/retailers.py            Google Shopping via Serper
src/analyser.py                      Gemini scores
src/price_check.py                   live price and stock check
src/cache.py                         data/deals_cache.json
src/notifier.py                      Slack
src/dedupe.py                        same listing from two sources
```

The workflow commits `data/deals_cache.json` after a successful run. Tests run first, so a broken tree does not send alerts.

Retailer pages and the Shopping API both change. When a source goes quiet, the Action log is the place to look. OzBargain's feed is the one that does not depend on a retailer's HTML.
