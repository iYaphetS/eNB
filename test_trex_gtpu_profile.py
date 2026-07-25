import unittest

from trex_gtpu_profile import gtp_header


class TrexGtpuProfileTest(unittest.TestCase):
    def test_builds_gtpu_header(self):
        self.assertEqual(
            b'\x30\xff\x00\x40\x00\x00\x03\xe9',
            gtp_header(1001, 64))

    def test_rejects_invalid_teid(self):
        with self.assertRaisesRegex(ValueError, 'TEID'):
            gtp_header(0x100000000, 64)


if __name__ == '__main__':
    unittest.main()
