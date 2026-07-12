from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from screener_data import read_csv_files  # noqa: E402
from screener_report import market_summary  # noqa: E402
from screener_scoring import rank_candidate, score_vcp, setup_type  # noqa: E402
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
