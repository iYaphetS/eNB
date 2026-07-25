import csv
import tempfile
import unittest
from pathlib import Path

from load_test import build_summary, load_subscribers, percentile, run_attach_load


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class LoadTestTest(unittest.TestCase):
    def test_loads_and_validates_subscribers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'subscribers.csv'
            with path.open('w', newline='') as subscriber_file:
                writer = csv.DictWriter(
                    subscriber_file,
                    fieldnames=('imsi', 'key', 'opc', 'mcc', 'mnc'),
                )
                writer.writeheader()
                writer.writerow({
                    'imsi': '111111000000001',
                    'key': '0' * 32,
                    'opc': '1' * 32,
                    'mcc': '111',
                    'mnc': '111',
                })
            self.assertEqual('111111000000001', load_subscribers(path)[0]['imsi'])

    def test_rejects_duplicate_imsi(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'subscribers.csv'
            path.write_text(
                'imsi,key,opc,mcc,mnc\n'
                f"111111000000001,{'0' * 32},{'1' * 32},111,111\n"
                f"111111000000001,{'2' * 32},{'3' * 32},111,111\n"
            )
            with self.assertRaisesRegex(ValueError, 'duplicate IMSI'):
                load_subscribers(path)

    def test_runs_rate_limited_attach_and_records_outcomes(self):
        subscribers = [
            {'imsi': str(111111000000001 + index), 'key': '0' * 32,
             'opc': '1' * 32, 'mcc': '111', 'mnc': '111'}
            for index in range(3)
        ]
        clock = FakeClock()
        sent_at = {}
        delays = {
            subscribers[0]['imsi']: (0.1, 'CONNECTED'),
            subscribers[1]['imsi']: (0.2, 'FAILED'),
        }

        def queue_put(message):
            sent_at[message['imsi']] = clock.time()

        def status_reader(imsi, _):
            if imsi not in delays:
                return None
            delay, status = delays[imsi]
            return status if clock.time() - sent_at[imsi] >= delay else None

        report = run_attach_load(
            subscribers,
            queue_put,
            status_reader,
            attach_rate=2,
            timeout=0.3,
            poll_interval=0.05,
            clock=clock.time,
            sleep=clock.sleep,
        )

        self.assertEqual(1, report['summary']['connected'])
        self.assertEqual(1, report['summary']['failed'])
        self.assertEqual(1, report['summary']['timed_out'])
        self.assertAlmostEqual(2, report['summary']['achieved_attach_rate'], delta=0.1)
        self.assertEqual(3, len(sent_at))

    def test_percentiles_use_nearest_rank(self):
        self.assertEqual(30, percentile([10, 20, 30, 40], 75))
        self.assertIsNone(percentile([], 95))

    def test_summary_handles_no_successes(self):
        summary = build_summary(
            [{'imsi': '1', 'status': 'FAILED', 'latency_ms': 10}],
            1,
            2,
        )
        self.assertEqual(0, summary['success_rate'])
        self.assertIsNone(summary['latency_ms']['p95'])


if __name__ == '__main__':
    unittest.main()
