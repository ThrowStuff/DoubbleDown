# SPDX-License-Identifier: GPL-3.0-only
import socket
import struct
import time

MAGIC = b'PTHRU001'
RATE = 32000
SAMPLES = 640
BLOCK_BYTES = SAMPLES * 2
MAX_BYTES = 12800


def read_exact(peer, count, stop=None, deadline=None, clean_eof=False):
    result = bytearray()
    while len(result) < count:
        if stop is not None and stop.is_set():
            raise EOFError('session stopped')
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError('peer timed out')
        try:
            chunk = peer.recv(count-len(result))
        except socket.timeout:
            continue
        if not chunk:
            if not result and clean_eof:
                return None
            raise EOFError('peer disconnected mid-frame')
        result.extend(chunk)
    return bytes(result)


def read_frame(peer, stop=None):
    header = read_exact(peer, 4, stop, clean_eof=True)
    if header is None:
        return None
    count = struct.unpack('!I', header)[0]
    if not 0 < count <= MAX_BYTES or count % 2:
        raise ValueError('invalid PCM frame length')
    return read_exact(peer, count, stop, deadline=time.monotonic()+5)


def send_frame(peer, pcm):
    if not 0 < len(pcm) <= MAX_BYTES or len(pcm) % 2:
        raise ValueError('invalid PCM frame length')
    peer.sendall(struct.pack('!I', len(pcm))+pcm)
