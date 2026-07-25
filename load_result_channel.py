import json
import os
import socket
import time
import uuid
from pathlib import Path


class LoadResultPublisher:
    def __init__(self, socket_factory=socket.socket, clock=time.time, unix_family=None):
        self._socket_factory = socket_factory
        self._clock = clock
        self._unix_family = unix_family
        self._socket = None

    def publish(self, session, status):
        result_socket = session.get('LOAD-TEST-RESULT-SOCKET')
        run_id = session.get('LOAD-TEST-RUN-ID')
        imsi = session.get('IMSI')
        if not result_socket or not run_id or not imsi:
            return False

        if self._socket is None:
            unix_family = self._unix_family or getattr(socket, 'AF_UNIX', None)
            if unix_family is None:
                return False
            self._socket = self._socket_factory(unix_family, socket.SOCK_DGRAM)
            self._socket.setblocking(False)
        event = json.dumps({
            'run_id': run_id,
            'imsi': imsi,
            'status': status,
            'emitted_at': self._clock(),
        }).encode('utf-8')
        try:
            self._socket.sendto(event, result_socket)
        except OSError:
            return False
        return True


class LoadResultServer:
    def __init__(
            self,
            run_id=None,
            socket_dir='/tmp',
            socket_factory=socket.socket,
            unix_family=None):
        self.run_id = run_id or uuid.uuid4().hex
        self.path = str(Path(socket_dir) / f'enb-load-{os.getpid()}-{self.run_id[:8]}.sock')
        unix_family = unix_family or getattr(socket, 'AF_UNIX', None)
        if unix_family is None:
            raise RuntimeError('Unix domain sockets are required for load result events')
        self._socket = socket_factory(unix_family, socket.SOCK_DGRAM)

    def __enter__(self):
        self._socket.bind(self.path)
        self._socket.setblocking(False)
        return self

    def read(self):
        events = []
        while True:
            try:
                payload = self._socket.recv(65535)
            except BlockingIOError:
                break
            try:
                event = json.loads(payload.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if event.get('run_id') == self.run_id:
                events.append(event)
        return events

    def __exit__(self, exc_type, exc_value, traceback):
        self._socket.close()
        try:
            Path(self.path).unlink()
        except FileNotFoundError:
            pass
