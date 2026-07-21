# Report Schema

Dashboard input: `reports/latest.json`

Top-level fields:

- `generatedAt`
- `universe`
- `summary`
- `candidates`
- `themes`
- `tracking`
- `sharedScreening`

Candidate fields used by the dashboard:

- `symbol`
- `code`
- `name`
- `market`
- `theme`
- `rank`
- `score`
- `setup`
- `price`
- `pivot`
- `stop`
- `target1`
- `target2`
- `rr`
- `riskLabel`
- `action`
- `reasons`

Keep this schema stable when adding real data providers.

Shared base feeds:

- `reports/shared/manifest.json`
- `reports/shared/jp-base.json`
- `reports/shared/us-base.json`
- `reports/shared/technical-top.json`

The base feeds contain one compact row for every screened symbol. Price-history download and base-indicator calculation are shared; each consumer may apply a different final strategy ranking without downloading the same market data again.
