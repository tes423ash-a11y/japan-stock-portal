from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from screener_data import recover_stale_history
from validate_market_freshness import validate_market_freshness


def frame(dates, prices):
    return pd.DataFrame({"Open": prices, "High": prices, "Low": prices,
                         "Close": prices, "Volume": [100] * len(dates)}, index=pd.to_datetime(dates))


def old_history(scale=1):
    return frame(pd.bdate_range(end="2026-09-16", periods=260), [100 * scale] * 260)


def recent(scale=1):
    return frame(["2026-09-16", "2026-09-17"], [100 * scale, 101 * scale])


class FreshnessRecoveryTests(unittest.TestCase):
    def test_market_date_does_not_claim_one_fresh_ticker_represents_everyone(self):
        from screener_report import market_summary
        rows = [{"symbol": str(i), "market": "US", "dataQuality": {"asOf": day, "status": "full"}}
                for i, day in enumerate(["2026-09-16"] * 99 + ["2026-09-17"])]
        with patch("market_sessions.expected_session", return_value="2026-09-17"):
            summary = market_summary(rows, rows, rows[:10])
        self.assertEqual(summary["asOf"], "2026-09-16")
        self.assertEqual(summary["latestAvailableDate"], "2026-09-17")
        self.assertEqual(summary["freshCoveragePct"], 1)

    def recover(self, histories, download, symbols=None, expected=None):
        with patch("screener_data.yf.download", side_effect=download), patch("screener_data.time.sleep"), \
                patch.dict("os.environ", {"YF_FRESHNESS_RETRIES": "3", "YF_FRESHNESS_BACKOFF_SECONDS": "0"}), \
                redirect_stdout(StringIO()):
            return recover_stale_history(
                symbols or list(histories), histories, expected or {"JP": "2026-09-17", "US": "2026-09-17"},
                chunk_size=80, period="18mo", timeout=10, threads=4, pause=0,
            )

    def test_explicit_range_includes_target_and_removes_unfinished_candle(self):
        histories = {"AAPL": old_history()}
        calls = []
        def download(**kwargs):
            calls.append(kwargs)
            return pd.concat({"AAPL": frame(["2026-09-16", "2026-09-17", "2026-09-18"], [100, 101, 102])}, axis=1)
        result = self.recover(histories, download)
        self.assertEqual(calls[0]["end"], "2026-09-18")
        self.assertEqual(calls[0]["start"], "2026-09-07")
        self.assertNotIn("period", calls[0])
        self.assertEqual(len(histories["AAPL"]), 261)
        self.assertEqual(str(histories["AAPL"].index[-1].date()), "2026-09-17")
        self.assertEqual(result["staleRecovered"], 1)

    def test_retries_only_unresolved_and_can_recover_on_third_pass(self):
        histories = {symbol: old_history() for symbol in ("AAPL", "MSFT")}
        calls = []
        def download(tickers, **kwargs):
            calls.append(list(tickers))
            return pd.concat({symbol: recent() if symbol == "AAPL" or len(calls) == 3
                              else old_history() for symbol in tickers}, axis=1)
        result = self.recover(histories, download)
        self.assertEqual(calls, [["AAPL", "MSFT"], ["MSFT"], ["MSFT"]])
        self.assertEqual([row["recovered"] for row in result["freshnessRetries"]], [1, 0, 1])
        self.assertEqual(result["staleUnresolved"], 0)

    def test_exhausted_retries_keep_old_history_and_fail_publication(self):
        previous = old_history()
        histories = {"AAPL": previous.copy()}
        result = self.recover(histories, lambda **kwargs: pd.concat({"AAPL": previous}, axis=1))
        self.assertEqual(len(result["freshnessRetries"]), 3)
        self.assertEqual(result["staleRecovered"], 0)
        self.assertEqual(result["staleUnresolvedSymbols"], ["AAPL"])
        pd.testing.assert_frame_equal(histories["AAPL"], previous)
        with self.assertRaisesRegex(ValueError, "Critical per-market freshness failure"):
            validate_market_freshness({"marketSummary": {"US": {
                "expectedSession": "2026-09-17", "dominantDate": str(histories["AAPL"].index[-1].date()),
                "freshCoveragePct": 0,
            }}}, markets=("US",))

    def test_market_windows_are_independent(self):
        histories = {"7203.T": old_history(), "AAPL": old_history()}
        calls = []
        def download(tickers, **kwargs):
            calls.append((tickers, kwargs["end"]))
            return pd.concat({symbol: frame(["2026-09-16", "2026-09-17", "2026-09-18"], [100, 101, 102]) for symbol in tickers}, axis=1)
        self.recover(histories, download, expected={"JP": "2026-09-18", "US": "2026-09-17"})
        self.assertEqual(calls, [(["7203.T"], "2026-09-19"), (["AAPL"], "2026-09-18")])

    def test_split_requires_full_reload_and_keeps_adjusted_prices_consistent(self):
        histories = {"AAPL": old_history()}
        def download(tickers, **kwargs):
            return old_history(.5) if isinstance(tickers, str) else pd.concat({"AAPL": recent(.5)}, axis=1)
        result = self.recover(histories, download)
        self.assertEqual(result["adjustmentReloads"], 1)
        self.assertEqual(result["staleRecovered"], 1)
        self.assertEqual(histories["AAPL"].Close.iloc[0], 50)
        self.assertEqual(histories["AAPL"].Close.iloc[-1], 50.5)
        self.assertEqual(len(histories["AAPL"]), 261)

    def test_failed_reload_does_not_skip_other_tickers_or_replace_history(self):
        previous = old_history()
        histories = {"BAD": previous.copy(), "GOOD": previous.copy()}
        def download(tickers, **kwargs):
            if isinstance(tickers, str):
                raise RuntimeError("reload failed")
            return pd.concat({symbol: recent(.5 if symbol == "BAD" else 1) for symbol in tickers}, axis=1)
        result = self.recover(histories, download)
        self.assertEqual(result["staleRecovered"], 1)
        self.assertEqual(result["staleUnresolvedSymbols"], ["BAD"])
        self.assertEqual(result["freshnessRetries"][0]["errorCount"], 1)
        pd.testing.assert_frame_equal(histories["BAD"], previous)
        self.assertEqual(str(histories["GOOD"].index[-1].date()), "2026-09-17")

    def test_short_history_cannot_substitute_for_missing_full_download(self):
        histories = {}
        def download(tickers, **kwargs):
            return recent() if isinstance(tickers, str) else pd.concat({"NEW": recent()}, axis=1)
        result = self.recover(histories, download, symbols=["NEW"])
        self.assertNotIn("NEW", histories)
        self.assertEqual(result["staleUnresolved"], 1)

    def test_diagnostics_survive_rejected_report(self):
        import build_report
        rows = [{"symbol": "AAPL", "market": "US", "name": "Apple"},
                {"symbol": "7203.T", "market": "JP", "name": "Toyota"}]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(build_report, "REPORT_DIR", root / "reports"), \
                    patch.object(build_report, "read_input_rows", return_value=(rows, "all_universe")), \
                    patch.object(build_report, "download_history", return_value=(
                        {row["symbol"]: old_history() for row in rows}, {"downloaded": 2, "staleUnresolved": 2})), \
                    patch("market_sessions.expected_session", return_value="2026-09-17"), \
                    patch.dict("os.environ", {"SCREENING_DIAGNOSTICS_DIR": str(root / "diagnostics")}), \
                    redirect_stdout(StringIO()):
                build_report.main()
            report = json.loads((root / "reports/latest.json").read_text())
            with self.assertRaises(ValueError):
                validate_market_freshness(report)
            diagnostic = json.loads((root / "diagnostics/report-freshness.json").read_text())
            self.assertEqual(diagnostic["marketSummary"]["US"]["dominantDate"], "2026-09-16")
            self.assertEqual(diagnostic["providerStatus"]["staleUnresolved"], 2)
            self.assertTrue((root / "diagnostics/provider.json").exists())


if __name__ == "__main__":
    unittest.main()
