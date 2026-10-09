from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_report
import build_validation_report as validation
import rescore_existing_report as rescore
import screener_data
import universe_eligibility as eligibility
import update_tracking


HEADER = 'symbol,name,market,sector,industry,theme,note\n'
ROWS = (
    '7240.T,7240,JP,輸送用機器,,AI,old index\n'
    '6486.T,イーグル工業,JP,機械,,機械,old snapshot\n'
    '641A.T,NOK Group,JP,輸送用機器,,AI,new listing\n'
    '999A.T,New listing,JP,電気機器,,AI,not in monthly metadata\n'
    'MU,Micron,US,Information Technology,Semiconductors,HBM Memory,priority\n'
)


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'universes').mkdir()
        self.universe = self.root / 'universes' / 'jp_topix500.csv'
        self.universe.write_text(HEADER + ROWS, encoding='utf-8')
        self.rows = screener_data.read_csv_files([self.universe])
        clock = patch('universe_eligibility.datetime')
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.clock.now.return_value = datetime(2026, 10, 6, tzinfo=ZoneInfo('Asia/Tokyo'))

    def test_before_on_and_after_delisting(self):
        for as_of, excluded in [('2026-09-28', set()), ('2026-09-29', {'7240.T', '6486.T'}), ('2026-10-05', {'7240.T', '6486.T'})]:
            with self.subTest(as_of=as_of):
                original = copy.deepcopy(self.rows)
                filtered = eligibility.filter_current_rows(self.rows, as_of)
                self.assertEqual(filtered, [row for row in original if row['symbol'] not in excluded])
                self.assertEqual(self.rows, original)
                self.assertTrue(all(row is next(item for item in self.rows if item['symbol'] == row['symbol']) for row in filtered))

    def test_date_inputs_are_strict_and_default_is_japan_local(self):
        self.assertEqual(eligibility.eligibility_date(), date(2026, 10, 6))
        self.clock.now.assert_called_with(ZoneInfo('Asia/Tokyo'))
        self.assertEqual(eligibility.eligibility_date(date(2026, 9, 29)), date(2026, 9, 29))
        for bad in ['', 'unknown', '2026-9-29', '20260929', '2026-02-30', '2026-09-29T00:00:00Z', datetime(2026, 9, 29), 20260929]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                eligibility.filter_current_rows(self.rows, bad)

    def test_missing_or_invalid_registry_fails_closed(self):
        registry = self.root / 'confirmed_delistings.csv'
        with patch.object(eligibility, 'CONFIRMED_DELISTINGS', registry):
            with self.assertRaises(FileNotFoundError):
                eligibility.filter_current_rows(self.rows)
            for invalid in [
                'symbol,market,delisted_on,name,source\n',
                'symbol,delisted_on\n7240.T,2026-09-29\n',
                'symbol,market,delisted_on,name,source\n7240.T,JP,,NOK,https://www.jpx.co.jp/listing/stocks/delisted/index.html\n',
                'symbol,market,delisted_on,name,source\n7240.T,JP,2026-02-30,NOK,https://www.jpx.co.jp/listing/stocks/delisted/index.html\n',
                'symbol,market,delisted_on,name,source\n7240.T,JP,2026-09-29,NOK,\n',
                'symbol,market,delisted_on,name,source\nMU,US,2026-09-29,Micron,https://www.jpx.co.jp/listing/stocks/delisted/index.html\n',
            ]:
                with self.subTest(invalid=invalid):
                    registry.write_text(invalid, encoding='utf-8')
                    with self.assertRaises(ValueError):
                        eligibility.filter_current_rows(self.rows)

    def test_all_screening_modes_filter_after_merging_and_keep_overlays(self):
        official = self.root / 'universes' / 'jp_tse_all.csv'
        official.write_text(HEADER + '641A.T,NOK Group,JP,輸送用機器,自動車・輸送機,輸送用機器,official\n', encoding='utf-8')
        inputs = [self.universe, official]
        original_files = [path.read_bytes() for path in inputs]
        for mode in ['all_universe', 'top_turnover', 'top_turnover_today', 'watchlists']:
            with self.subTest(mode=mode), patch.dict(os.environ, {'SCREENING_MODE': mode}), patch.object(screener_data, 'UNIVERSE_FILES', inputs), patch.object(screener_data, 'WATCHLISTS', inputs):
                rows, returned_mode = screener_data.read_input_rows('2026-09-29')
                self.assertEqual(returned_mode, mode)
                self.assertEqual([row['symbol'] for row in rows], ['641A.T', '999A.T', 'MU'])
                self.assertEqual(rows[0]['theme'], 'AI')
                self.assertEqual(rows[0]['industry'], '自動車・輸送機')
                self.assertEqual(rows[-1], self.rows[-1])
        self.assertEqual([path.read_bytes() for path in inputs], original_files)
        # Raw reads remain available to historical/metadata consumers.
        self.assertIn('7240.T', {row['symbol'] for row in screener_data.read_csv_files(inputs)})

    def test_filtered_empty_universe_does_not_fall_back_to_watchlist(self):
        self.universe.write_text(HEADER + '7240.T,NOK,JP,,,,\n', encoding='utf-8')
        watchlist = self.root / 'watchlist.csv'
        watchlist.write_text(HEADER + ROWS, encoding='utf-8')
        with patch.dict(os.environ, {'SCREENING_MODE': 'all_universe'}), patch.object(screener_data, 'UNIVERSE_FILES', [self.universe]), patch.object(screener_data, 'WATCHLISTS', [watchlist]):
            self.assertEqual(screener_data.read_input_rows('2026-09-29'), ([], 'all_universe'))

    def test_validation_membership_uses_same_effective_filter(self):
        with patch.object(validation, 'ROOT', self.root):
            self.assertEqual(validation.current_universe_symbols('2026-09-28'), {'7240.T', '6486.T', '641A.T', '999A.T', 'MU'})
            self.assertEqual(validation.current_universe_symbols('2026-09-29'), {'641A.T', '999A.T', 'MU'})

    def test_report_build_filters_before_download_scoring_and_shared_ranking(self):
        reports = self.root / 'reports'
        frame = pd.DataFrame({
            'Open': np.linspace(100, 199, 300), 'High': np.linspace(102, 201, 300),
            'Low': np.linspace(98, 197, 300), 'Close': np.linspace(100, 199, 300),
            'Volume': np.full(300, 1000000),
        }, index=pd.bdate_range(end='2026-10-05', periods=300))
        requested = []
        def download(symbols):
            requested.extend(symbols)
            return {symbol: frame.copy() for symbol in symbols}, {'downloaded': len(symbols), 'requested': len(symbols)}
        with patch.dict(os.environ, {'SCREENING_MODE': 'all_universe', 'SCREENING_DIAGNOSTICS_DIR': str(self.root / 'diagnostics')}), patch.object(screener_data, 'UNIVERSE_FILES', [self.universe]), patch.object(build_report, 'REPORT_DIR', reports), patch.object(build_report, 'download_history', side_effect=download), patch.object(build_report, 'build_raw_candidate', wraps=build_report.build_raw_candidate) as build, redirect_stdout(io.StringIO()):
            build_report.main()
        self.assertEqual(requested, ['641A.T', '999A.T', 'MU'])
        self.assertEqual([call.args[0]['symbol'] for call in build.call_args_list], requested)
        result = json.loads((reports / 'latest.json').read_text())
        self.assertEqual(result['inputRowsByMarket'], {'JP': 2, 'US': 1})
        self.assertEqual({row['symbol'] for row in result['candidates']}, set(requested))
        base = json.loads((reports / 'shared' / 'jp-base.json').read_text())
        self.assertEqual({row['symbol'] for row in base['rows']}, {'641A.T', '999A.T'})
        top = json.loads((reports / 'shared' / 'technical-top.json').read_text())
        self.assertEqual({row['symbol'] for row in top['candidates']}, set(requested))

    def test_validation_retains_original_records_histories_and_returns(self):
        records = [dict(id=f'{symbol}|2026-09-24', symbol=symbol, name=symbol, market='JP', detectedAt='2026-09-24', detectedSetupType='vcp_ready', initialStop=90, plannedEntryPrice=100) for symbol in ['7240.T', '6486.T']]
        tracking = self.root / 'tracking.json'
        tracking.write_text(json.dumps({'records': records}), encoding='utf-8')
        before_tracking = tracking.read_bytes()
        # A confirmed exit must remain visible even when no active members remain.
        self.universe.write_text(HEADER + ''.join(ROWS.splitlines(keepends=True)[:2]), encoding='utf-8')
        frame = pd.DataFrame({'Open': [100, 101], 'High': [102, 103], 'Low': [99, 100], 'Close': [101, 102]}, index=pd.to_datetime(['2026-09-25', '2026-09-28']))
        original_frame = frame.copy(deep=True)
        for as_of, event in [('2026-09-28', None), ('2026-09-29', 'delisted'), ('2026-10-05', 'delisted')]:
            self.clock.now.return_value = datetime.fromisoformat(as_of).replace(tzinfo=ZoneInfo('Asia/Tokyo'))
            output = self.root / 'validation.json'
            with self.subTest(as_of=as_of), patch.dict(os.environ, {'VALIDATION_OFFLINE': 'false'}), patch.object(validation, 'ROOT', self.root), patch.object(validation, 'TRACKING', tracking), patch.object(validation, 'OUTPUT', output), patch.object(validation, 'HISTORICAL_UNIVERSE', self.root / 'absent.csv'), patch.object(validation, 'download_history', return_value=({'7240.T': frame, '6486.T': frame}, {'downloaded': 2})) as download, patch.object(validation, 'simulate_long_trade', wraps=validation.simulate_long_trade) as simulate, redirect_stdout(io.StringIO()):
                validation.main()
                payload = json.loads(output.read_text())
                download.assert_called_once_with(['6486.T', '7240.T'])
                self.assertTrue(all(call.kwargs['terminal_event'] is None for call in simulate.call_args_list))
                self.assertEqual({trade['symbol'] for trade in payload['trades']}, {'7240.T', '6486.T'})
                self.assertFalse(payload['quality']['historicalUniverseCoverage'])
                self.assertEqual(payload['quality']['survivorshipStatus'], 'prospective_only')
                self.assertEqual(payload['quality']['confirmedDelistingEvents'], 2 if event else 0)
                for trade in payload['trades']:
                    self.assertEqual(trade['terminalEvent'], event)
                    self.assertEqual(trade['universeExited'], bool(event))
                    self.assertEqual(trade['status'], 'open')
                    self.assertFalse(trade['closed'])
                    baseline = validation.simulate_long_trade(frame, '2026-09-24', 90, 120)
                    for key in ['entryPrice', 'exitPrice', 'exitReason', 'netReturnPct', 'rMultiple']:
                        self.assertEqual(trade[key], baseline[key])
        self.assertEqual(tracking.read_bytes(), before_tracking)
        pd.testing.assert_frame_equal(frame, original_frame)

    def test_rescore_and_tracking_preserve_historical_record_and_prices(self):
        latest = self.root / 'latest.json'
        record = {'id': '7240.T|2026-09-24', 'symbol': '7240.T', 'detectedAt': '2026-09-24', 'entryPrice': 100, 'currentPrice': 102, 'currentGainPct': 2, 'maxGainPct': 2, 'maxDrawdownPct': 0, 'initialStop': 90, 'detectedSetupType': 'vcp_ready'}
        candidates = [dict(row, score=0, rank='D', setupType='data_issue', metrics={}, dataQuality={'status': 'missing'}) for row in self.rows]
        latest.write_text(json.dumps({'generatedAt': '2026-10-05T21:00:00Z', 'candidates': candidates, 'tracking': [record]}), encoding='utf-8')
        with patch.dict(os.environ, {'SCREENING_MODE': 'all_universe'}), patch.object(screener_data, 'UNIVERSE_FILES', [self.universe]), patch.object(rescore, 'LATEST', latest), redirect_stdout(io.StringIO()):
            rescore.main()
        result = json.loads(latest.read_text())
        self.assertEqual({row['symbol'] for row in result['candidates']}, {'641A.T', '999A.T', 'MU'})
        self.assertEqual(result['tracking'], [record])
        self.assertEqual(result['generatedAt'], '2026-10-05T21:00:00Z')
        tracking = self.root / 'tracking.json'
        tracking.write_text(json.dumps({'schemaVersion': 2, 'records': [record]}), encoding='utf-8')
        with patch.object(update_tracking, 'LATEST', latest), patch.object(update_tracking, 'TRACKING', tracking), redirect_stdout(io.StringIO()):
            update_tracking.main()
        retained = json.loads(tracking.read_text())['records']
        self.assertEqual(len(retained), 1)
        for key, value in record.items():
            self.assertEqual(retained[0][key], value)


if __name__ == '__main__':
    unittest.main()
