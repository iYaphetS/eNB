import json
import tempfile
import unittest
from pathlib import Path

from bearer_export import BearerEventPublisher, build_bearer_records


def session():
    return {
        'IMSI': '111111000000001',
        'PDN-ADDRESS-IPV4': '10.45.0.2',
        'ENB-GTP-ADDRESS-INT': int.from_bytes(b'\xc0\x00\x02\x0a', 'big'),
        'RAB-ID': [5],
        'SGW-GTP-ADDRESS': [b'\xc0\x00\x02\x14'],
        'SGW-TEID': [b'\x00\x00\x03\xe9'],
        'ENB-TEID': [b'\x00\x00\x07\xd1'],
    }


class BearerExportTest(unittest.TestCase):
    def test_builds_complete_record(self):
        self.assertEqual([{
            'imsi': '111111000000001',
            'ue_ip': '10.45.0.2',
            'upf_ip': '192.0.2.20',
            'enb_gtpu_ip': '192.0.2.10',
            'uplink_teid': 1001,
            'downlink_teid': 2001,
            'bearer_id': 5,
        }], build_bearer_records(session()))

    def test_publishes_lifecycle_without_duplicate_events(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'bearers.jsonl'
            publisher = BearerEventPublisher(
                output, clock=lambda: 123.0, run_id='a' * 32)
            current = session()
            publisher.sync(current)
            publisher.sync(current)
            current['SGW-TEID'][0] = b'\x00\x00\x03\xea'
            publisher.sync(current)
            current['RAB-ID'].clear()
            publisher.sync(current)
            publisher.close()
            events = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(
                ['bearer-up', 'bearer-update', 'bearer-down'],
                [event['event'] for event in events])
            self.assertEqual([1, 2, 3], [event['sequence'] for event in events])
            self.assertEqual(['a' * 32] * 3, [event['run_id'] for event in events])
            self.assertEqual(3, publisher.stats['published'])


if __name__ == '__main__':
    unittest.main()
