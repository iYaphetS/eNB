import unittest

from resource_registry import ResourceRegistry


class FakeResource:
    def __init__(self, name, closed):
        self.name = name
        self.closed = closed

    def close(self):
        self.closed.append(self.name)


class ResourceRegistryTest(unittest.TestCase):
    def test_closes_resources_in_reverse_order(self):
        closed = []
        registry = ResourceRegistry(close_fd=lambda fd: closed.append(f'fd:{fd}'))
        registry.add(FakeResource('socket', closed))
        registry.add_fd(10)

        registry.close()

        self.assertEqual(['fd:10', 'socket'], closed)

    def test_close_is_idempotent(self):
        registry = ResourceRegistry()
        registry.close()
        registry.close()


if __name__ == '__main__':
    unittest.main()
