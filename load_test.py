#!/usr/bin/python3
import argparse
import csv
import json
import math
import time
from pathlib import Path


TERMINAL_STATUSES = {'CONNECTED', 'FAILED'}


def load_subscribers(path):
    subscribers = []
    seen_imsis = set()
    with open(path, newline='') as subscriber_file:
        for line_number, row in enumerate(csv.DictReader(subscriber_file), start=2):
            subscriber = {key: (value or '').strip() for key, value in row.items()}
            _validate_subscriber(subscriber, line_number)
            if subscriber['imsi'] in seen_imsis:
                raise ValueError(f"line {line_number}: duplicate IMSI {subscriber['imsi']}")
            seen_imsis.add(subscriber['imsi'])
            subscribers.append(subscriber)
    if not subscribers:
        raise ValueError('subscriber file is empty')
    return subscribers


def _validate_subscriber(subscriber, line_number):
    required = ('imsi', 'key', 'opc', 'mcc', 'mnc')
    missing = [field for field in required if not subscriber.get(field)]
    if missing:
        raise ValueError(f"line {line_number}: missing {', '.join(missing)}")
    if len(subscriber['imsi']) != 15 or not subscriber['imsi'].isdigit():
        raise ValueError(f"line {line_number}: IMSI must contain 15 digits")
    for field in ('key', 'opc'):
        value = subscriber[field]
        if len(value) != 32 or any(char not in '0123456789abcdefABCDEF' for char in value):
            raise ValueError(f"line {line_number}: {field} must contain 32 hex characters")
    if not subscriber['mcc'].isdigit() or not subscriber['mnc'].isdigit():
        raise ValueError(f"line {line_number}: MCC and MNC must be numeric")


def percentile(values, percentile_value):
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile_value / 100) * len(ordered)))
    return ordered[rank - 1]


def build_summary(results, started_at, finished_at):
    connected = [result for result in results if result['status'] == 'CONNECTED']
    failed = [result for result in results if result['status'] == 'FAILED']
    timed_out = [result for result in results if result['status'] == 'TIMEOUT']
    latencies = [result['latency_ms'] for result in connected]
    total = len(results)
    return {
        'total': total,
        'connected': len(connected),
        'failed': len(failed),
        'timed_out': len(timed_out),
        'success_rate': len(connected) / total if total else 0,
        'duration_seconds': round(finished_at - started_at, 3),
        'latency_ms': {
            'min': min(latencies) if latencies else None,
            'p50': percentile(latencies, 50),
            'p95': percentile(latencies, 95),
            'p99': percentile(latencies, 99),
            'max': max(latencies) if latencies else None,
        },
    }


class StatusReader:
    def __init__(self, status_dir):
        self.status_dir = Path(status_dir)

    def read(self, imsi, sent_at):
        status_path = self.status_dir / f'ue_{imsi}_status'
        try:
            if status_path.stat().st_mtime < sent_at:
                return None
            status = status_path.read_text().strip().upper()
        except (FileNotFoundError, OSError):
            return None
        return status if status in TERMINAL_STATUSES else None


def run_attach_load(
        subscribers,
        queue_put,
        status_reader,
        attach_rate,
        timeout,
        poll_interval=0.05,
        clock=time.time,
        sleep=time.sleep):
    if attach_rate <= 0:
        raise ValueError('attach rate must be greater than zero')
    if timeout <= 0:
        raise ValueError('timeout must be greater than zero')

    started_at = clock()
    next_send_at = started_at
    interval = 1.0 / attach_rate
    sent_count = 0
    first_sent_at = None
    last_sent_at = None
    pending = {}
    results = []

    while sent_count < len(subscribers) or pending:
        now = clock()
        if sent_count < len(subscribers) and now >= next_send_at:
            subscriber = subscribers[sent_count]
            queue_put({
                'procedure': 'attach',
                'imsi': subscriber['imsi'],
                'ki': subscriber['key'],
                'opc': subscriber['opc'],
                'mcc': subscriber['mcc'],
                'mnc': subscriber['mnc'],
            })
            if first_sent_at is None:
                first_sent_at = now
            last_sent_at = now
            pending[subscriber['imsi']] = now
            sent_count += 1
            next_send_at = started_at + (sent_count * interval)

        for imsi, sent_at in list(pending.items()):
            status = status_reader(imsi, sent_at)
            completed_at = clock()
            if status:
                results.append({
                    'imsi': imsi,
                    'status': status,
                    'latency_ms': round((completed_at - sent_at) * 1000, 3),
                })
                del pending[imsi]
            elif completed_at - sent_at >= timeout:
                results.append({
                    'imsi': imsi,
                    'status': 'TIMEOUT',
                    'latency_ms': round((completed_at - sent_at) * 1000, 3),
                })
                del pending[imsi]

        if sent_count < len(subscribers) or pending:
            sleep(poll_interval)

    finished_at = clock()
    results.sort(key=lambda result: result['imsi'])
    enqueue_duration = (
        (last_sent_at - first_sent_at) + interval
        if first_sent_at is not None else 0
    )
    summary = build_summary(results, started_at, finished_at)
    summary['enqueue_duration_seconds'] = round(enqueue_duration, 3)
    summary['achieved_attach_rate'] = round(sent_count / enqueue_duration, 3)
    return {
        'summary': summary,
        'users': results,
    }


def detach_connected(report, queue_put, detach_rate, sleep=time.sleep):
    if detach_rate <= 0:
        raise ValueError('detach rate must be greater than zero')
    interval = 1.0 / detach_rate
    connected = [user for user in report['users'] if user['status'] == 'CONNECTED']
    for index, user in enumerate(connected):
        queue_put({'procedure': 'detach', 'imsi': user['imsi']})
        if index + 1 < len(connected):
            sleep(interval)
    return len(connected)


def _queue_writer():
    from ipcqueue import posixmq

    queue = posixmq.Queue('/foo')
    return queue.put


def main():
    parser = argparse.ArgumentParser(description='Run a rate-limited S1 attach load test')
    parser.add_argument('--subscribers', required=True, help='CSV with imsi,key,opc,mcc,mnc columns')
    parser.add_argument('--attach-rate', type=float, default=10, help='Attach requests per second')
    parser.add_argument('--timeout', type=float, default=30, help='Per-user Attach timeout in seconds')
    parser.add_argument('--status-dir', default='/var/log/sim', help='Simulator status directory')
    parser.add_argument('--hold-seconds', type=float, default=0, help='Time to keep successful UEs online')
    parser.add_argument('--detach', action='store_true', help='Detach successful UEs after the hold period')
    parser.add_argument('--detach-rate', type=float, default=20, help='Detach requests per second')
    parser.add_argument('--report', default='load-test-report.json', help='JSON report path')
    args = parser.parse_args()

    subscribers = load_subscribers(args.subscribers)
    queue_put = _queue_writer()
    report = run_attach_load(
        subscribers,
        queue_put,
        StatusReader(args.status_dir).read,
        args.attach_rate,
        args.timeout,
    )
    if args.hold_seconds > 0:
        time.sleep(args.hold_seconds)
    if args.detach:
        report['summary']['detach_queued'] = detach_connected(
            report,
            queue_put,
            args.detach_rate,
        )

    report['configuration'] = {
        'attach_rate': args.attach_rate,
        'timeout': args.timeout,
        'hold_seconds': args.hold_seconds,
        'detach': args.detach,
        'detach_rate': args.detach_rate,
    }
    Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
