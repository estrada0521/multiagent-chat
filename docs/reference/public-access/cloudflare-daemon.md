# Cloudflare Public Daemon

Reference note: this is auxiliary material for optional external publication. The primary product flow remains local/LAN-first.

This keeps the public named tunnel path alive across login and recovers the public edge automatically.

It only manages the public stack:

- `cloudflared`
- `multiagent-public-edge`

It does not replace or modify the local Hub/chat flow.

## Install

```sh
bin/multiagent-cloudflare daemon-install
```

This installs a user LaunchAgent and starts a watchdog that repeatedly calls:

```sh
bin/multiagent-cloudflare named-start
```

The watchdog is safe to run continuously because `named-start` is idempotent and now also restores the public edge if only that process died.

## Status

```sh
bin/multiagent-cloudflare daemon-status
bin/multiagent-cloudflare status
```

Useful logs:

- `logs/cloudflare/watchdog.log`
- `logs/cloudflare/launchd.out.log`
- `logs/cloudflare/launchd.err.log`
- `logs/cloudflare/public-edge.log`
- `logs/cloudflare/cloudflared.log`

## Uninstall

```sh
bin/multiagent-cloudflare daemon-uninstall
```

This removes only the LaunchAgent. Public access can still be started manually with:

```sh
bin/multiagent-cloudflare named-start
```
