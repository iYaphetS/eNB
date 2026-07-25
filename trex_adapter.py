#!/usr/bin/env python3
import argparse
import json
import os
import zlib
from pathlib import Path


class BearerState:
    def __init__(self, shard_count=1):
        if shard_count < 1:
            raise ValueError('shard count must be positive')
        self.shard_count = shard_count
        self.active = {}
        self._shards = [dict() for _ in range(shard_count)]
        self.event_count = 0
        self.sequence_gaps = 0
        self.last_sequence = None
        self.run_id = None
        self.restarts = 0

    def apply(self, event):
        event_type = event['event']
        if event_type not in ('bearer-up', 'bearer-update', 'bearer-down'):
            raise ValueError(f'unknown bearer event: {event_type}')
        key = (str(event['imsi']), int(event['bearer_id']))
        record = None
        if event_type in ('bearer-up', 'bearer-update'):
            record = {
                field: event[field] for field in (
                    'imsi', 'ue_ip', 'upf_ip', 'enb_gtpu_ip',
                    'uplink_teid', 'downlink_teid', 'bearer_id',
                )
            }
        run_id = event.get('run_id')
        sequence = event.get('sequence')
        if sequence is not None:
            sequence = int(sequence)

        restarted = bool(run_id and self.run_id and run_id != self.run_id)
        if restarted:
            self.active.clear()
            for shard in self._shards:
                shard.clear()
            self.last_sequence = None
            self.restarts += 1
        if run_id:
            self.run_id = str(run_id)
        self.event_count += 1
        if sequence is not None:
            if self.last_sequence is not None and sequence > self.last_sequence + 1:
                self.sequence_gaps += sequence - self.last_sequence - 1
            self.last_sequence = max(sequence, self.last_sequence or sequence)
        shard_index = _shard_for(key[0], self.shard_count)
        if event_type == 'bearer-down':
            self.active.pop(key, None)
            self._shards[shard_index].pop(key, None)
        else:
            self.active[key] = record
            self._shards[shard_index][key] = record
        return {
            'restarted': restarted,
            'shard_index': shard_index,
        }

    def sessions(self, shard_count=1, shard_index=0):
        if shard_count < 1 or not 0 <= shard_index < shard_count:
            raise ValueError('invalid shard count or shard index')
        if shard_count == self.shard_count:
            source = self._shards[shard_index]
            keys = source
        else:
            source = self.active
            keys = self.active
        if shard_count > 1 and shard_count != self.shard_count:
            keys = [key for key in keys
                    if _shard_for(key[0], shard_count) == shard_index]
        return [source[key] for key in sorted(keys)]

    def summary(self):
        return {
            'processed': self.event_count,
            'last_sequence': self.last_sequence,
            'sequence_gaps': self.sequence_gaps,
            'run_id': self.run_id,
            'restarts': self.restarts,
        }


def replay_events(events):
    state = BearerState()
    for event in events:
        state.apply(event)
    return state.sessions(), state.summary()


def active_bearers(events):
    return replay_events(events)[0]


def read_events(path):
    with Path(path).open(encoding='utf-8') as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                if not line.endswith('\n'):
                    return
                raise ValueError(f'invalid JSON on line {line_number}: {error}') from error


def _shard_for(imsi, shard_count):
    return zlib.crc32(str(imsi).encode('ascii')) % shard_count


def build_manifest(events, uplink_pps=1000, downlink_pps=1000, payload_size=64,
                   shard_count=1, shard_index=0):
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError('invalid shard count or shard index')
    sessions, event_summary = replay_events(events)
    return build_manifest_from_sessions(
        sessions, event_summary, uplink_pps, downlink_pps, payload_size,
        shard_count, shard_index)


def build_manifest_from_state(state, uplink_pps=1000, downlink_pps=1000,
                              payload_size=64, shard_count=1, shard_index=0):
    return build_manifest_from_sessions(
        state.sessions(shard_count, shard_index), state.summary(), uplink_pps,
        downlink_pps, payload_size, 1, 0,
        shard_metadata={'count': shard_count, 'index': shard_index})


def build_manifest_from_sessions(sessions, event_summary, uplink_pps,
                                 downlink_pps, payload_size, shard_count,
                                 shard_index, shard_metadata=None):
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError('invalid shard count or shard index')
    if shard_count > 1:
        sessions = [session for session in sessions
                    if _shard_for(session['imsi'], shard_count) == shard_index]
    return {
        'schema_version': 2,
        'generator': 'eNB TRex adapter',
        'shard': shard_metadata or {'count': shard_count, 'index': shard_index},
        'events': event_summary,
        'traffic': {
            'uplink_pps_per_bearer': uplink_pps,
            'downlink_pps_per_bearer': downlink_pps,
            'inner_payload_size': payload_size,
        },
        'sessions': sessions,
    }


def write_manifest(path, manifest, compact=False):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    if compact:
        encoded = json.dumps(manifest, separators=(',', ':'), sort_keys=True)
    else:
        encoded = json.dumps(manifest, indent=2, sort_keys=True)
    temporary.write_text(encoded + '\n', encoding='utf-8')
    os.replace(temporary, path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Build an active TRex GTP-U session manifest from bearer events')
    parser.add_argument('--events', required=True, help='bearer event JSONL file')
    parser.add_argument('--output', required=True, help='output manifest JSON file')
    parser.add_argument('--uplink-pps', type=int, default=1000)
    parser.add_argument('--downlink-pps', type=int, default=1000)
    parser.add_argument('--payload-size', type=int, default=64)
    parser.add_argument('--shards', type=int, default=1,
                        help='number of deterministic IMSI shards')
    parser.add_argument('--shard-index', type=int, default=0)
    parser.add_argument('--compact', action='store_true',
                        help='write compact JSON for large manifests')
    args = parser.parse_args(argv)
    for name in ('uplink_pps', 'downlink_pps', 'payload_size'):
        if getattr(args, name) < 0:
            parser.error(f'--{name.replace("_", "-")} must be non-negative')
    if args.payload_size < 28:
        parser.error('--payload-size must be at least 28')
    if args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error('--shard-index must be between 0 and --shards - 1')
    try:
        manifest = build_manifest(
            read_events(args.events), args.uplink_pps, args.downlink_pps,
            args.payload_size, args.shards, args.shard_index)
        write_manifest(args.output, manifest, args.compact)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
