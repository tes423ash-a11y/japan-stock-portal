# Data

Optional local data files can be placed here.

The current screening pipeline uses the CSV files in `watchlists/` and `universes/`.

Optional `historical_universe.csv` columns:

```csv
symbol,listed_on,delisted_on,reason
```

Use point-in-time exchange or licensed vendor data. When the file is absent, the validation report labels survivorship coverage as `prospective_only` instead of implying a bias-free historical backtest.
