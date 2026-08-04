import unittest

from eNB_LOCAL import nas_pco


class NasPcoTest(unittest.TestCase):
    def test_default_pco_does_not_request_pcscf(self):
        self.assertNotIn(b'\x00\x0c\x00\x00', nas_pco(1, False))
        self.assertNotIn(b'\x00\x01\x00\x00', nas_pco(2, False))
        self.assertNotIn(b'\x00\x0c\x00\x00', nas_pco(3, False))
        self.assertNotIn(b'\x00\x01\x00\x00', nas_pco(3, False))


if __name__ == '__main__':
    unittest.main()
