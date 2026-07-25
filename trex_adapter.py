#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def active_bearers(events):
    active = {}
    for event in events:
        key = (str(event['imsi']), int(event['bearer_id']))
        if event['event'] == 'bearer-down':
            active.pop(key, None)
        elif event['event'] in ('bearer-up', 'bearer-update'):
            active[key] = {
                field: event[field] for field in (
                    'imsi', 'ue_ip', 'upf_ip', 'enb_gtpu_ip',
                    'uplink_teid', 'downlink_teid', 'bearer_id',
                )
            }
    return [active[key] for key in sorted(active)]


def read_events(path):
    with Path(path).open(encoding='utf-8') as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'invalid JSON on line {line_number}: {error}') from error


def build_manifest(events, uplink_pps=1000, downlink_pps=1000, payload_size=64):
    sessions = active_bearers(events)
    return {
        'schema_version': 1,
        'generator': 'eNB TRex adapter',
        'traffic': {
            'uplink_pps_per_bearer': uplink_pps,
            'downlink_pps_per_bearer': downlink_pps,
            'inner_payload_size': payload_size,
        },
        'sessions': sessions,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Build an active TRex GTP-U session manifest from bearer events')
    parser.add_argument('--events', required=True, help='bearer event JSONL file')
    parser.add_argument('--output', required=True, help='output manifest JSON file')
    parser.add_argument('--uplink-pps', type=int, default=1000)
    parser.add_argument('--downlink-pps', type=int, default=1000)
    parser.add_argument('--payload-size', type=int, default=64)
    args = parser.parse_args(argv)
    for name in ('uplink_pps', 'downlink_pps', 'payload_size'):
        if getattr(args, name) < 0:
            parser.error(f'--{name.replace("_", "-")} must be non-negative')
    if args.payload_size < 28:
        parser.error('--payload-size must be at least 28')
    try:
        manifest = build_manifest(
            read_events(args.events), args.uplink_pps, args.downlink_pps,
            args.payload_size)
        Path(args.output).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
