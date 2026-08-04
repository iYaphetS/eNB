#!/usr/bin/python3
import argparse
import cmd
import json
import shlex
import subprocess

from command_validation import validate_command
from load_test import StatusReader, detach_connected, load_subscribers, run_attach_load
from simulator import msg_queue


class SimulatorConsole(cmd.Cmd):
    identchars = cmd.Cmd.identchars + '-'
    intro = 'eNB console ready; type help or ? to list commands.'
    prompt = 'enb> '

    def __init__(self, subscribers, timeout=30, apn='3gnet', pdn_type='3'):
        super().__init__()
        self.subscribers = {user['imsi']: user for user in subscribers}
        self.timeout = timeout
        self.apn = apn
        self.pdn_type = pdn_type
        self.connected = set()

    def parseline(self, line):
        command, arg, original = super().parseline(line)
        return (command.replace('-', '_') if command else command, arg, original)

    def emptyline(self):
        pass

    def _user(self, imsi):
        try:
            return dict(self.subscribers[imsi], apn=self.apn, pdn_type=self.pdn_type)
        except KeyError as error:
            raise ValueError(f'IMSI not found in subscriber CSV: {imsi}') from error

    def _attach(self, users, rate):
        report = run_attach_load(
            users, msg_queue, StatusReader('/var/log/sim').read,
            rate, self.timeout,
        )
        self.connected.update(
            user['imsi'] for user in report['users']
            if user['status'] == 'CONNECTED'
        )
        print(json.dumps(report['summary'], indent=2))

    def do_attach(self, arg):
        "attach IMSI: attach one subscriber and wait for the result."
        try:
            parts = shlex.split(arg)
            if len(parts) != 1:
                raise ValueError('usage: attach IMSI')
            self._attach([self._user(parts[0])], 1)
        except (OSError, ValueError) as error:
            print(f'ERROR: {error}')

    def do_attach_rate(self, arg):
        "attach-rate RATE [COUNT]: attach pending CSV users at RATE users/s."
        try:
            rate, count = parse_rate(arg)
            users = [
                self._user(imsi) for imsi in self.subscribers
                if imsi not in self.connected
            ][:count]
            if not users:
                raise ValueError('no pending subscribers')
            self._attach(users, rate)
        except (OSError, ValueError) as error:
            print(f'ERROR: {error}')

    def do_detach(self, arg):
        "detach IMSI: queue one Detach request."
        try:
            parts = shlex.split(arg)
            if len(parts) != 1:
                raise ValueError('usage: detach IMSI')
            imsi = parts[0]
            self._user(imsi)
            msg_queue(validate_command({'procedure': 'detach', 'imsi': imsi}))
            self.connected.discard(imsi)
            print(f'detach queued: {imsi}')
        except (OSError, ValueError) as error:
            print(f'ERROR: {error}')

    def do_detach_rate(self, arg):
        "detach-rate RATE [COUNT]: queue tracked UEs at RATE users/s."
        try:
            rate, count = parse_rate(arg)
            imsis = sorted(self.connected)[:count]
            if not imsis:
                raise ValueError('no connected subscribers tracked by this console')
            report = {'users': [
                {'imsi': imsi, 'status': 'CONNECTED'} for imsi in imsis
            ]}
            queued = detach_connected(report, msg_queue, rate)
            self.connected.difference_update(imsis)
            print(f'detach queued: {queued}')
        except (OSError, ValueError) as error:
            print(f'ERROR: {error}')

    def do_ping(self, arg):
        "ping IMSI [TARGET] [COUNT]: ping from the UE namespace."
        try:
            parts = shlex.split(arg)
            if not 1 <= len(parts) <= 3:
                raise ValueError('usage: ping IMSI [TARGET] [COUNT]')
            imsi = parts[0]
            self._user(imsi)
            target = parts[1] if len(parts) >= 2 else '8.8.8.8'
            count = int(parts[2]) if len(parts) == 3 else 2
            if not 1 <= count <= 100:
                raise ValueError('COUNT must be between 1 and 100')
            subprocess.run([
                'ip', 'netns', 'exec', imsi,
                'ping', '-c', str(count), '-W', '2', '--', target,
            ], check=False)
        except (OSError, ValueError) as error:
            print(f'ERROR: {error}')

    def do_status(self, arg):
        "status: show subscribers tracked as connected by this console."
        if self.connected:
            print('\n'.join(sorted(self.connected)))
        else:
            print('no connected subscribers tracked by this console')

    def do_quit(self, arg):
        "quit: leave the console without stopping the simulator."
        return True

    def do_EOF(self, arg):
        print()
        return True


def parse_rate(arg):
    parts = shlex.split(arg)
    if not 1 <= len(parts) <= 2:
        raise ValueError('expected RATE [COUNT]')
    rate = float(parts[0])
    count = int(parts[1]) if len(parts) == 2 else None
    if rate <= 0:
        raise ValueError('RATE must be greater than zero')
    if count is not None and count <= 0:
        raise ValueError('COUNT must be greater than zero')
    return rate, count


def main(argv=None):
    parser = argparse.ArgumentParser(description='Interactive eNB simulator console')
    parser.add_argument('--subscribers', required=True)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--apn', default='3gnet')
    parser.add_argument('--pdn-type', default='3', choices=('1', '2', '3', '5'))
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be greater than zero')
    SimulatorConsole(
        load_subscribers(args.subscribers), args.timeout, args.apn, args.pdn_type,
    ).cmdloop()


if __name__ == '__main__':
    main()
