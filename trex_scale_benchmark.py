#!/usr/bin/env python3
import argparse
import json
import time

from trex_adapter import BearerState, build_manifest_from_state


def synthetic_event(index):
    return {
        'event': 'bearer-up',
        'imsi': f'111111{index:09d}',
        'ue_ip': f'10.{(index // 65536) % 256}.{(index // 256) % 256}.{index % 256}',
        'upf_ip': '192.0.2.20',
        'enb_gtpu_ip': '192.0.2.10',
        'uplink_teid': index + 1,
        'downlink_teid': index + 100001,
        'bearer_id': 5,
        'sequence': index + 1,
        'run_id': 'benchmark',
    }


def benchmark(user_count=100000, shard_count=8):
    if user_count < 1 or shard_count < 1:
        raise ValueError('user_count and shard_count must be positive')
    state = BearerState(shard_count)
    started = time.perf_counter()
    for index in range(1, user_count + 1):
        state.apply(synthetic_event(index))
    apply_seconds = time.perf_counter() - started
    started = time.perf_counter()
    manifests = [
        build_manifest_from_state(state, 1000, 1000, 64, shard_count, shard)
        for shard in range(shard_count)
    ]
    render_seconds = time.perf_counter() - started
    return {
        'users': user_count,
        'shards': shard_count,
        'apply_seconds': round(apply_seconds, 6),
        'render_seconds': round(render_seconds, 6),
        'apply_events_per_second': round(user_count / apply_seconds, 2),
        'sessions_per_shard': [len(manifest['sessions']) for manifest in manifests],
        'total_sessions': sum(len(manifest['sessions']) for manifest in manifests),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Benchmark TRex bearer state at scale')
    parser.add_argument('--users', type=int, default=100000)
    parser.add_argument('--shards', type=int, default=8)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(benchmark(args.users, args.shards), indent=2))
    except ValueError as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
