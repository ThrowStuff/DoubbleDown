# SPDX-License-Identifier: GPL-3.0-only
"""Bounded, headless relay session for isolated integration tests."""
import argparse
import json
from pathlib import Path
import struct
import time

from .audio import AudioBridge
from .identity import Identity, private_write
from .server import RelayServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--identity-directory', type=Path, required=True)
    parser.add_argument('--setup-file', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=49721)
    parser.add_argument('--duration', type=int, default=180)
    parser.add_argument('--capture', default='silence')
    parser.add_argument('--playback', default='discard')
    parser.add_argument('--save-uplink-pcm', type=Path,
                        help='Explicit test recording: save bounded received PCM16LE mono32kHz, privately; never overwrite')
    parser.add_argument('--record-uplink-seconds', type=int, default=30,
                        help='Maximum recorded uplink duration, 1..180seconds (default30)')
    parser.add_argument('--quiet-clip-pcm', type=Path,
                        help='Play one PCM16LE mono32kHz test clip after1second, peak limited to103/32768')
    parser.add_argument('--reference-clip-pcm', type=Path,
                        help='Explicitly user-approved reference speech test, peak limited to9830/32768')
    options = parser.parse_args()
    if options.save_uplink_pcm and options.save_uplink_pcm.exists():
        parser.error('uplink recording destination already exists')
    if not 1 <= options.record_uplink_seconds <= 180:
        parser.error('record-uplink-seconds must be between1 and180')
    if not 1 <= options.duration <= 3600:
        parser.error('duration must be between1 and3600seconds')
    identity = Identity(options.identity_directory)
    if options.quiet_clip_pcm and options.reference_clip_pcm:
        parser.error('select only one test clip')
    clip_path = options.quiet_clip_pcm or options.reference_clip_pcm
    clip = clip_path.read_bytes() if clip_path else b''
    peak_limit = 9830 if options.reference_clip_pcm else 103
    if clip:
        if options.capture != 'silence' or len(clip)%2 or len(clip)>32000*2*5:
            parser.error('quiet clip requires silence capture and at most5seconds of PCM16mono')
        if max(abs(n[0]) for n in struct.iter_unpack('<h', clip))>peak_limit:
            parser.error('clip exceeds the selected digital peak limit')
    counters = {'downlink_frames': 0, 'uplink_frames': 0, 'uplink_peak': 0}
    uplink_recording = bytearray()
    class MeasuredAudio(AudioBridge):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.clip_position = 0
            self.lead_in = 50
        def capture_frame(self):
            result = super().capture_frame()
            counters['downlink_frames'] += 1
            if clip:
                if self.lead_in:
                    self.lead_in -= 1
                elif self.clip_position<len(clip):
                    part=clip[self.clip_position:self.clip_position+len(result)]
                    self.clip_position+=len(part)
                    result=part+bytes(len(result)-len(part))
            return result
        def play_frame(self, pcm):
            if options.save_uplink_pcm:
                remaining = 32000 * 2 * options.record_uplink_seconds - len(uplink_recording)
                uplink_recording.extend(pcm[:remaining])
            counters['uplink_frames'] += 1
            counters['uplink_peak'] = max(counters['uplink_peak'], max((abs(n[0]) for n in struct.iter_unpack('<h', pcm)), default=0))
            super().play_frame(pcm)
    def report(status):
        print(json.dumps({'status': status}), flush=True)
    server = RelayServer(identity, lambda: MeasuredAudio(options.capture, options.playback), report)
    server.start(options.host, options.port)
    if not server.ready.wait(5) or server.error:
        server.stop()
        raise RuntimeError(server.error or 'listener startup timeout')
    private_write(options.setup_file, json.dumps({'host': options.host, 'port': server.address[1],
                  'fingerprint': identity.fingerprint, 'token': identity.token}).encode())
    print(json.dumps({'ready': True, 'setup_file': str(options.setup_file)}), flush=True)
    try:
        deadline = time.monotonic()+options.duration
        while time.monotonic() < deadline and server.thread.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        if not server.join(5):
            raise RuntimeError('relay worker has not stopped')
        if options.save_uplink_pcm and uplink_recording:
            private_write(options.save_uplink_pcm, uplink_recording)
            counters['recorded_uplink_samples'] = len(uplink_recording) // 2
        print(json.dumps({'test_metrics': counters}), flush=True)


if __name__ == '__main__':
    main()
