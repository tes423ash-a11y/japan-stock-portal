# J-Quants Setup

J-Quants credentials are optional.

If credentials are available, Japanese stocks in `watchlists/jp_candidates.csv` are scored with daily quote data.

## GitHub Secrets

Set either:

- `JQUANTS_EMAIL`
- `JQUANTS_PASSWORD`

or:

- `JQUANTS_REFRESH_TOKEN`

Do not commit credentials to repository files.

## Supported MVP indicators

- 50, 150, 200 day moving averages
- 52 week high and low
- 20 and 50 day volume averages
- ATR style volatility
- 20 and 60 day returns
- Simple SEPA/VCP score

## Fallback

Without credentials, the report builder uses CSV-only placeholder scoring so the dashboard still works.
