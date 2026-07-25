import json
import tempfile
import unittest
from pathlib import Path

from trex_adapter import BearerState, build_manifest, write_manifest


class TrexAdapterTest(unittest.TestCase):
    def test_keeps_only_active_latest_bearers(self):
        base = {
            'imsi': '111111000000001', 'ue_ip': '10.45.0.2',
            'upf_ip': '192.0.2.20', 'enb_gtpu_ip': '192.0.2.10',
            'uplink_teid': 1001, 'downlink_teid': 2001, 'bearer_id': 5,
        }
        events = [
            dict(base, event='bearer-up'),
            dict(base, event='bearer-update', uplink_teid=1002),
            dict(base, event='bearer-up', imsi='111111000000002'),
            dict(base, event='bearer-down', imsi='111111000000002'),
        ]
        manifest = build_manifest(events, 10, 20, 128)
        self.assertEqual(1, len(manifest['sessions']))
        self.assertEqual(1002, manifest['sessions'][0]['uplink_teid'])
        self.assertEqual(10, manifest['traffic']['uplink_pps_per_bearer'])

    def test_shards_by_stable_imsi_hash(self):
        base = {
            'ue_ip': '10.45.0.2', 'upf_ip': '192.0.2.20',
            'enb_gtpu_ip': '192.0.2.10', 'uplink_teid': 1001,
            'downlink_teid': 2001, 'bearer_id': 5, 'event': 'bearer-up',
        }
        events = [dict(base, imsi=f'11111100000000{i}') for i in range(1, 5)]
        left = build_manifest(events, shard_count=2, shard_index=0)
        right = build_manifest(events, shard_count=2, shard_index=1)
        self.assertEqual(4, len(left['sessions']) + len(right['sessions']))
        self.assertEqual(2, left['shard']['count'])
        self.assertEqual(0, left['shard']['index'])

    def test_reports_sequence_gaps_and_writes_manifest(self):
        base = {
            'imsi': '111111000000001', 'ue_ip': '10.45.0.2',
            'upf_ip': '192.0.2.20', 'enb_gtpu_ip': '192.0.2.10',
            'uplink_teid': 1001, 'downlink_teid': 2001, 'bearer_id': 5,
        }
        manifest = build_manifest([
            dict(base, event='bearer-up', sequence=1),
            dict(base, event='bearer-update', sequence=3, uplink_teid=1002),
        ])
        self.assertEqual(1, manifest['events']['sequence_gaps'])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'manifest.json'
            write_manifest(output, manifest)
            self.assertEqual(2, json.loads(output.read_text())['events']['processed'])
            self.assertFalse(Path(str(output) + '.tmp').exists())
            compact = Path(directory) / 'compact.json'
            write_manifest(compact, manifest, compact=True)
            self.assertLess(compact.stat().st_size, output.stat().st_size)

    def test_new_run_clears_stale_sessions(self):
        base = {
            'event': 'bearer-up', 'ue_ip': '10.45.0.2',
            'upf_ip': '192.0.2.20', 'enb_gtpu_ip': '192.0.2.10',
            'uplink_teid': 1001, 'downlink_teid': 2001, 'bearer_id': 5,
        }
        manifest = build_manifest([
            dict(base, imsi='111111000000001', sequence=1, run_id='old'),
            dict(base, imsi='111111000000002', sequence=1, run_id='new'),
        ])
        self.assertEqual(
            ['111111000000002'],
            [session['imsi'] for session in manifest['sessions']])
        self.assertEqual(1, manifest['events']['restarts'])
        self.assertEqual('new', manifest['events']['run_id'])

    def test_invalid_event_does_not_mutate_state(self):
        state = BearerState()
        with self.assertRaises(ValueError):
            state.apply({
                'event': 'unknown', 'imsi': '111111000000001',
                'bearer_id': 5, 'run_id': 'new', 'sequence': 1,
            })
        self.assertEqual(0, state.event_count)
        self.assertIsNone(state.run_id)

    def test_maintains_incremental_shard_index(self):
        state = BearerState(4)
        base = {
            'event': 'bearer-up', 'ue_ip': '10.45.0.2',
            'upf_ip': '192.0.2.20', 'enb_gtpu_ip': '192.0.2.10',
            'uplink_teid': 1001, 'downlink_teid': 2001, 'bearer_id': 5,
        }
        results = []
        for index in range(1, 5):
            results.append(state.apply(
                dict(base, imsi=f'11111100000000{index}')))
        for shard_index in range(4):
            expected = sum(
                result['shard_index'] == shard_index for result in results)
            self.assertEqual(
                expected, len(state.sessions(4, shard_index)))
        removed = dict(base, event='bearer-down', imsi='111111000000001')
        shard_index = state.apply(removed)['shard_index']
        self.assertNotIn(
            '111111000000001',
            [item['imsi'] for item in state.sessions(4, shard_index)])


if __name__ == '__main__':
    unittest.main()
