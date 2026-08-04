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
            'pdp_type': '3',
        }
        self.assertIs(command, validate_command(command))

    def test_rejects_invalid_pdn_type(self):
        with self.assertRaisesRegex(ValueError, 'pdn_type'):
            validate_command({'procedure': 's1-setup', 'pdp_type': '4'})

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

    def test_accepts_external_gtpu_start(self):
        command = {
            'procedure': 'start-simulator',
            'enb_ip': '192.0.2.1',
            'mme_ip': '192.0.2.2',
            'gtpu_ip': '198.51.100.10',
            's1_port': '36412',
            'external_gtpu': True,
            'bearer_events': '/var/log/sim/bearers.jsonl',
        }
        self.assertIs(command, validate_command(command))

    def test_rejects_invalid_s1_port(self):
        with self.assertRaisesRegex(ValueError, 's1_port'):
            validate_command({'procedure': 's1-setup', 's1_port': '65536'})


if __name__ == '__main__':
    unittest.main()
