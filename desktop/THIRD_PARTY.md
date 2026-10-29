# Dependency attribution

PassThrough's project-authored desktop code is GNU GPLv3 only. No code from surveyed relay/control applications was copied.

Runtime libraries retain their licenses:

- Qt for Python / PySide6 and Shiboken: LGPLv3/GPL/commercial options; use under compatible open-source terms and retain distributed notices. https://doc.qt.io/qtforpython-6/licenses.html
- sounddevice: MIT; PortAudio: MIT-style license. https://github.com/spatialaudio/python-sounddevice / https://github.com/PortAudio/portaudio
- cryptography: Apache2.0 or BSD3-Clause. https://github.com/pyca/cryptography
- CFFI: MIT. https://foss.heptapod.net/pypy/cffi
- Windows PyAudioWPatch/PyAudio: MIT; bundled PortAudio retains its license. https://github.com/s0d3s/PyAudioWPatch
- NumPy: BSD3-Clause. https://numpy.org/doc/stable/license.html
- python-soxr: LGPL2.1-or-later; libsoxr LGPL2.1. https://github.com/dofuuz/python-soxr
- PyInstaller: GPL2.0-or-later with bootloader exception. https://pyinstaller.org/en/stable/license.html
- Python and OpenSSL retain their respective licenses.

PipeWire/PulseAudio tools are invoked as separately installed system programs. Windows virtual audio drivers are not bundled and require their own authorized installation/license. Packaged release must include actual installed dependency license texts/metadata; this source summary alone is not a substitute for those notices.
