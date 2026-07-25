import unittest

from load_result_channel import LoadResultPublisher, LoadResultServer


class FakeDatagramNetwork:
    def __init__(self):
        self.queues = {}

    def socket(self, family, socket_type):
        return FakeDatagramSocket(self)


class FakeDatagramSocket:
    def __init__(self, network):
        self.network = network
        self.path = None

    def bind(self, path):
        self.path = path
        self.network.queues[path] = []

    def setblocking(self, blocking):
        pass

    def sendto(self, payload, path):
        self.network.queues[path].append(payload)

    def recv(self, size):
        queue = self.network.queues[self.path]
        if not queue:
            raise BlockingIOError()
        return queue.pop(0)

    def close(self):
        pass


class LoadResultChannelTest(unittest.TestCase):
    def test_publishes_event_for_matching_run(self):
        network = FakeDatagramNetwork()
        server = LoadResultServer(
            run_id='run-1',
            socket_dir='/tmp',
            socket_factory=network.socket,
            unix_family=1,
        )
        server.__enter__()
        publisher = LoadResultPublisher(
            socket_factory=network.socket,
            clock=lambda: 123.0,
            unix_family=1,
        )
        published = publisher.publish({
            'IMSI': '111111000000001',
            'LOAD-TEST-RUN-ID': 'run-1',
            'LOAD-TEST-RESULT-SOCKET': server.path,
        }, 'CONNECTED')

        self.assertTrue(published)
        self.assertEqual([{
            'run_id': 'run-1',
            'imsi': '111111000000001',
            'status': 'CONNECTED',
            'emitted_at': 123.0,
        }], server.read())
        server.__exit__(None, None, None)

    def test_ignores_session_without_load_test_metadata(self):
        publisher = LoadResultPublisher()
        self.assertFalse(publisher.publish({'IMSI': '1'}, 'FAILED'))


if __name__ == '__main__':
    unittest.main()
