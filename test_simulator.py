import argparse
import unittest

from simulator import command_from_args, service_definition


class SimulatorTest(unittest.TestCase):
    def test_builds_validated_command(self):
        args = argparse.Namespace(
            procedure='detach',
            enb_ip=None,
            mme_ip=None,
            imsi='111111000000001',
            ki=None,
            opc=None,
            mcc=None,
            mnc=None,
            apn=None,
            tac1=None,
            tac2=None,
            enb_id=None,
        )
        self.assertEqual({
            'procedure': 'detach',
            'imsi': '111111000000001',
        }, command_from_args(args))

    def test_service_uses_actual_project_and_python_paths(self):
        service = service_definition(
            '192.0.2.1',
            '192.0.2.2',
            project_dir='/opt/enb',
            python='/usr/bin/python3',
        )
        self.assertIn('WorkingDirectory=/opt/enb', service)
        self.assertIn(
            'ExecStart=/usr/bin/python3 /opt/enb/eNB_LOCAL.py -i 192.0.2.1 -m 192.0.2.2',
            service,
        )


if __name__ == '__main__':
    unittest.main()
