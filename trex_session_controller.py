#!/usr/bin/env python3
import argparse
import json
import logging
import select
import signal
import socket
from pathlib import Path

from trex_adapter import BearerState, build_manifest_from_state, write_manifest


def output_path(template, shard_index):
    try:
        return template.format(index=shard_index)
    except (KeyError, ValueError) as error:
        raise ValueError('invalid output template; use {index} for shard number') from error


def write_shards(state, output_template, shard_count, uplink_pps,
                 downlink_pps, payload_size, shard_indices=None, compact=False):
    paths = []
    shard_indices = range(shard_count) if shard_indices is None else shard_indices
    for shard_index in sorted(shard_indices):
        path = output_path(output_template, shard_index)
        manifest = build_manifest_from_state(
            state, uplink_pps, downlink_pps, payload_size,
            shard_count, shard_index)
        write_manifest(path, manifest, compact)
        paths.append(path)
    return paths


def run_controller(socket_path, output_template, shard_count=1,
                   uplink_pps=1000, downlink_pps=1000, payload_size=64,
                   flush_interval=0.25, receive_buffer=16 * 1024 * 1024,
                   compact=False):
    socket_path = Path(socket_path)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()
    receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, receive_buffer)
    receiver.bind(str(socket_path))
    receiver.setblocking(False)
    logging.info(
        'Bearer event socket receive buffer: %d bytes',
        receiver.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
    state = BearerState(shard_count)
    dirty_shards = set(range(shard_count))
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while running:
            readable, _, _ = select.select([receiver], [], [], flush_interval)
            if readable:
                while True:
                    try:
                        payload = receiver.recv(65535)
                    except BlockingIOError:
                        break
                    try:
                        event = json.loads(payload)
                        result = state.apply(event)
                        if result['restarted']:
                            dirty_shards.update(range(shard_count))
                        else:
                            dirty_shards.add(result['shard_index'])
                    except (UnicodeDecodeError, json.JSONDecodeError,
                            KeyError, TypeError, ValueError):
                        logging.exception('Dropping invalid bearer event')
            if dirty_shards:
                write_shards(
                    state, output_template, shard_count, uplink_pps,
                    downlink_pps, payload_size, dirty_shards, compact)
                dirty_shards.clear()
    finally:
        receiver.close()
        if socket_path.exists():
            socket_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Continuously build sharded TRex manifests from bearer events')
    parser.add_argument('--socket', required=True, help='Unix datagram socket path')
    parser.add_argument('--output-template', required=True,
                        help='manifest path; use {index} for the shard number')
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--uplink-pps', type=int, default=1000)
    parser.add_argument('--downlink-pps', type=int, default=1000)
    parser.add_argument('--payload-size', type=int, default=64)
    parser.add_argument('--flush-interval', type=float, default=0.25)
    parser.add_argument('--receive-buffer', type=int, default=16 * 1024 * 1024)
    parser.add_argument('--compact', action='store_true',
                        help='write compact JSON for large manifests')
    args = parser.parse_args(argv)
    if args.shards < 1:
        parser.error('--shards must be positive')
    if args.payload_size < 28:
        parser.error('--payload-size must be at least 28')
    if args.uplink_pps < 0 or args.downlink_pps < 0:
        parser.error('PPS values must be non-negative')
    if args.flush_interval <= 0:
        parser.error('--flush-interval must be positive')
    if args.receive_buffer <= 0:
        parser.error('--receive-buffer must be positive')
    if args.shards > 1 and '{index}' not in args.output_template:
        parser.error('--output-template must contain {index} for multiple shards')
    try:
        run_controller(
            args.socket, args.output_template, args.shards, args.uplink_pps,
            args.downlink_pps, args.payload_size, args.flush_interval,
            args.receive_buffer, args.compact)
    except OSError as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
