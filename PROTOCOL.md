# PassThrough prototype wire protocol v1

Scope: initial Wi-Fi/USB TCP transport. No Bluetooth transport implementation or native headset-role claim.

1. Desktop listens on an explicitly configured endpoint; loopback is the default.
2. Phone establishes TLS1.2 or TLS1.3. The leaf certificate must be currently valid and its SHA-256 DER fingerprint must match the out-of-band desktop fingerprint before any token/audio is sent. Self-signed desktop identities are intended; pin replacement requires explicit user configuration.
3. Phone sends ASCII `PTHRU001` (8 bytes), then a desktop-generated random token encoded as64 lowercase ASCII hexadecimal characters.
4. Desktop compares token in constant time and replies ASCII `OKAY` (4 bytes). Invalid authentication closes the connection.
5. Each direction independently sends4-byte unsigned big-endian length followed by signed16-bit little-endian mono PCM at32000Hz. Positive even lengths only, maximum12800 bytes. Clean EOF stops the session; truncated/invalid frames fail. No files or audio recording by default.

Current Android connection/read timeout is5 seconds. Desktop must send continuous frames (silence is valid PCM) while playback is active. Playback-only phone sessions omit microphone frames. Format negotiation, stereo and timestamp/jitter negotiation are future protocol changes, not implicit v1 behavior.

Do not send certificate private keys or real session tokens through bridge/public source. Tests use a deterministic synthetic token and temporary self-signed certificate only.
