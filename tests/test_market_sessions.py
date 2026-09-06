from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from unittest.mock import patch
from market_sessions import expected_session, completed_history, merge_fresh_history, freshness_summary


def frame(dates, prices):
    return pd.DataFrame({'Close': prices, 'Open': prices, 'High': prices, 'Low': prices, 'Volume': [100]*len(dates)}, index=pd.to_datetime(dates))


class SessionTests(unittest.TestCase):
    def test_weekend_and_labor_day(self):
        self.assertEqual(expected_session('US', datetime(2026,9,7,23,tzinfo=timezone.utc)), '2026-09-04')
        self.assertEqual(expected_session('JP', datetime(2026,9,7,7,tzinfo=timezone.utc)), '2026-09-07')
    def test_incomplete_candle_is_removed(self):
        day = expected_session('US', datetime(2026,9,4,18,tzinfo=timezone.utc))
        self.assertEqual(day, '2026-09-03')
        result = completed_history(frame(['2026-09-03','2026-09-04'], [100,101]), day)
        self.assertEqual(len(result), 1)
    def test_early_close_and_dst(self):
        self.assertEqual(expected_session('US', datetime(2026,11,27,18,tzinfo=timezone.utc)), '2026-11-27')
        self.assertEqual(expected_session('US', datetime(2026,11,27,17,tzinfo=timezone.utc)), '2026-11-25')
    def test_unknown_year_fails_closed(self):
        self.assertIsNone(expected_session('JP', datetime(2030,9,4,23,tzinfo=timezone.utc)))
    def test_retry_merges_without_losing_history(self):
        result = merge_fresh_history(frame(['2026-09-02','2026-09-03'],[99,100]), frame(['2026-09-03','2026-09-04'],[100,101]), '2026-09-04')
        self.assertEqual(list(result.Close), [99,100,101])
    def test_adjusted_price_scale_requires_full_reload(self):
        result = merge_fresh_history(frame(['2026-09-02','2026-09-03'],[99,100]), frame(['2026-09-03','2026-09-04'],[50,51]), '2026-09-04')
        self.assertIsNone(result)
    def test_empty_retry_preserves_old_history(self):
        old = frame(['2026-09-03'], [100])
        self.assertTrue(merge_fresh_history(old, pd.DataFrame(), '2026-09-04').equals(old))
    def test_max_date_does_not_hide_majority_lag(self):
        rows = [{'dataQuality':{'asOf':date,'status':'full'}} for date in ['2026-09-03']*99+['2026-09-04']]
        result = freshness_summary(rows, 'US', datetime(2026,9,5,tzinfo=timezone.utc))
        self.assertEqual(result['dominantDate'], '2026-09-03')
        self.assertEqual(result['freshCoveragePct'], 1)

class BulkRetryTests(unittest.TestCase):
    def test_retry_includes_every_stale_symbol_not_only_a_display_subset(self):
        from screener_data import download_history
        symbols = [f"TEST{i}" for i in range(60)]
        calls = []
        def download(tickers, period, **kwargs):
            calls.append((list(tickers), period))
            dates, prices = (["2026-09-02", "2026-09-03"], [99,100]) if period == "18mo" else (["2026-09-03", "2026-09-04"], [100,101])
            return pd.concat({ticker: frame(dates,prices) for ticker in tickers}, axis=1)
        with patch("screener_data.expected_session", return_value="2026-09-04"), patch("screener_data.yf.download", side_effect=download), patch.dict("os.environ", {"YF_CHUNK_PAUSE_SECONDS":"0", "YF_PERIOD":"18mo"}):
            histories, diagnostics = download_history(symbols)
        self.assertEqual(diagnostics["staleRetryRequested"], 60)
        self.assertEqual(diagnostics["staleRecovered"], 60)
        self.assertEqual(len(calls[1][0]), 60)
        self.assertTrue(all(len(f)==3 and f.index[-1].date().isoformat()=="2026-09-04" for f in histories.values()))

if __name__ == '__main__': unittest.main()
