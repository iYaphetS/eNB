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
            gtpu_ip=None,
            external_gtpu=False,
            bearer_events=None,
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

    def test_service_configures_external_gtpu(self):
        service = service_definition(
            '192.0.2.1', '192.0.2.2', project_dir='/opt/enb',
            python='/usr/bin/python3', gtpu_ip='198.51.100.10',
            external_gtpu=True, bearer_events='/var/log/sim/bearers.jsonl')
        self.assertIn('--gtpu-ip 198.51.100.10', service)
        self.assertIn('--external-gtpu', service)
        self.assertIn('--bearer-events /var/log/sim/bearers.jsonl', service)


if __name__ == '__main__':
    unittest.main()
