# multiagent-chat v1.0.9

Japanese version: [beta-1.0.9.ja.md](beta-1.0.9.ja.md)

Released: 2026-04-12

## Fixes

### macOS Desktop App: Python 3.9 compatibility fix

The desktop app now works on Macs where the system Python is 3.9 (Command Line Tools default on older macOS). Version 1.0.8 failed to start a chat session on Python 3.9 due to a backslash inside an f-string expression, which is only valid in Python 3.12+. This is now fixed.

### macOS Desktop App: cryptography package auto-install

The Hub now automatically installs the `cryptography` Python package on first launch if it is not already present, instead of failing silently.

### Documentation: Gatekeeper bypass instructions updated

The download pages now include the correct Gatekeeper bypass command (`xattr -cr`) for the "damaged app" warning that macOS shows for unsigned apps downloaded from the internet.
