# PassThrough desktop

Original GPL-3.0-only companion for the PassThrough Android app. Desktop targets: **Linux and Windows11**. Windows10 is outside official support. Linux is the first live-test target; Windows code/build recipes are not Windows hardware validation.

## Current implementation

Native Qt configuration UI; explicit Wi-Fi/USB connection selection, certificate fingerprint and session token, explicit audio input/output selectors, start/stop, temporary Linux virtual microphone setup and read-only endpoint enumeration. Bluetooth computer transport is visibly unavailable pending implementation.

TLS1.2+ server matches the Android prototype protocol. Private desktop identity persists in the local application data directory; token changes each launch. Verify/copy these values privately into the phone. No account/cloud service or automatic default-route changes. Normal relay use does not record audio. Listening starts only when requested; network bind defaults to loopback.

Initial audio format: mono32kHz PCM16LE. Linux uses explicit PipeWire nodes/monitor capture; PortAudio routes are also available. Windows loopback capture uses PyAudioWPatch with native-rate resampling via soxr; ordinary audio outputs use sounddevice. These Windows paths have not run on Windows yet.

## Run from source

Use Python3.12+ and a virtual environment:

```sh
python -m venv .venv
# Activate .venv using your platform's normal activation command.
python -m pip install -r requirements.txt
python -m passthrough
```

On Linux, system PipeWire tools (`pw-cat`, `pw-dump`, `pactl`) support the preferred routes. PortAudio must be installed for sounddevice. No global audio configuration is modified at startup. The packaged build is intended to include the libraries; PipeWire command-line tools remain a system dependency.

## Test sequence

1. First use Silence/Discard to verify only the encrypted connection. Start listening on desktop, configure its address/port/fingerprint/token on phone, then select a real hearing-device output and Start relay. Android still requires an available selected output; synthetic desktop silence is not a bilateral playback test.
2. For Wi-Fi select a LAN address shown by the desktop; bind0.0.0.0 only when intentionally accepting LAN connections. For USB debugging, target the correct phone with `adb -s <phone> reverse tcp:49721 tcp:49721`; keep loopback listener. USB tethering instead uses a network adapter address and listener bound there.
3. Select the computer's playback monitor for outgoing audio. Select a virtual microphone input/sink for incoming phone audio. On Linux, the Create virtual microphone button creates temporary modules only after confirmation and removes its own modules on exit. Windows requires a separately installed virtual audio driver such as VB-CABLE; select its input as this app's receive output and its output as the calling app's microphone. Driver licensing/install is separate and not bundled.
4. Confirm audible playback in both ears and independently prove the selected input comes from the aids, with the phone mic excluded. No route advertisement or GUI success establishes this. Test disconnect/focus loss and Stop before claiming reliability.

Live Pixel tests have confirmed audible ASHA playback and a nonzero LE Audio microphone uplink with Android verifying the selected recorder route. A known external speaker-clip match, bilateral microphone behavior, direct LAN/physical USB, and Windows runtime remain untested. See ../LIVE-TEST-2026-10-28.md. Red Bluetooth remains off following the authorized handover.

For an explicitly authorized microphone test, the source-only headless runner supports `--save-uplink-pcm <new-private-file>`. It retains at most30 seconds by default of incoming PCM16LE mono32kHz (`--record-uplink-seconds` permits an explicit bound of1..180 seconds for synchronization), writes only after the relay stops, uses0600 permissions and refuses to overwrite. This is opt-in and does not change the GUI's recording behavior. Keep recordings and session credentials outside the repository. A nonzero recording is not proof that it contains the known test clip.

## Offline validation

```sh
python -m unittest discover -s tests -v
```

Tests use generated temporary identities, synthetic PCM and loopback TLS, never microphones/speakers. Optional `PASSTHROUGH_JDK=/path/to/jdk` adds interoperability with the Android app's actual Java connection/framing source on a desktop JVM. That is not an Android audio/provider test.

## Packaging

```sh
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onedir --windowed --name PassThrough launcher.py
```

Build on Linux for Linux and on Windows11 for Windows11; PyInstaller is not a cross-compiler. Include project LICENSE and THIRD_PARTY.md with distributions. Current build tooling used Qt6.12/sounddevice0.5.6/cryptography50.0.2. Do not present a Windows source recipe as a tested Windows executable.
