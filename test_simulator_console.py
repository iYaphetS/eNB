import unittest

from simulator_console import SimulatorConsole, parse_rate


class SimulatorConsoleTest(unittest.TestCase):
    def test_parses_rate_and_optional_count(self):
        self.assertEqual((10.0, None), parse_rate('10'))
        self.assertEqual((2.5, 20), parse_rate('2.5 20'))
        with self.assertRaises(ValueError):
            parse_rate('0')

    def test_accepts_hyphenated_rate_commands(self):
        command, argument, _ = SimulatorConsole([]).parseline('attach-rate 10 20')
        self.assertEqual('attach_rate', command)
        self.assertEqual('10 20', argument)


if __name__ == '__main__':
    unittest.main()
