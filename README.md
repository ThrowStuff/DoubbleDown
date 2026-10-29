# DoubbleDown — PassThrough

**DoubbleDown** is the project repository; **PassThrough** is the Android app. The revised scope makes PassThrough a Bluetooth-first, hearing-aid companion designed for broad device compatibility. Computer audio over a local network belongs in a separate desktop-link component. The source is original and licensed GPL-3.0-only; existing projects were used as learning references, not copied.

This remains an early prototype, not a replacement for Signia's full feature set. The Android TLS session and PCM framing now live in a separate Gradle library, while audio orchestration, hearing-aid routes and settings remain in the app. Live tests confirmed spoken playback through the Android hearing-device output and matched a known speaker-played tone in the hearing-aid microphone uplink. Both tests used one Pixel 7 setup; they do not establish voice quality, long-term reliability, or compatibility with other devices. Windows has not been run or validated, and Windows 11 testing remains paused.

Implemented in the transitional prototype: saved Wi-Fi/USB connection settings, device and route inventory, explicit audio-route selection, authenticated TLS relay, route-loss handling, and Linux desktop audio endpoints. The Android network session and frame codec are isolated in `:desktop-link`; the UI and audio lifecycle are still in the app. PassThrough's target is direct hearing-aid Bluetooth operation. A Bluetooth computer-to-phone link is outside the revised scope. Hearing-aid program controls, broad cross-device compatibility, full component separation and Windows runtime support remain unfinished. See [scope and architecture](SCOPE.md), [desktop documentation](desktop/README.md), [requirements](REQUIREMENTS.md) and [wire protocol](PROTOCOL.md).

## Intended components

- **PassThrough for Android:** hearing-aid selection and grouping, per-ear battery, supported program controls, Bluetooth audio routing, and actual hearing-aid-origin microphone relay where the aid and Android device expose it.
- **Separate desktop-link component:** encrypted, authenticated computer-to-phone audio over the local network, with explicit audio endpoints, user-visible streaming controls, reconnect handling and diagnostics.
- Capability-specific explanations where proprietary functions or Android platform restrictions prevent support.

Cloud Signia Assistant, provider TeleCare and permanent fitting writes have no verified replacement interface. These are research gaps, not implemented features. The project does not claim clinical fitting, universal manufacturer support, Windows validation or a complete vendor-app replacement.

## Build requirements

JDK 17, Android SDK platform 35 and build-tools 35.0.0. Set `JAVA_HOME` and `ANDROID_HOME`, then run:

```sh
./gradlew :app:assembleDebug :app:lintDebug
```

The Gradle 8.11.1 wrapper includes distribution checksum verification. Android 8/API 26 is the compatibility baseline; availability of hearing-aid playback depends on OS and device support. Microphone communication routing requires Android 12/API 31+ and an actual compatible hearing-device route. Compilation does not establish manufacturer-wide compatibility. Desktop targets are Linux and Windows 11; Windows 10 is outside scope.

## Transitional computer relay

The current prototype connects the phone to a desktop companion over pinned TLS using Wi-Fi or USB/ADB. The v1 wire protocol is retained during the boundary refactor. Its tested live path used ADB reverse forwarding; direct LAN and physical USB operation still need validation.

The stream format is mono PCM16LE at 32 kHz; stereo and adaptive latency are unfinished. Audio is not recorded to disk during normal relay use. Phone microphone/speaker are excluded from route choices. Android may reroute queued audio before callbacks execute, so source/output isolation and disconnect tests on real devices remain required; preferred-device selection is not a hard OS routing guarantee.

## Validation

Android debug build and lint pass (warnings remain for prototype UI localization and custom certificate pinning). Core Java frame tests cover byte order, payload preservation, EOF, malformed lengths and truncation. Desktop tests cover duplex framing, certificate pinning, token rejection, oversized frames and Java/Python interoperability. Focused offline tests and a PipeWire synthetic-PCM test passed. These tests do not establish long-term Android lifecycle behavior, universal hearing-device compatibility or Windows functionality.

Live evidence is limited: one user-confirmed voice playback through the hearing-device output, and a 1 kHz tone played by the nearby Linux desktop that matched the phone's hearing-aid microphone uplink (correlation 0.60356, found about 9.12 seconds into a 30-second capture). Android reported the selected hearing-aid microphone route verified. This confirms the known test signal reached the uplink on this Pixel 7 setup; speech quality, bilateral behavior, lifecycle reliability, direct LAN/physical USB, and other devices remain to be tested. The recording stays outside the repository.

Licensed under GNU GPL version 3 only; see [LICENSE](LICENSE) and [third-party notices](desktop/THIRD_PARTY.md).
