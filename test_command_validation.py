import unittest

from command_validation import validate_command


class CommandValidationTest(unittest.TestCase):
    def test_accepts_valid_attach(self):
        command = {
            'procedure': 'attach',
            'imsi': '111111000000001',
            'ki': '0' * 32,
            'opc': '1' * 32,
            'mcc': '111',
            'mnc': '11',
        }
        self.assertIs(command, validate_command(command))

    def test_rejects_command_injection_in_procedure(self):
        with self.assertRaisesRegex(ValueError, 'procedure'):
            validate_command({'procedure': 'attach; reboot'})

    def test_rejects_legacy_numeric_menu_actions(self):
        with self.assertRaisesRegex(ValueError, 'procedure'):
            validate_command({'procedure': '50'})

    def test_requires_attach_credentials(self):
        with self.assertRaisesRegex(ValueError, 'ki'):
            validate_command({
                'procedure': 'attach',
                'imsi': '111111000000001',
            })

    def test_rejects_invalid_ip_and_ranges(self):
        with self.assertRaises(ValueError):
            validate_command({
                'procedure': 'start-simulator',
                'enb_ip': 'not-an-ip',
                'mme_ip': '127.0.0.1',
            })
        with self.assertRaisesRegex(ValueError, 'tac1'):
            validate_command({'procedure': 's1-setup', 'tac1': '70000'})

    def test_restricts_load_result_socket(self):
        with self.assertRaisesRegex(ValueError, 'result socket'):
            validate_command({
                'procedure': 'attach',
                'imsi': '111111000000001',
                'ki': '0' * 32,
                'opc': '1' * 32,
                'mcc': '111',
                'mnc': '111',
                'load_run_id': '0' * 32,
                'load_result_socket': '/tmp/arbitrary.sock',
            })


if __name__ == '__main__':
    unittest.main()
