# SPDX-License-Identifier: GPL-3.0-only
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from passthrough.audio import AudioBridge
from passthrough.identity import Identity
from passthrough.server import RelayServer


@unittest.skipUnless(os.environ.get('PASSTHROUGH_JDK'), 'Set PASSTHROUGH_JDK for Android-source JVM interoperability')
class JavaInterop(unittest.TestCase):
    def test_sustained_android_duplex_rate(self):
        root = Path(__file__).resolve().parents[2]
        jdk = Path(os.environ['PASSTHROUGH_JDK'])
        class RateAudio(AudioBridge):
            received = 0
            def start(self):
                pass
            def play_frame(self, pcm):
                if len(pcm) != 1280:
                    raise ValueError('unexpected PCM size')
                self.received += 1
        with tempfile.TemporaryDirectory() as directory:
            java = root/'app/src/main/java/org/openhearing/app'
            subprocess.run([str(jdk/'bin/javac'), '-d', directory,
                            str(java/'FrameCodec.java'), str(java/'PinnedConnection.java'),
                            str(root/'tests/TlsThroughputProbe.java')], check=True)
            identity = Identity(Path(directory)/'identity')
            audio = RateAudio()
            server = RelayServer(identity, lambda: audio)
            server.start(port=0)
            self.assertTrue(server.ready.wait(5))
            try:
                result = subprocess.run([str(jdk/'bin/java'), '-cp', directory,
                                         'org.openhearing.app.TlsThroughputProbe', str(server.address[1]),
                                         identity.fingerprint, identity.token],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertGreaterEqual(audio.received, 180,
                                        f'Only {audio.received}/200 uplink frames arrived in4.7seconds')
                self.assertGreaterEqual(int(result.stdout.strip().split('=')[1]), 180)
            finally:
                server.stop()
                self.assertTrue(server.join())

    def test_android_connection_source_against_real_desktop_server(self):
        root = Path(__file__).resolve().parents[2]
        jdk = Path(os.environ['PASSTHROUGH_JDK'])
        class ProbeAudio(AudioBridge):
            def start(self):
                self.received = []
            def capture_frame(self):
                if self.stop.wait(0.02):
                    raise EOFError('stopped')
                return b'\x00\x80\xff\x7f'
            def play_frame(self, pcm):
                self.received.append(pcm)
        with tempfile.TemporaryDirectory() as directory:
            java = root/'app/src/main/java/org/openhearing/app'
            subprocess.run([str(jdk/'bin/javac'), '-d', directory,
                            str(java/'FrameCodec.java'), str(java/'PinnedConnection.java'),
                            str(root/'tests/TlsProbe.java')], check=True)
            identity = Identity(Path(directory)/'identity')
            audio = ProbeAudio()
            server = RelayServer(identity, lambda: audio)
            server.start(port=0)
            self.assertTrue(server.ready.wait(5))
            try:
                result = subprocess.run([str(jdk/'bin/java'), '-cp', directory,
                                         'org.openhearing.app.TlsProbe', str(server.address[1]),
                                         identity.fingerprint, identity.token],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                deadline = time.monotonic()+1
                while not audio.received and time.monotonic()<deadline:
                    time.sleep(0.01)
                self.assertEqual(audio.received, [b'\x00\x80\xff\x7f'])
            finally:
                server.stop()
                self.assertTrue(server.join())
