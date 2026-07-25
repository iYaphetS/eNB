import unittest

from trex_scale_benchmark import benchmark


class TrexScaleBenchmarkTest(unittest.TestCase):
    def test_benchmarks_small_population(self):
        result = benchmark(20, 4)
        self.assertEqual(20, result['total_sessions'])
        self.assertEqual(4, len(result['sessions_per_shard']))
        self.assertGreater(result['apply_events_per_second'], 0)


if __name__ == '__main__':
    unittest.main()
