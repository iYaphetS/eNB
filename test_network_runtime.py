import subprocess
import unittest

from network_runtime import NetworkCommandError, NetworkRuntime


class FakeRunner:
    def __init__(self, namespaces='', bridge_exists=False):
        self.namespaces = namespaces
        self.bridge_exists = bridge_exists
        self.commands = []

    def __call__(self, command, capture_output, text):
        self.commands.append(command)
        if command == ['ip', 'netns', 'list']:
            return subprocess.CompletedProcess(command, 0, self.namespaces, '')
        if command[:5] == ['ip', '-details', 'link', 'show', 'dev']:
            if self.bridge_exists:
                return subprocess.CompletedProcess(command, 0, 'bridge state UP', '')
            return subprocess.CompletedProcess(command, 1, '', 'not found')
        if command[:5] == ['ip', 'link', 'show', 'dev']:
            return subprocess.CompletedProcess(command, 1, '', 'not found')
        return subprocess.CompletedProcess(command, 0, '', '')


class NetworkRuntimeTest(unittest.TestCase):
    def test_creates_bridge_without_deleting_existing_resources(self):
        runner = FakeRunner()
        runtime = NetworkRuntime(runner)
        runtime.ensure_bridge('brlo')

        self.assertIn(['ip', 'link', 'add', 'brlo', 'type', 'bridge'], runner.commands)
        self.assertFalse(any('delete' in command for command in runner.commands))

    def test_reuses_existing_bridge(self):
        runner = FakeRunner(bridge_exists=True)
        runtime = NetworkRuntime(runner)
        runtime.ensure_bridge('brlo')

        self.assertNotIn(['ip', 'link', 'add', 'brlo', 'type', 'bridge'], runner.commands)
        self.assertIn(['ip', 'link', 'set', 'dev', 'brlo', 'up'], runner.commands)

    def test_deletes_only_exact_requested_namespace(self):
        runner = FakeRunner(namespaces='111111000000001\nother-ns\n')
        runtime = NetworkRuntime(runner)
        runtime.delete_ue_namespace('111111000000001')

        delete_commands = [command for command in runner.commands if 'delete' in command]
        self.assertEqual(
            [['ip', 'netns', 'delete', '111111000000001']],
            delete_commands,
        )

    def test_rejects_injected_namespace_name(self):
        runtime = NetworkRuntime(FakeRunner())
        with self.assertRaises(ValueError):
            runtime.delete_ue_namespace('ue;ip link delete brlo')

    def test_refuses_to_reuse_non_bridge_interface(self):
        runner = FakeRunner(bridge_exists=True)
        runner.bridge_exists = True

        def non_bridge(command, capture_output, text):
            if command[:5] == ['ip', '-details', 'link', 'show', 'dev']:
                return subprocess.CompletedProcess(command, 0, 'ether state UP', '')
            return runner(command, capture_output, text)

        with self.assertRaises(NetworkCommandError):
            NetworkRuntime(non_bridge).ensure_bridge('brlo')


if __name__ == '__main__':
    unittest.main()
