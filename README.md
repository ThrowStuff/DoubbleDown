# DoubbleDown — PassThrough audio bridge

**DoubbleDown** is the project repository; **PassThrough** is the app name. This is an original GPL-3.0-only Android companion and desktop audio-relay prototype for hearing-aid users. Existing projects were used as learning references; no third-party implementation has been copied into this source.

This is an early, incomplete prototype, not a replacement for Signia's full feature set. The Android app and Linux desktop companion build. A live test confirmed spoken playback through the Android hearing-device output. A later test verified that Android selected the hearing-device microphone route and that nonzero audio reached the desktop. Matching a known external acoustic reference is still pending, so aid-microphone content has not been independently confirmed. Windows has not been run or validated.

Implemented: saved connection settings, device and route inventory, explicit audio-route selection, authenticated TLS Wi-Fi/USB relay, route-loss handling, Linux desktop controls and audio endpoints. Bluetooth PC-to-phone transport, hearing-aid program controls, robust cross-device compatibility and Windows runtime support remain unfinished. See [desktop documentation](desktop/README.md), [requirements](REQUIREMENTS.md) and [wire protocol](PROTOCOL.md).

## Intended complete package

- Hearing-aid selection and pair grouping, per-ear battery, program enumeration and supported user controls.
- Playback plus actual hearing-aid-origin microphone relay to a desktop companion, with explicit input/output selection and route-loss handling.
- Secure local pairing, user-visible streaming controls, reconnect handling, diagnostics and an accessible interface.
- Capability-specific explanations where proprietary functions or Android platform restrictions prevent support.

Cloud Signia Assistant, provider TeleCare and permanent fitting writes have no verified replacement interface. These are research gaps, not implemented features. The project does not claim clinical fitting, universal manufacturer support, Windows validation or a complete vendor-app replacement.

## Build requirements

JDK 17, Android SDK platform 35 and build-tools 35.0.0. Set `JAVA_HOME` and `ANDROID_HOME`, then run:

```sh
./gradlew :app:assembleDebug :app:lintDebug
```

The Gradle 8.11.1 wrapper includes distribution checksum verification. Android 8/API 26 is the compatibility baseline; availability of hearing-aid playback depends on OS and device support. Microphone communication routing requires Android 12/API 31+ and an actual compatible hearing-device route. Compilation does not establish manufacturer-wide compatibility. Desktop targets are Linux and Windows 11; Windows 10 is outside scope.

## Prototype relay

Wi-Fi and USB use the same pinned TLS connection to a desktop companion. Set the desktop address, port `49721`, SHA-256 certificate fingerprint and 64-character session token. Verify the fingerprint out of band on your own desktop. For USB tethering, use the computer's tether-network address. For ADB, run `adb reverse tcp:49721 tcp:49721` on the computer and choose USB debugging mode; the phone uses localhost. The tested live path used Wi-Fi ADB forwarding; direct LAN and physical USB operation still need validation.

The stream format is mono PCM16LE at 32 kHz; stereo and adaptive latency are unfinished. Audio is not recorded to disk during normal relay use. Phone microphone/speaker are excluded from route choices. Android may reroute queued audio before callbacks execute, so source/output isolation and disconnect tests on real devices remain required; preferred-device selection is not a hard OS routing guarantee.

## Validation

Android debug build and lint pass (warnings remain for prototype UI localization and custom certificate pinning). Core Java frame tests cover byte order, payload preservation, EOF, malformed lengths and truncation. Desktop tests cover duplex framing, certificate pinning, token rejection, oversized frames and Java/Python interoperability. Focused offline tests and a PipeWire synthetic-PCM test passed. These tests do not establish long-term Android lifecycle behavior, universal hearing-device compatibility or Windows functionality.

Live evidence is limited: one user-confirmed voice playback through the hearing-device output, and a separate session with Android reporting the hearing-device microphone as the selected recorder route while nonzero PCM arrived at desktop. A known external acoustic reference has not yet been matched. No claim is made that microphone samples contain the user's voice or that the complete path is reliable.

Licensed under GNU GPL version 3 only; see [LICENSE](LICENSE) and [third-party notices](desktop/THIRD_PARTY.md).
