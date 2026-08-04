#!/usr/bin/python3
import argparse
import getpass
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from command_validation import validate_command
from simulator import msg_queue


ROOT = Path(__file__).resolve().parent
LOG = Path('/var/log/sim/tool.log')
STATUS_DIR = Path('/var/log/sim')


def wait_for(check, process, timeout, description):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        if process.poll() is not None:
            raise RuntimeError(f'simulator exited while waiting for {description}')
        time.sleep(0.1)
    raise RuntimeError(f'timed out waiting for {description}')


def log_contains(offset, text):
    try:
        with LOG.open(errors='replace') as log_file:
            log_file.seek(offset)
            return text in log_file.read()
    except OSError:
        return False


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(5)


def stop_capture(process):
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(5)


def build_parser():
    parser = argparse.ArgumentParser(description='Run one complete S1 and GTP-U smoke test')
    parser.add_argument('--imsi', required=True)
    parser.add_argument('--key', dest='ki', help='prompted securely when omitted')
    parser.add_argument('--opc', help='prompted securely when omitted')
    parser.add_argument('--enb-ip', default='192.168.29.31')
    parser.add_argument('--mme-ip', default='192.168.28.17')
    parser.add_argument('--s1-port', default='36412')
    parser.add_argument('--gtpu-ip', default='192.168.31.31')
    parser.add_argument('--mcc', default='460')
    parser.add_argument('--mnc', default='06')
    parser.add_argument('--enb-id', default='100000')
    parser.add_argument('--tac1', default='24066')
    parser.add_argument('--tac2', default='24070')
    parser.add_argument('--apn', default='3gnet')
    parser.add_argument('--pdn-type', dest='pdp_type', default='3')
    parser.add_argument(
        '--target', action='append', dest='targets',
        help='repeatable ping target; defaults to 8.8.8.8',
    )
    parser.add_argument('--interface', default='enp10s0')
    parser.add_argument('--capture', default='/tmp/enb-smoke-test.pcap')
    parser.add_argument('--timeout', type=float, default=30)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if os.geteuid() != 0:
        raise RuntimeError('run as root')

    args.ki = args.ki or getpass.getpass('K: ')
    args.opc = args.opc or getpass.getpass('OPc: ')
    start = validate_command({
        'procedure': 'start-simulator', 'enb_ip': args.enb_ip,
        'mme_ip': args.mme_ip, 'gtpu_ip': args.gtpu_ip,
        's1_port': args.s1_port,
    })
    setup = validate_command({
        'procedure': 's1-setup', 'mcc': args.mcc, 'mnc': args.mnc,
        'enb_id': args.enb_id, 'tac1': args.tac1, 'tac2': args.tac2,
    })
    attach = validate_command({
        'procedure': 'attach', 'imsi': args.imsi, 'ki': args.ki,
        'opc': args.opc, 'mcc': args.mcc, 'mnc': args.mnc,
        'apn': args.apn, 'pdp_type': args.pdp_type,
    })

    if subprocess.run(['pgrep', '-f', 'eNB_LOCAL.py'], capture_output=True).returncode == 0:
        raise RuntimeError('another eNB_LOCAL.py process is already running')

    process = capture = None
    attached = detached = False
    try:
        enb_status = STATUS_DIR / 'enb_status'
        old_enb_mtime = enb_status.stat().st_mtime_ns if enb_status.exists() else None
        process = subprocess.Popen([
            sys.executable, str(ROOT / 'eNB_LOCAL.py'), '-i', start['enb_ip'],
            '-m', start['mme_ip'], '--s1-port', start['s1_port'],
            '--gtpu-ip', start['gtpu_ip'],
        ], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_for(
            lambda: enb_status.exists()
            and enb_status.stat().st_mtime_ns != old_enb_mtime
            and enb_status.read_text().strip() == 'CONNECTED',
            process, args.timeout, 'SCTP connection')
        print('SCTP CONNECTED')

        offset = LOG.stat().st_size
        msg_queue(setup)
        wait_for(lambda: log_contains(offset, 'S1SetupResponse received'),
                 process, args.timeout, 'S1 Setup')
        print('S1 SETUP OK')

        status_path = STATUS_DIR / f'ue_{args.imsi}_status'
        old_mtime = status_path.stat().st_mtime_ns if status_path.exists() else None
        msg_queue(attach)

        def ue_status():
            try:
                if status_path.stat().st_mtime_ns == old_mtime:
                    return None
                value = status_path.read_text().strip()
                return value if value in ('CONNECTED', 'FAILED') else None
            except OSError:
                return None

        status = wait_for(ue_status, process, args.timeout, 'Attach')
        if status != 'CONNECTED':
            raise RuntimeError(f'Attach ended with {status}')
        attached = True
        print('ATTACH CONNECTED')

        subprocess.run(['ip', 'netns', 'exec', args.imsi, 'ip', 'route'], check=True)
        capture_path = Path(args.capture)
        capture_path.parent.mkdir(parents=True, exist_ok=True)
        capture_path.unlink(missing_ok=True)
        capture = subprocess.Popen([
            'tcpdump', '-ni', args.interface, '-s0', '-w', str(capture_path),
            'udp port 2152',
        ])
        time.sleep(0.5)
        if capture.poll() is not None:
            raise RuntimeError('tcpdump exited before traffic generation')
        for target in args.targets or ('8.8.8.8',):
            ping = subprocess.run([
                'ip', 'netns', 'exec', args.imsi,
                'ping', '-c', '2', '-W', '2', target,
            ])
            if ping.returncode != 0:
                raise RuntimeError(f'user-plane ping failed: {target}')
        stop_capture(capture)
        capture = None
        if capture_path.stat().st_size <= 24:
            raise RuntimeError('no GTP-U packets were captured')
        print(f'GTP-U OK: {capture_path}')

        offset = LOG.stat().st_size
        msg_queue(validate_command({'procedure': 'detach', 'imsi': args.imsi}))
        wait_for(lambda: log_contains(offset, 'DetachAccept received'),
                 process, args.timeout, 'Detach')
        detached = True
        print('SMOKE TEST PASSED')
    finally:
        stop_capture(capture)
        if attached and not detached and process is not None and process.poll() is None:
            msg_queue({'procedure': 'detach', 'imsi': args.imsi})
            time.sleep(1)
        stop_process(process)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as error:
        print(f'FAILED: {error}', file=sys.stderr)
        raise SystemExit(1)
