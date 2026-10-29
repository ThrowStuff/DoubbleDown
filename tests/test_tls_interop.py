# SPDX-License-Identifier: GPL-3.0-only
"""Offline protocol tests against desktop TLS; no audio/device access.

Set PASSTHROUGH_JDK to a JDK17+ directory, then run python3 tests/test_tls_interop.py.
This checks desktop-JVM behavior, not Android's TLS provider or audio routes.
"""
import hashlib
import os
from pathlib import Path
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
JDK = Path(os.environ['PASSTHROUGH_JDK'])
TOKEN = 'a' * 64  # deterministic test token only


def exact(stream, count):
    data = b''
    while len(data) < count:
        part = stream.recv(count - len(data))
        if not part:
            raise EOFError('truncated stream')
        data += part
    return data


class Interop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='passthrough-tls-test-')
        cls.path = Path(cls.temp.name)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(cls.path/'key.pem'), '-out', str(cls.path/'cert.pem'),
                        '-days', '1', '-subj', '/CN=PassThrough test'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        der = ssl.PEM_cert_to_DER_cert((cls.path/'cert.pem').read_text())
        cls.pin = hashlib.sha256(der).hexdigest()
        java = ROOT/'desktop-link/src/main/java/org/openhearing/desktoplink'
        subprocess.run([str(JDK/'bin/javac'), '-d', str(cls.path),
                        str(java/'PcmFrames.java'), str(java/'DesktopLinkSession.java'),
                        str(ROOT/'tests/TlsProbe.java')], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def session(self, pin=None, token=TOKEN, malformed=False):
        events = []
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(10)
        port = listener.getsockname()[1]
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.path/'cert.pem', self.path/'key.pem')

        def serve():
            try:
                with listener.accept()[0] as raw:
                    raw.settimeout(5)
                    with context.wrap_socket(raw, server_side=True) as peer:
                        handshake = exact(peer, 72)
                        events.append(('handshake', handshake))
                        if handshake != b'PTHRU001' + TOKEN.encode():
                            peer.sendall(b'NOPE')
                            return
                        peer.sendall(b'OKAY')
                        if malformed:
                            peer.sendall(struct.pack('!I', 0x7fffffff))
                        else:
                            peer.sendall(struct.pack('!I', 4) + b'\x00\x80\xff\x7f')
                            events.append(('frame', exact(peer, 8)))
            except (ssl.SSLError, EOFError, OSError) as error:
                events.append(('closed', type(error).__name__))
            finally:
                listener.close()

        thread = threading.Thread(target=serve)
        thread.start()
        result = subprocess.run([str(JDK/'bin/java'), '-cp', str(self.path),
                                 'org.openhearing.desktoplink.TlsProbe', str(port),
                                 self.pin if pin is None else pin, token],
                                capture_output=True, text=True, timeout=15)
        thread.join(10)
        self.assertFalse(thread.is_alive(), 'server did not terminate')
        return result, events

    def test_duplex_frame(self):
        result, events = self.session()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(('frame', b'\0\0\0\x04\x00\x80\xff\x7f'), events)

    def test_bad_pin_sends_no_application_data(self):
        result, events = self.session(pin='0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(kind == 'handshake' for kind, _ in events))

    def test_bad_token_rejected(self):
        result, events = self.session(token='b' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(kind == 'frame' for kind, _ in events))

    def test_oversize_frame_rejected(self):
        result, _ = self.session(malformed=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Invalid PCM frame length', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
