# SPDX-License-Identifier: GPL-3.0-only
import hashlib
from pathlib import Path
import socket
import ssl
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import types

from passthrough.audio import AudioBridge
from passthrough.identity import Identity
from passthrough.protocol import MAGIC, BLOCK_BYTES, read_exact, read_frame, send_frame
from passthrough.server import RelayServer


class FakeAudio(AudioBridge):
    def __init__(self):
        super().__init__()
        self.received = []
        self.started = False

    def start(self):
        self.started = True

    def play_frame(self, pcm):
        self.received.append(pcm)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='passthrough-desktop-test-')
        self.identity = Identity(self.temp.name)
        self.audios = []
        def factory():
            audio = FakeAudio()
            self.audios.append(audio)
            return audio
        self.server = RelayServer(self.identity, factory)
        self.server.start(port=0)
        self.assertTrue(self.server.ready.wait(5))
        self.assertIsNone(self.server.error)

    def tearDown(self):
        self.server.stop()
        self.assertTrue(self.server.join())
        self.temp.cleanup()

    def connect(self, token=None, fragmented=False):
        context = ssl.create_default_context(cafile=str(self.identity.cert))
        peer = context.wrap_socket(socket.socket(), server_hostname='localhost')
        peer.settimeout(3)
        peer.connect(self.server.address)
        self.assertEqual(hashlib.sha256(peer.getpeercert(binary_form=True)).hexdigest(), self.identity.fingerprint)
        header = MAGIC+(self.identity.token if token is None else token).encode()
        if fragmented:
            for i in range(0, len(header), 3):
                peer.sendall(header[i:i+3])
        else:
            peer.sendall(header)
        return peer

    def test_duplex_and_fragmented_handshake(self):
        with self.connect(fragmented=True) as peer:
            self.assertEqual(read_exact(peer, 4), b'OKAY')
            self.assertEqual(len(read_frame(peer)), BLOCK_BYTES)
            payload = b'\0\x80\xff\x7f'
            wire = struct.pack('!I', len(payload))+payload
            for byte in wire:
                peer.sendall(bytes([byte]))
            deadline = time.monotonic()+2
            while not self.audios[0].received and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertEqual(self.audios[0].received, [payload])

    def test_playback_only_without_uplink_keeps_streaming(self):
        with self.connect() as peer:
            self.assertEqual(read_exact(peer, 4), b'OKAY')
            time.sleep(0.7)  # no phone microphone frames: downlink must stay active
            for _ in range(4):
                self.assertEqual(len(read_frame(peer)), BLOCK_BYTES)

    def test_android_style_separate_header_tls_records_are_drained(self):
        # Android's DataOutputStream can writeInt as four one-byte writes.
        # Each send below deliberately creates a separate TLS record.
        with self.connect() as peer:
            peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.assertEqual(read_exact(peer, 4), b'OKAY')
            pcm = bytes(BLOCK_BYTES)
            for _ in range(30):
                for byte in struct.pack('!I', len(pcm)):
                    peer.sendall(bytes([byte]))
                peer.sendall(pcm)
            deadline = time.monotonic()+1.2
            while len(self.audios[0].received)<30 and time.monotonic()<deadline:
                time.sleep(0.005)
            self.assertEqual(len(self.audios[0].received), 30)

    def test_invalid_token_opens_no_audio(self):
        with self.connect(token='0'*64) as peer:
            self.assertEqual(peer.recv(4), b'')
        self.assertEqual(self.audios, [])

    def test_invalid_lengths_close_session(self):
        for length in (0, 1, 12802, 0xffffffff):
            with self.connect() as peer:
                self.assertEqual(read_exact(peer, 4), b'OKAY')
                peer.sendall(struct.pack('!I', length))
                while peer.recv(16384):
                    pass

    def test_stop_closes_connected_phone(self):
        with self.connect() as peer:
            self.assertEqual(read_exact(peer, 4), b'OKAY')
            self.server.stop()
            self.assertTrue(self.server.join())

    def test_identity_reused_token_changes(self):
        second = Identity(self.temp.name)
        self.assertEqual(second.fingerprint, self.identity.fingerprint)
        self.assertNotEqual(second.token, self.identity.token)
        self.assertEqual((Path(self.temp.name)/'private-key.pem').stat().st_mode & 0o777, 0o600)

    def test_audio_queues_are_bounded(self):
        audio = AudioBridge('sd:0', 'sd:0')
        for _ in range(20):
            audio._capture(bytes(BLOCK_BYTES))
        self.assertEqual(audio.outgoing.qsize(), 8)
        self.assertGreater(audio.dropped, 0)
        for _ in range(8):
            audio.play_frame(bytes(BLOCK_BYTES))
        with self.assertRaises(OSError):
            audio.play_frame(bytes(BLOCK_BYTES))
        audio.close()

    def test_stop_during_audio_setup_closes_all_streams(self):
        entered, release = threading.Event(), threading.Event()
        streams = []
        class Stream:
            def __init__(self, **kwargs):
                streams.append(self)
                self.closed = False
            def start(self):
                if len(streams) == 1:
                    entered.set()
                    self.assert_released = release.wait(2)
            def abort(self):
                pass
            def close(self):
                self.closed = True
        audio = AudioBridge('sd:0', 'sd:0')
        with patch.dict('sys.modules', {'sounddevice': types.SimpleNamespace(RawInputStream=Stream, RawOutputStream=Stream)}):
            setup = threading.Thread(target=audio.start)
            setup.start()
            self.assertTrue(entered.wait(1))
            stopping = threading.Thread(target=audio.close)
            stopping.start()
            release.set()
            setup.join(2)
            stopping.join(2)
        self.assertFalse(setup.is_alive())
        self.assertFalse(stopping.is_alive())
        self.assertTrue(streams)
        self.assertTrue(all(stream.closed for stream in streams))

    def test_process_exit_race_does_not_skip_stream_cleanup(self):
        class Process:
            def poll(self): return None
            def terminate(self): raise ProcessLookupError()
            def wait(self, timeout=None): return 0
        class Stream:
            closed = False
            def abort(self): pass
            def close(self): self.closed = True
        audio = AudioBridge()
        stream = Stream()
        audio.processes.append(Process())
        audio.streams.append(stream)
        audio.close()
        self.assertTrue(stream.closed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
