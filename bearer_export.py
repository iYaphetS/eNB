import json
import socket
import threading
import time
from pathlib import Path


def _ipv4(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return socket.inet_ntoa(value)
    if isinstance(value, int):
        return socket.inet_ntoa(value.to_bytes(4, byteorder='big'))
    return str(value)


def _teid(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return int.from_bytes(value, byteorder='big')
    return int(value)


def build_bearer_records(session):
    """Return complete bearer records from the simulator's parallel lists."""
    records = []
    rab_ids = session.get('RAB-ID', [])
    for position, bearer_id in enumerate(rab_ids):
        try:
            upf_ip = _ipv4(session.get('SGW-GTP-ADDRESS', [])[position])
            uplink_teid = _teid(session.get('SGW-TEID', [])[position])
            downlink_teid = _teid(session.get('ENB-TEID', [])[position])
        except (IndexError, TypeError, ValueError, OSError):
            continue
        ue_ip = session.get('PDN-ADDRESS-IPV4')
        enb_gtpu_ip = _ipv4(session.get('ENB-GTP-ADDRESS-INT'))
        if not all((ue_ip, upf_ip, enb_gtpu_ip)):
            continue
        if uplink_teid is None or downlink_teid is None:
            continue
        records.append({
            'imsi': str(session.get('IMSI', '')),
            'ue_ip': str(ue_ip),
            'upf_ip': upf_ip,
            'enb_gtpu_ip': enb_gtpu_ip,
            'uplink_teid': uplink_teid,
            'downlink_teid': downlink_teid,
            'bearer_id': int(bearer_id),
        })
    return records


class BearerEventPublisher:
    """Publish bearer lifecycle events to JSONL or a Unix datagram socket."""

    def __init__(self, destination=None, clock=time.time):
        self.destination = destination
        self.clock = clock
        self._active = {}
        self._by_imsi = {}
        self._lock = threading.Lock()
        self._output = None
        self._sender = None
        self._opened_once = False

    @property
    def enabled(self):
        return bool(self.destination)

    def sync(self, session):
        if not self.enabled:
            return
        imsi = str(session.get('IMSI', ''))
        current = {
            (record['imsi'], record['bearer_id']): record
            for record in build_bearer_records(session)
        }
        with self._lock:
            session_keys = self._by_imsi.setdefault(imsi, set())
            previous = {key: self._active[key] for key in session_keys}
            for key, record in current.items():
                old = previous.get(key)
                if old is None:
                    self._publish('bearer-up', record)
                elif old != record:
                    self._publish('bearer-update', record)
                self._active[key] = record
                session_keys.add(key)
            for key, record in previous.items():
                if key not in current:
                    self._publish('bearer-down', record)
                    self._active.pop(key, None)
                    session_keys.discard(key)
            if not session_keys:
                self._by_imsi.pop(imsi, None)

    def remove_session(self, session):
        if not self.enabled:
            return
        imsi = str(session.get('IMSI', ''))
        with self._lock:
            for key in self._by_imsi.pop(imsi, set()):
                self._publish('bearer-down', self._active.pop(key))

    def close(self):
        with self._lock:
            if self._output is not None:
                self._output.close()
                self._output = None
            if self._sender is not None:
                self._sender.close()
                self._sender = None

    def _publish(self, event, record):
        payload = dict(record, event=event, timestamp=self.clock())
        encoded = json.dumps(payload, sort_keys=True) + '\n'
        if str(self.destination).startswith('unix:'):
            target = str(self.destination)[5:]
            try:
                if self._sender is None:
                    self._sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                    self._sender.setblocking(False)
                self._sender.sendto(encoded.rstrip().encode('utf-8'), target)
            except (BlockingIOError, FileNotFoundError, OSError):
                pass
            return
        path = Path(self.destination)
        try:
            if self._output is None:
                path.parent.mkdir(parents=True, exist_ok=True)
                mode = 'a' if self._opened_once else 'w'
                self._output = path.open(mode, encoding='utf-8', buffering=1)
                self._opened_once = True
            self._output.write(encoded)
        except OSError:
            if self._output is not None:
                self._output.close()
                self._output = None
