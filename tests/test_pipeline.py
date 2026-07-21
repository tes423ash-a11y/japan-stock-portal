from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from screener_data import read_csv_files  # noqa: E402
from build_report import market_limits  # noqa: E402
from screener_report import market_summary, usable_coverage  # noqa: E402
from screener_scoring import rank_candidate, score_vcp, setup_type  # noqa: E402
from shared_feed import compact_candidate, write_shared_feeds  # noqa: E402
from update_all_universes import parse_jp_frame, rows_from_nasdaq  # noqa: E402
from update_topix500_universe import apply_listed_issue_metadata  # noqa: E402
from update_tracking import update_extremes  # noqa: E402


class MetadataMergeTests(unittest.TestCase):
    def test_theme_overlay_does_not_replace_official_sector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            overlay = Path(directory) / "01_overlay.csv"
            official = Path(directory) / "02_official.csv"
            with overlay.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(["symbol", "name", "market", "theme", "note"])
                writer.writerow(["MU", "Micron", "US", "HBM Memory", "priority"])
            with official.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(["symbol", "name", "market", "sector", "industry", "theme", "note"])
                writer.writerow(["MU", "Micron Technology", "US", "Information Technology", "Semiconductors", "Information Technology", "official"])

            row = read_csv_files([overlay, official])[0]
            self.assertEqual(row["theme"], "HBM Memory")
            self.assertEqual(row["sector"], "Information Technology")
            self.assertEqual(row["industry"], "Semiconductors")

    def test_official_name_replaces_numeric_placeholder(self) -> None:
        collected = {
            "6752.T": (["6752.T", "6752", "JP", "Electric Appliances", "", "Electric Appliances", "source"], 1.0)
        }
        metadata = {"6752.T": {"name": "パナソニック ホールディングス", "sector": "電気機器", "industry": "電機・精密"}}
        row = apply_listed_issue_metadata(collected, metadata)["6752.T"][0]
        self.assertEqual(row[1], "パナソニック ホールディングス")
        self.assertEqual(row[3], "電気機器")


class FullUniverseTests(unittest.TestCase):
    def test_jp_parser_keeps_domestic_alphanumeric_stock_codes(self) -> None:
        frame = pd.DataFrame([
            {
                "コード": "285A",
                "銘柄名": "キオクシアホールディングス",
                "市場・商品区分": "プライム（内国株式）",
                "33業種区分": "電気機器",
                "17業種区分": "電機・精密",
            },
            {
                "コード": "1306",
                "銘柄名": "TOPIX連動型上場投資信託",
                "市場・商品区分": "ETF・ETN",
                "33業種区分": "-",
            },
        ])
        rows = parse_jp_frame(frame)
        self.assertEqual([row[0] for row in rows], ["285A.T"])
        self.assertEqual(rows[0][1], "キオクシアホールディングス")

    def test_us_parser_filters_non_common_and_illiquid_securities(self) -> None:
        payload = {"data": {"rows": [
            {"symbol": "GOOD", "name": "Good Systems Common Stock", "lastsale": "$20", "marketCap": "500000000", "volume": "100000", "sector": "Technology", "industry": "Software"},
            {"symbol": "BADW", "name": "Bad Systems Warrants", "lastsale": "$20", "marketCap": "500000000", "volume": "100000", "sector": "Technology", "industry": "Software"},
            {"symbol": "TINY", "name": "Tiny Systems Common Stock", "lastsale": "$2", "marketCap": "50000000", "volume": "100000", "sector": "Technology", "industry": "Software"},
        ]}}
        rows = rows_from_nasdaq(payload)
        self.assertEqual([row[0] for row in rows], ["GOOD"])

    def test_default_market_limits_screen_full_universe_but_publish_500_each(self) -> None:
        names = {
            "SCREENING_TOP_N", "SCREENING_TOP_N_JP", "SCREENING_TOP_N_US",
            "SCREENING_MAX_SYMBOLS", "SCREENING_MAX_SYMBOLS_JP", "SCREENING_MAX_SYMBOLS_US",
        }
        clean_environment = {key: value for key, value in os.environ.items() if key not in names}
        with patch.dict(os.environ, clean_environment, clear=True):
            top_n, maximums = market_limits()
        self.assertEqual(top_n, {"JP": 500, "US": 500})
        self.assertEqual(maximums, {"JP": 5000, "US": 8000})


class SharedFeedTests(unittest.TestCase):
    def candidate(self, symbol: str, score: int) -> dict:
        return {
            "symbol": symbol,
            "code": symbol.replace(".T", ""),
            "name": symbol,
            "market": "JP" if symbol.endswith(".T") else "US",
            "sector": "Technology",
            "industry": "Semiconductors",
            "theme": "AI",
            "score": score,
            "rank": "A",
            "setupType": "vcp_ready",
            "metrics": {"price": 100, "rsRating": 90, "ma50": 95, "ma200": 80},
            "componentScores": {"trend": 25},
            "trendTemplate": {"passed": 8, "total": 8},
            "vcpScore": 20,
            "tradePlan": {"entryLow": 99, "entryHigh": 102, "stop": 94},
            "dataQuality": {"status": "full", "bars": 300, "asOf": "2026-07-21", "staleDays": 0},
        }

    def test_shared_feed_keeps_all_base_rows_and_small_ranked_feed(self) -> None:
        jp = [self.candidate("1111.T", 80), self.candidate("2222.T", 90)]
        us = [self.candidate("AAA", 70), self.candidate("BBB", 95)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_shared_feeds(
                root,
                "2026-07-21T12:00:00+00:00",
                "Technical SEPA/VCP v4",
                {"JP": jp, "US": us},
                {"JP": jp, "US": us},
                {"JP": {"asOf": "2026-07-21"}, "US": {"asOf": "2026-07-20"}},
                1,
            )
            jp_payload = json.loads((root / "shared" / "jp-base.json").read_text(encoding="utf-8"))
            top_payload = json.loads((root / "shared" / "technical-top.json").read_text(encoding="utf-8"))
        self.assertEqual(jp_payload["screenedRows"], 2)
        self.assertEqual([row["symbol"] for row in jp_payload["rows"]], ["1111.T", "2222.T"])
        self.assertEqual([row["symbol"] for row in top_payload["candidates"]], ["2222.T", "BBB"])
        self.assertEqual(manifest["architecture"], "shared-base-metrics-with-strategy-specific-ranking")
        self.assertEqual(compact_candidate(jp[0])["metrics"]["ma50"], 95)


class ScoringTests(unittest.TestCase):
    def healthy_vcp(self) -> dict[str, float | bool]:
        return {
            "price": 100, "ma20": 98, "ma50": 94, "ma200": 80,
            "ma200Slope20dPct": 2, "distanceToPivotPct": -2,
            "volumeDryUp5vs50": 0.65, "latestVolumeRatio20": 0.8,
            "contractionSequence": True, "range15Pct": 6, "tightness10Pct": 5,
            "closeLocation20Pct": 82, "baseDepth60Pct": 24, "atrPct": 3.5,
            "extendedFromMa20Pct": 2,
        }

    def test_deep_base_is_not_vcp_ready(self) -> None:
        healthy = self.healthy_vcp()
        deep = dict(healthy, baseDepth60Pct=52, range15Pct=17)
        self.assertGreater(score_vcp(healthy), score_vcp(deep))
        self.assertEqual(setup_type(healthy, 8, score_vcp(healthy), 90, 50_000_000, "full"), "vcp_ready")
        self.assertNotEqual(setup_type(deep, 8, score_vcp(deep), 90, 50_000_000, "full"), "vcp_ready")

    def test_rank_boundaries_match_published_scale(self) -> None:
        common = ("pullback_ready", 85, 8, 20, 4.0, 50_000_000, "full")
        self.assertEqual(rank_candidate(80, *common), "A")
        self.assertEqual(rank_candidate(79, *common), "B")
        self.assertEqual(rank_candidate(69, *common), "C")
        self.assertEqual(rank_candidate(59, *common), "D")


class ReportingTests(unittest.TestCase):
    def test_top_level_coverage_counts_only_usable_candidates(self) -> None:
        full = {"symbol": "A", "dataQuality": {"status": "full"}}
        missing = {"symbol": "B", "dataQuality": {"status": "missing"}}
        coverage = usable_coverage(2, [full, missing], provider_downloaded=2)
        self.assertEqual(coverage["providerDownloaded"], 2)
        self.assertEqual(coverage["usable"], 1)
        self.assertEqual(coverage["downloaded"], 1)
        self.assertEqual(coverage["missingSymbols"], ["B"])
        self.assertEqual(coverage["coveragePct"], 50.0)

    def test_market_coverage_counts_downloaded_rows(self) -> None:
        universe = [{"symbol": "A"}, {"symbol": "B"}]
        full = {"symbol": "A", "rank": "A", "score": 80, "setupType": "vcp_ready", "dataQuality": {"status": "full", "asOf": "2026-07-10"}}
        missing = {"symbol": "B", "rank": "D", "score": 0, "setupType": "data_issue", "dataQuality": {"status": "missing", "asOf": None}}
        summary = market_summary(universe, [full, missing], [full, missing])
        self.assertEqual(summary["downloadedRows"], 1)
        self.assertEqual(summary["missingRows"], 1)
        self.assertEqual(summary["coveragePct"], 50.0)
        self.assertEqual(summary["asOf"], "2026-07-10")


class TrackingTests(unittest.TestCase):
    def test_extremes_keep_zero_as_starting_point(self) -> None:
        losing = {"maxGainPct": 0.0, "maxDrawdownPct": 0.0}
        update_extremes(losing, -3.2)
        self.assertEqual(losing["maxGainPct"], 0.0)
        self.assertEqual(losing["maxDrawdownPct"], -3.2)

        winning = {"maxGainPct": 0.0, "maxDrawdownPct": 0.0}
        update_extremes(winning, 4.1)
        self.assertEqual(winning["maxGainPct"], 4.1)
        self.assertEqual(winning["maxDrawdownPct"], 0.0)


if __name__ == "__main__":
    unittest.main()
