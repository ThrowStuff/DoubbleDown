# SPDX-License-Identifier: GPL-3.0-only
"""Explicit audio routes. Listing never opens capture/playback or changes defaults."""
from dataclasses import dataclass
import json
import queue
import subprocess
import sys
import threading
import time

from .protocol import BLOCK_BYTES, RATE, SAMPLES


@dataclass(frozen=True)
class Device:
    key: str
    name: str


def list_devices():
    inputs = [Device('silence', 'Silence · connection test (no capture)')]
    outputs = [Device('discard', 'Discard · connection test (no playback)')]
    if sys.platform.startswith('linux'):
        try:
            data = json.loads(subprocess.check_output(['pw-dump'], timeout=5, stderr=subprocess.DEVNULL))
            for obj in data:
                props = obj.get('info', {}).get('props', {})
                kind = props.get('media.class', '')
                serial = props.get('object.serial')
                if serial is None:
                    continue
                name = props.get('node.description', props.get('node.name', str(serial)))
                if kind == 'Audio/Sink':
                    inputs.append(Device(f'pw-monitor:{serial}', f'{name} · computer playback monitor'))
                    outputs.append(Device(f'pw-output:{serial}', name))
                elif kind in ('Audio/Source', 'Audio/Source/Virtual'):
                    inputs.append(Device(f'pw-input:{serial}', name))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    try:
        import sounddevice as sd
        for index, info in enumerate(sd.query_devices()):
            name = info['name']
            if info['max_input_channels'] > 0:
                inputs.append(Device(f'sd:{index}', name+' · audio input'))
            if info['max_output_channels'] > 0:
                outputs.append(Device(f'sd:{index}', name+' · audio output'))
    except Exception:
        # Keep the diagnostic-only mode available when no audio service is present.
        pass
    if sys.platform == 'win32':
        try:
            import pyaudiowpatch as pa
            with pa.PyAudio() as audio:
                for info in audio.get_loopback_device_info_generator():
                    inputs.append(Device(f'wasapi:{int(info["index"])}', info['name']+' · Windows playback monitor'))
        except (ImportError, OSError):
            pass
    return inputs, outputs


class AudioBridge:
    def __init__(self, capture='silence', playback='discard'):
        self.capture = capture
        self.playback = playback
        self.stop = threading.Event()
        self.incoming = queue.Queue(maxsize=8)
        self.outgoing = queue.Queue(maxsize=8)
        self.streams = []
        self.processes = []
        self.threads = []
        self.failure = None
        self.dropped = 0
        self.closed = False
        self.close_lock = threading.RLock()

    def _capture(self, pcm):
        if self.stop.is_set():
            return
        try:
            self.outgoing.put_nowait(pcm)
        except queue.Full:
            try:
                self.outgoing.get_nowait()
            except queue.Empty:
                pass
            self.dropped += 1
            try:
                self.outgoing.put_nowait(pcm)
            except queue.Full:
                pass

    def start(self):
        with self.close_lock:
            if self.closed or self.stop.is_set():
                raise EOFError('audio setup canceled')
            self._start()

    def _start(self):
        try:
            if self.capture.startswith('pw-'):
                self._pipewire_capture()
            elif self.capture.startswith('sd:'):
                import sounddevice as sd
                def capture(data, frames, timing, status):
                    self._capture(bytes(data))
                stream = sd.RawInputStream(device=int(self.capture.split(':')[1]), samplerate=RATE,
                                           channels=1, dtype='int16', blocksize=SAMPLES,
                                           callback=capture, latency='low')
                self.streams.append(stream)
                stream.start()
            elif self.capture.startswith('wasapi:'):
                self._wasapi_capture()
            elif self.capture != 'silence':
                raise ValueError('unknown capture device')
            if self.playback.startswith('pw-output:'):
                self._pipewire_playback()
            elif self.playback.startswith('sd:'):
                import sounddevice as sd
                pending = bytearray()
                def playback(data, frames, timing, status):
                    count = len(data)
                    while len(pending) < count:
                        try:
                            pending.extend(self.incoming.get_nowait())
                        except queue.Empty:
                            break
                    chunk = bytes(pending[:count])
                    del pending[:count]
                    data[:] = chunk + bytes(count-len(chunk))
                stream = sd.RawOutputStream(device=int(self.playback.split(':')[1]), samplerate=RATE,
                                            channels=1, dtype='int16', blocksize=SAMPLES,
                                            callback=playback, latency='low')
                self.streams.append(stream)
                stream.start()
            elif self.playback != 'discard':
                raise ValueError('unknown playback device')
        except Exception:
            self.close()
            raise

    def _spawn(self, command, reader):
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL if reader else subprocess.PIPE,
                                   stdout=subprocess.PIPE if reader else subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        self.processes.append(process)
        return process

    def _thread(self, action):
        def guarded():
            try:
                action()
            except Exception as error:
                if not self.stop.is_set():
                    self.failure = str(error)
                    self.stop.set()
        worker = threading.Thread(target=guarded, daemon=True)
        self.threads.append(worker)
        worker.start()

    def _pipewire_capture(self):
        kind, serial = self.capture.split(':', 1)
        command = ['pw-cat', '--record', '--raw', '--rate', str(RATE), '--channels', '1',
                   '--format', 's16', '--latency', '20ms', '--target', serial]
        props = {'node.dont-fallback': True, 'node.dont-reconnect': True, 'node.dont-move': True}
        if kind == 'pw-monitor':
            props['stream.capture.sink'] = True
        command += ['--properties', json.dumps(props)]
        process = self._spawn(command+['-'], True)
        def read():
            while not self.stop.is_set():
                pcm = process.stdout.read(BLOCK_BYTES)
                if len(pcm) != BLOCK_BYTES:
                    raise OSError('PipeWire capture stopped; select an available device')
                self._capture(pcm)
        self._thread(read)

    def _pipewire_playback(self):
        serial = self.playback.split(':', 1)[1]
        process = self._spawn(['pw-cat', '--playback', '--raw', '--rate', str(RATE), '--channels', '1',
                               '--format', 's16', '--latency', '20ms', '--target', serial,
                               '--properties', '{"node.dont-fallback":true,"node.dont-reconnect":true,"node.dont-move":true}', '-'], False)
        def write():
            while not self.stop.is_set():
                try:
                    pcm = self.incoming.get(timeout=0.1)
                except queue.Empty:
                    continue
                process.stdin.write(pcm)
                process.stdin.flush()
        self._thread(write)

    def _wasapi_capture(self):
        import pyaudiowpatch as pa
        import numpy as np
        import soxr
        audio = pa.PyAudio()
        self.streams.append(audio)
        info = audio.get_device_info_by_index(int(self.capture.split(':')[1]))
        channels = int(info['maxInputChannels'])
        rate = int(info['defaultSampleRate'])
        if channels < 1 or not info.get('isLoopbackDevice'):
            raise ValueError('Select an actual Windows loopback endpoint')
        resampler = soxr.ResampleStream(rate, RATE, 1, dtype='float32')
        pending = bytearray()
        def capture(data, frames, timing, status):
            try:
                samples = np.frombuffer(data, dtype='<f4').reshape(-1, channels).mean(axis=1)
                converted = resampler.resample_chunk(samples)
                pending.extend((np.clip(converted, -1, 1)*32767).astype('<i2').tobytes())
                while len(pending) >= BLOCK_BYTES:
                    self._capture(bytes(pending[:BLOCK_BYTES]))
                    del pending[:BLOCK_BYTES]
                return (None, pa.paContinue)
            except Exception as error:
                self.failure = str(error)
                return (None, pa.paAbort)
        stream = audio.open(format=pa.paFloat32, channels=channels, rate=rate, input=True,
                            input_device_index=int(info['index']), frames_per_buffer=max(1, rate//50),
                            stream_callback=capture)
        self.streams.append(stream)

    def capture_frame(self):
        if self.failure:
            raise OSError(self.failure)
        if self.capture == 'silence':
            if self.stop.wait(0.02):
                raise EOFError('audio stopped')
            return bytes(BLOCK_BYTES)
        try:
            return self.outgoing.get(timeout=0.5)
        except queue.Empty:
            raise OSError(self.failure or 'No PCM from the selected computer input') from None

    def play_frame(self, pcm):
        if self.failure:
            raise OSError(self.failure)
        if self.playback != 'discard':
            try:
                self.incoming.put_nowait(pcm)
            except queue.Full:
                raise OSError('Microphone playback queue overflow; check selected output') from None

    def close(self):
        with self.close_lock:
            if self.closed:
                return
            self.closed = True
            self.stop.set()
            for process in self.processes:
                try:
                    if process.poll() is None:
                        process.terminate()
                except OSError:
                    pass
            for stream in reversed(self.streams):
                try:
                    if hasattr(stream, 'abort'):
                        stream.abort()
                    elif hasattr(stream, 'stop_stream'):
                        stream.stop_stream()
                    if hasattr(stream, 'close'):
                        stream.close()
                    elif hasattr(stream, 'terminate'):
                        stream.terminate()
                except Exception:
                    pass
            for process in self.processes:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                        process.wait(timeout=1)
                    except (OSError, subprocess.SubprocessError):
                        pass
                except OSError:
                    pass
            for worker in self.threads:
                if worker is not threading.current_thread():
                    worker.join(1)
