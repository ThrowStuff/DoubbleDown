# SPDX-License-Identifier: GPL-3.0-only
"""Explicit Linux synthetic-audio test. Creates/removes one private null sink.

Never captures a real microphone or plays to a physical output. Not part of
automatic unittest discovery. Run only during an authorized local audio test.
"""
import json
import math
import os
import struct
import subprocess
import time
from passthrough.audio import AudioBridge
from passthrough.protocol import RATE, SAMPLES


def default(kind):
    return subprocess.check_output(['pactl', 'get-default-'+kind], timeout=5).decode().strip()


def main():
    before = {kind: default(kind) for kind in ('sink', 'source')}
    name = 'passthrough_test_'+str(os.getpid())
    module = None
    audio = None
    try:
        module = subprocess.check_output([
            'pactl', 'load-module', 'module-null-sink', 'sink_name='+name,
            'sink_properties=device.description=PassThrough_Private_Test priority.session=0 node.virtual=true'
        ], timeout=5).decode().strip()
        assert module.isdigit()
        for kind in before:
            if default(kind) in (name, name+'.monitor'):
                subprocess.run(['pactl', 'set-default-'+kind, before[kind]], check=True, timeout=5)
        data = json.loads(subprocess.check_output(['pw-dump'], timeout=5))
        nodes = [obj['info']['props'] for obj in data if obj.get('info',{}).get('props',{}).get('node.name')==name]
        assert len(nodes)==1, 'Private test sink not found'
        serial = nodes[0]['object.serial']
        audio = AudioBridge(f'pw-monitor:{serial}', f'pw-output:{serial}')
        audio.start()
        block = b''.join(struct.pack('<h', int(2000*math.sin(2*math.pi*440*i/RATE))) for i in range(SAMPLES))
        heard = False
        deadline = time.monotonic()+3
        while time.monotonic()<deadline:
            audio.play_frame(block)
            pcm = audio.capture_frame()
            if any(abs(sample[0])>200 for sample in struct.iter_unpack('<h', pcm)):
                heard=True
                break
        assert heard, 'Synthetic PCM did not pass through the explicit null-sink routes'
        assert all(default(kind)==before[kind] for kind in before), 'Default route changed'
        print('PASS: actual PipeWire synthetic PCM capture/playback on private null sink; defaults unchanged')
    finally:
        if audio is not None:
            audio.close()
        if module is not None:
            subprocess.run(['pactl','unload-module',module], timeout=5, check=True)
        for kind in before:
            if default(kind) in (name, name+'.monitor'):
                subprocess.run(['pactl','set-default-'+kind,before[kind]],timeout=5,check=True)


if __name__ == '__main__':
    main()
