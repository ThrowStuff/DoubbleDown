# SPDX-License-Identifier: GPL-3.0-only
import hmac
import socket
import ssl
import threading
import time

from .protocol import MAGIC, read_exact, read_frame, send_frame


class RelayServer:
    """One authenticated phone, bounded audio backend, explicit start/stop."""
    def __init__(self, identity, audio_factory, report=lambda message: None):
        self.identity = identity
        self.audio_factory = audio_factory
        self.report = report
        self.stop_event = threading.Event()
        self.thread = None
        self.listener = None
        self.peer = None
        self.audio = None
        self.address = None
        self.ready = threading.Event()
        self.error = None

    def start(self, host='127.0.0.1', port=49721):
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError('A relay is already running')
        self.stop_event.clear()
        self.ready.clear()
        self.error = None
        self.thread = threading.Thread(target=self._serve, args=(host, port), daemon=True)
        self.thread.start()

    def _serve(self, host, port):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            context.load_cert_chain(self.identity.cert, self.identity.key)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                self.listener = listener
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind((host, port))
                listener.listen(1)
                listener.settimeout(0.3)
                self.address = listener.getsockname()
                self.ready.set()
                self.report('Listening · waiting for your phone')
                while not self.stop_event.is_set():
                    try:
                        raw, _ = listener.accept()
                    except socket.timeout:
                        continue
                    self.peer = raw
                    try:
                        raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        raw.settimeout(3)
                        with context.wrap_socket(raw, server_side=True) as peer:
                            self.peer = peer
                            peer.settimeout(0.5)
                            handshake = read_exact(peer, 72, self.stop_event, time.monotonic()+5)
                            if not hmac.compare_digest(handshake, MAGIC+self.identity.token.encode('ascii')):
                                self.report('Connection rejected · session token mismatch')
                                continue
                            peer.sendall(b'OKAY')
                            self._session(peer)
                    except (OSError, EOFError, ValueError) as error:
                        if not self.stop_event.is_set():
                            self.report('Connection ended: '+str(error))
                    finally:
                        try:
                            raw.close()
                        except OSError:
                            pass
                        self.peer = None
                        if self.audio is not None:
                            self.audio.close()
                            self.audio = None
                self.report('Stopped')
        except Exception as error:
            self.error = str(error)
            self.report('Cannot start relay: '+str(error))
        finally:
            self.ready.set()
            self.listener = None

    def _session(self, peer):
        audio = self.audio_factory()
        self.audio = audio
        audio.start()
        import struct
        from .protocol import MAX_BYTES
        pending = bytearray()
        partial_since = None
        self.report('Connected · encrypted audio session')
        try:
            # One thread owns TLS reads and writes. A playback-only phone may send
            # no PCM; a short read timeout must never stop the outgoing stream.
            while not self.stop_event.is_set():
                pcm = audio.capture_frame()
                peer.settimeout(0.5)
                send_frame(peer, pcm)
                # Drain fragmented TLS records, rather than limiting each PCM
                # frame to one record per20ms downlink cycle. Bound work so an
                # aggressive sender cannot starve outgoing audio or Stop.
                receive_deadline = time.monotonic()+0.004
                received_bytes = 0
                ended = False
                while received_bytes < (MAX_BYTES+4)*8 and time.monotonic() < receive_deadline:
                    peer.settimeout(0.001)
                    try:
                        chunk = peer.recv(MAX_BYTES+4)
                    except socket.timeout:
                        break
                    if chunk == b'':
                        ended = True
                        break
                    received_bytes += len(chunk)
                    pending.extend(chunk)
                    while len(pending) >= 4:
                        count = struct.unpack('!I', pending[:4])[0]
                        if not 0 < count <= MAX_BYTES or count % 2:
                            raise ValueError('invalid PCM frame length')
                        if len(pending) < count+4:
                            break
                        audio.play_frame(bytes(pending[4:count+4]))
                        del pending[:count+4]
                    if not pending:
                        partial_since = None
                    elif partial_since is None:
                        partial_since = time.monotonic()
                if ended:
                    break
                if partial_since is not None and time.monotonic()-partial_since > 5:
                    raise TimeoutError('phone sent a truncated PCM frame')
        finally:
            audio.close()
            try:
                peer.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def stop(self):
        self.stop_event.set()
        if self.audio is not None:
            self.audio.stop.set()  # worker owns potentially blocking audio cleanup
        peer = self.peer
        if peer is not None:
            try:
                peer.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                peer.close()
            except OSError:
                pass

    def join(self, timeout=3):
        if self.thread is not None:
            self.thread.join(timeout)
        return self.thread is None or not self.thread.is_alive()
