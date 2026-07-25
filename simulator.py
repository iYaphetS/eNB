#!/usr/bin/python3
import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from command_validation import validate_command


SERVICE_PATH = Path('/lib/systemd/system/tool.service')


def build_parser():
    parser = argparse.ArgumentParser(description='Control the eNB S1 simulator')
    parser.add_argument('-P', '--procedure', dest='procedure', required=True)
    parser.add_argument('-I', '--enbip', dest='enb_ip')
    parser.add_argument('-M', '--mmeip', dest='mme_ip')
    parser.add_argument('-S', '--imsi')
    parser.add_argument('-K', '--key', dest='ki')
    parser.add_argument('-C', '--opc')
    parser.add_argument('-L', '--mcc')
    parser.add_argument('-N', '--mnc')
    parser.add_argument('-A', '--apn')
    parser.add_argument('-T', '--tac1')
    parser.add_argument('-V', '--tac2')
    parser.add_argument('-E', '--enbid', dest='enb_id')
    parser.add_argument('--gtpu-ip', dest='gtpu_ip')
    parser.add_argument('--external-gtpu', action='store_true')
    parser.add_argument('--bearer-events', dest='bearer_events')
    return parser


def command_from_args(args):
    command = {
        key: value if isinstance(value, bool) else str(value)
        for key, value in vars(args).items()
        if value is not None and value is not False
    }
    return validate_command(command)


def run_command(command):
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"command failed: {' '.join(command)}") from error


def msg_queue(command):
    from ipcqueue import posixmq

    queue = posixmq.Queue('/foo')
    queue.put(command)


def service_definition(enb_ip, mme_ip, project_dir=None, python=None,
                       gtpu_ip=None, external_gtpu=False, bearer_events=None):
    project_dir = str(Path(project_dir or Path(__file__).resolve().parent)).replace('\\', '/')
    python = python or sys.executable
    executable = f'{project_dir}/eNB_LOCAL.py'
    command = [python, str(executable), '-i', enb_ip, '-m', mme_ip]
    if gtpu_ip:
        command.extend(['--gtpu-ip', gtpu_ip])
    if external_gtpu:
        command.append('--external-gtpu')
    if bearer_events:
        command.extend(['--bearer-events', bearer_events])
    return '\n'.join([
        '[Unit]',
        'Description=eNB S1 Simulator',
        'After=network-online.target',
        '',
        '[Service]',
        'Restart=always',
        'User=root',
        f'WorkingDirectory={project_dir}',
        'ExecStart=' + ' '.join(map(shlex.quote, command)),
        '',
        '[Install]',
        'WantedBy=multi-user.target',
        '',
    ])


def start_sim(enb_ip, mme_ip, gtpu_ip=None, external_gtpu=False,
              bearer_events=None):
    SERVICE_PATH.write_text(service_definition(
        enb_ip, mme_ip, gtpu_ip=gtpu_ip, external_gtpu=external_gtpu,
        bearer_events=bearer_events))
    run_command(['sudo', 'systemctl', 'daemon-reload'])
    run_command(['sudo', 'systemctl', 'enable', '--now', SERVICE_PATH.name])


def stop_sim():
    run_command(['sudo', 'systemctl', 'stop', SERVICE_PATH.name])
    try:
        SERVICE_PATH.unlink()
    except FileNotFoundError:
        pass
    run_command(['sudo', 'systemctl', 'daemon-reload'])


def main(argv=None):
    parser = build_parser()
    try:
        command = command_from_args(parser.parse_args(argv))
        procedure = command['procedure']
        if procedure == 'start-simulator':
            start_sim(
                command['enb_ip'], command['mme_ip'], command.get('gtpu_ip'),
                command.get('external_gtpu', False), command.get('bearer_events'))
        elif procedure == 'stop-simulator':
            stop_sim()
        else:
            msg_queue(command)
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
