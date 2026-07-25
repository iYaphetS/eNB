import unittest

from trex_adapter import build_manifest


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


if __name__ == '__main__':
    unittest.main()
