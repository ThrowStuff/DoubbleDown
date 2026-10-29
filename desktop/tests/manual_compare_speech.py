# SPDX-License-Identifier: GPL-3.0-only
"""Offline diagnostic for authorized PCM test captures; requires optional numpy.

Inputs: PCM16LE mono32kHz. Reports a normalized waveform match, not an
automatic acoustic-origin verdict. Room acoustics, codec and noise processing
can reduce correlation; inspect control recordings before interpreting scores.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def compare(capture, reference):
    def reduced(raw):
        values = np.frombuffer(raw, dtype='<i2').astype(np.float64)
        return values[:len(values)//8*8].reshape(-1, 8).mean(axis=1)

    y, r = reduced(capture), reduced(reference)
    active = np.flatnonzero(np.abs(r) > max(1, np.max(np.abs(r))*0.01))
    if not len(active):
        raise ValueError('reference contains no usable signal')
    trim = int(active[0])
    r = r[trim:int(active[-1])+1]
    if len(y) < len(r) or len(r) < 400:
        raise ValueError('capture/reference too short for comparison')
    r = r-r.mean()
    n = len(r)
    size = 1 << (len(y)+n-2).bit_length()
    dots = np.fft.irfft(np.fft.rfft(y, size)*np.fft.rfft(r[::-1], size), size)[n-1:len(y)]
    sums = np.concatenate(([0.0], np.cumsum(y)))
    squares = np.concatenate(([0.0], np.cumsum(y*y)))
    energy = np.maximum(0, squares[n:]-squares[:-n]-(sums[n:]-sums[:-n])**2/n)
    denominator = np.sqrt(energy*np.dot(r, r))
    scores = np.divide(dots, denominator, out=np.zeros_like(dots), where=denominator>0)
    best = int(np.argmax(np.abs(scores)))
    return {'waveform_correlation': round(float(scores[best]), 5),
            'reference_start_in_capture_seconds': round((best-trim)/4000, 4),
            'compared_speech_seconds': round(n/4000, 4),
            'capture_seconds': len(capture)/64000,
            'interpretation': 'Diagnostic only; a known playback and verified route are also required.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('reference', type=Path)
    options = parser.parse_args()
    for path, limit in [(options.capture, 64000*180), (options.reference, 64000*5)]:
        if not 2 <= path.stat().st_size <= limit or path.stat().st_size % 2:
            parser.error('input must be bounded even-length PCM16LE mono32kHz')
    print(json.dumps(compare(options.capture.read_bytes(), options.reference.read_bytes())))


if __name__ == '__main__':
    main()
