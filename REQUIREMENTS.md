# Acceptance requirements

## PassThrough: Bluetooth hearing-aid core

PassThrough connects to hearing aids through Bluetooth and uses standard Android audio/device APIs where possible. Target broad compatibility across manufacturers and Android devices through runtime capability detection; do not claim universal support until tested. Identify intended aids explicitly and preserve existing bonds. Enumerate real controls and supported programs before enabling controls; never guess vendor characteristic values. Track both ears and report partial failures. A successful write is not proof both aids changed: read back or use device events. Preserve existing fitting/gain and restore previous supported settings on a failed coordinated change where feasible.

The PassThrough core does not own the computer-to-phone local-network transport. Do not add a Bluetooth computer-to-phone data link to satisfy the revised scope.

## Audio

Support user-selectable Bluetooth, Wi-Fi and USB computer links. Provide saved configuration per transport, computer/device selection, readable capability and connection status, explicit connect/disconnect, and user-visible transport failure. USB choices distinguish tethered networking from ADB. Switching modes must stop the current relay cleanly and preserve hearing-aid bonds; no silent fallback. Bluetooth implementation depends on verified Android roles; distinguish custom Bluetooth data transport with a companion from behaving as a standard Bluetooth headset.

Prove bilateral playback with user listening confirmation. Prove microphone input originates in the aids by checking actual AudioRecord routing and a user-controlled isolation test; never silently fall back to the phone microphone. ASHA-only connections must report microphone unavailable. A route request or service advertisement alone is insufficient.

Implement hearing-aid streaming only following explicit user start, with a persistent stop control, bounded queues, backpressure and route verification. Stop capture on route loss rather than leak phone-microphone audio or unexpectedly switch playback to the speaker. Test permission revocation, disconnect/reconnect, screen-off, calls and process death. No captured audio stored by default.

## Separate desktop-link component

Computer audio reaches the phone through a separate component over the local network. It must provide authenticated pairing, encrypted transport, explicit start/stop, bounded queues and explicit computer audio input/output selection. Keep the audio protocol and transport isolated from PassThrough's Bluetooth hearing-aid layer. Windows 11 and Linux are desktop targets; Windows 10 is outside scope.

## Feature completeness

Before calling this a Signia replacement, inventory the exact installed app's user-visible functions and classify each as implemented, device-unsupported or blocked by an unavailable vendor interface. Program controls, permanent fitting, cloud Assistant and TeleCare are distinct capabilities. No substitute clinical tuning algorithm is implied.

## Delivery

Reproducible Android build, installable signed APK, GPLv3 source and dependency attribution, separate desktop-link component for the agreed local-network transport, documented tests on the actual Pixel7/Android17 and Signia Pure C&G T1IX firmware25.6.1104.3. No claims of tested capture or transport until observed. Current preview has not met these delivery requirements.

## Desktop platforms

Windows 11 and Linux are required for the separate desktop-link component. Windows 10 is explicitly outside scope and has no official project support. Provide equivalent local-network configuration controls, explicit audio input/output devices, platform-specific virtual microphone instructions, and packaged desktop application. Test each platform separately; Linux tests do not establish Windows behavior. Windows 11 testing on Red is paused until the new component boundaries and test scope are documented and mutually acknowledged. Any later admin USB handoff must be explicitly approved. Preserve internal adapter and hearing-aid bonds; the spare Bluetooth 4.0 adapter is not an LE Audio microphone validation radio.

## Broad Android compatibility

Support Android across manufacturers/platforms, not a Pixel-only app. Baseline Android8/API26 for app/UI and available playback routes; newer capabilities gated by API and runtime device support. Communication-route mic selection requires Android12/API31 APIs; LEAudio capability API33+, actual hearing-aid microphone route must be verified. Document unsupported capabilities clearly rather than advertise every feature on every device. Test across Android versions and vendors; Pixel7 is one reference target.

Testing order: finish the scope and component split first. Then test the separate desktop-link component on Linux; resume Windows 11 validation only after the rescope is complete. White leads architecture and integration; Red holds Windows testing until then.

Budget correction: user explicitly excludes persistentWindows11 test VM, its image and VM disk from project storage limitations. Treat as reusable tool. Project artifacts remain separately accounted.
