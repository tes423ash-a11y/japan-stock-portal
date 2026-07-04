# Report Schema

Dashboard input: `reports/latest.json`

Top-level fields:

- `generatedAt`
- `universe`
- `summary`
- `candidates`
- `themes`
- `tracking`

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
