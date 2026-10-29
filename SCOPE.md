# PassThrough and desktop-link scope

**Status:** revised scope acknowledged by White and Red on 2026-10-29. Architecture work is in progress. Windows 11 testing remains paused until this rescope is complete.

## Product boundary

### PassThrough

PassThrough is the Android hearing-aid companion. Its device connection is Bluetooth. The design goal is to work across hearing-aid brands and Android devices by using standard Bluetooth capabilities and Android APIs, with runtime capability detection. Compatibility must be demonstrated per device and feature; “agnostic” is a target, not a claim that every aid exposes the same controls.

PassThrough owns hearing-aid selection, supported device controls, audio route selection, playback and hearing-aid microphone capture where the aid and Android platform provide it. It must preserve existing aid bonds and fitting state. It must not silently switch to the phone microphone or speaker when an aid route is lost.

### Separate desktop-link component

Computer audio and microphone routing belong to a separate desktop-link component. The phone and desktop component communicate over the local network, initially Wi-Fi. Linux and Windows 11 are desktop targets; Windows 10 remains outside project scope. A Bluetooth data link between the computer and phone is not part of the revised plan.

Target audio path:

```text
Computer audio app ↔ desktop-link ↔ local network ↔ phone-side link ↔ PassThrough ↔ Bluetooth hearing aids
```

The exact boundary between the Android link adapter and PassThrough still needs implementation design. Keep the network protocol independent of Bluetooth routing so either side can evolve without coupling the two transports.

## Current code and migration

The published prototype currently puts hearing-aid route controls and the phone-to-desktop TLS relay in the same Android app. The desktop folder implements the Linux companion and a Windows audio path that has not been run on Windows. The current Wi-Fi/USB relay and its v1 protocol are transitional; isolate them as the separate desktop-link component before extending their features. Preserve compatibility during the refactor until the replacement path is verified.

The live Pixel 7 test verified Android's selected hearing-aid microphone route and matched a known speaker-played 1 kHz tone in the desktop uplink capture. This confirms that test signal path for one setup; it does not establish voice quality, broader compatibility or long-term reliability.

## Work and test order

1. Keep PassThrough Bluetooth hearing-aid functions distinct from the desktop-link local-network transport.
2. Define the phone/desktop component boundary, message lifecycle, pairing, security and audio route API.
3. Refactor the existing Wi-Fi/USB prototype into the separate component without regressing verified aid routing.
4. Continue Linux validation after the scope and architecture are agreed.
5. Resume Windows 11 testing only after the rescope is complete and Red is released from the hold.
6. Expand Android validation beyond the Pixel 7 before making broad compatibility claims.

Current testing constraint: phone UI activation and control is paused. Background ADB checks are allowed. Windows 11 testing remains on hold until this rescope is complete.
