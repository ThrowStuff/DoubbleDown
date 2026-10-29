# Existing-project survey — 2026-10-28

Objective: GPLv3 open-source Android app replacing Signia user controls, plus phone relay of PC playback and hearing-aid-origin microphone audio. Research first per user; no APK implementation or installation yet. User subsequently chose BOTH Bluetooth and Wi-Fi/USB with configuration UI.

Old Bazzite/Connexx/publication work paused by explicit user instruction; pause sent to red in b228dea2-0cdf-4d35-8f59-588a8e192441. Preserve current aid connections and completed source bundle. No hardware handover or fitting writes.

## Findings

- https://github.com/FlyToRakib/soundpush : GPL-3.0-or-later, Android plus desktop audio relay, both directions/headset mode over Wi-Fi/USB. Early preview: human testing reported Windows11+Android12; Linux automated tests only. No verified Signia aid-origin microphone integration or Bluetooth PC-phone relay found. Candidate architecture to inspect, not proven solution.
- https://github.com/teamclouday/AndroidMic : GPLv3 phone-to-PC microphone transport, Linux/Windows/macOS; Wi-Fi TCP/UDP and USB ADB/Serial. README explicitly says Bluetooth transport removed. No exact Signia microphone path proven. Candidate mic transport component.
- https://github.com/Gheop/hearing-aid-presets : MIT Linux GNOME app with actual HAS GATT program enumeration/selection and volume controls. Verified source extension/extension.js uses HAS0x1854 and standard control point0x2bdb/active preset0x2bdc. Tested ReSound Vivia; Signia listed untested. Not Android and not a full vendor-app replacement. Retain MIT notices if reusing compatible code in GPLv3 project. Generalized compatibility/hardware claims in README not accepted as our exact-pair evidence.
- https://github.com/robertojrdev/bluetooth-mic-router : Apache2 Android communication-route helper, BLE headset/HFP support claimed. Does not record or relay audio. Android/other apps can override route; successful route request not source proof. Potential route-handling reference.
- https://github.com/thivyan-studios/hark-app : BSD3 phone microphone to hearing aids via Android/Oboe. Opposite microphone direction from required aid-origin input; not complete relay/controller.

No verified ready-made full Signia replacement plus bidirectional PC-phone-aid relay found in this survey. No claim exhaustive search.

## Architecture gates

ASHA is output-only; Android ASHA specification uses central/phone microphones for call input. Aid-origin mic requires actual LE Audio capture routing (or another verified bidirectional transport), regardless of relay app. Verify AudioRecord actual routed device and both-ear playback on Pixel7/Android17 before claiming microphone support. Merely exposing Source PAC/ASE on aids is insufficient.

PC-phone Bluetooth native audio peripheral role is not established for stock Pixel by these projects. Wi-Fi/USB data relay to phone with Bluetooth only on phone-aids side is a distinct architecture; do not silently substitute it if Bluetooth end-to-end is required.

Signia proprietary controls and cloud services (Assistant/TeleCare) not replicated by HAS presets alone. Full fitting/startup persistence separate from app control. No guessed GATT writes.

Primary technical references:
- https://source.android.com/docs/core/connect/bluetooth/asha
- https://developer.android.com/develop/connectivity/bluetooth/ble-audio/overview
- https://developer.android.com/reference/android/media/AudioDeviceInfo
