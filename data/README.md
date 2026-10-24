# Data

Optional local data files can be placed here.

The current screening pipeline uses the CSV files in `watchlists/` and `universes/`.

## Confirmed current-screening exclusions

`confirmed_delistings.csv` is a deliberately partial, source-backed registry of
known Japanese delistings, not a complete historical universe. Its required
columns are `symbol,market,delisted_on,name,source`. Dates must be valid
`YYYY-MM-DD` values; missing/malformed registry data stops report generation.

Current screening and rescoring exclude a registered symbol on and after its
delisting date (Japan local date). The filter runs after metadata merging and
before price downloads, scoring, market-relative ranking, or top-N selection.
Watchlists, overlays, and stale index constituent files cannot reintroduce it.
An unregistered symbol remains eligible: absence from a lagging monthly JPX
metadata file is not evidence of delisting.

The initial two events, 6486.T (Eagle Industry) and 7240.T (NOK), were verified on
2026-10-05 against the [JPX delisting list](https://www.jpx.co.jp/listing/stocks/delisted/index.html).
Both delisted on 2026-09-29. The [JPX listing outline](https://www.jpx.co.jp/english/listing/stocks/new/vk0khi0000028oe4-att/10NOKGroup-OutlineEN.pdf)
also documents the separate 641A listing on 2026-10-01. There is no automatic
symbol mapping, price-series splicing, or successor position/return conversion.

Historical tracking records and price requests retain their original symbols.
Forward validation annotates effective confirmed delistings and current-universe
exits; these events alone do not force a last-price sale or infer a settlement.
They do not enable `historicalUniverseCoverage` or change `prospective_only`.

## Optional historical universe

Optional `historical_universe.csv` columns:

```csv
symbol,listed_on,delisted_on,reason
```

Use point-in-time exchange or licensed vendor data. When the file is absent, the validation report labels survivorship coverage as `prospective_only` instead of implying a bias-free historical backtest.
