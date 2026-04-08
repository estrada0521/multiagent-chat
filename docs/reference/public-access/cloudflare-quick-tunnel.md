# Cloudflare Quick Tunnel

Reference note: this is auxiliary material for optional external publication. The primary product flow remains local/LAN-first.

This repo can expose Hub through a single public hostname while keeping chat routed under `/session/<name>/...`.

## Start

```sh
bin/multiagent-cloudflare quick-start
```

This does four things:

1. starts `cloudflared tunnel --url https://127.0.0.1:8788`
2. reads the generated `https://...trycloudflare.com` URL
3. stores its hostname in `certs/public-host.txt`
4. restarts Hub so `open-session` returns `/session/<name>/...` URLs on that hostname

## Stop

```sh
bin/multiagent-cloudflare quick-stop
```

This stops `cloudflared`, clears `certs/public-host.txt`, and restarts Hub back into local-only mode.

## Status

```sh
bin/multiagent-cloudflare status
```

## Files

- tunnel log: `logs/cloudflare/cloudflared.log`
- tunnel pid: `logs/cloudflare/cloudflared.pid`
- current public URL: `logs/cloudflare/cloudflared-url.txt`
- public host override: `certs/public-host.txt`

## Named Tunnel

For stable external access, use a named tunnel instead of Quick Tunnel.

### 1. Login

```sh
bin/multiagent-cloudflare named-login
```

This opens the Cloudflare browser login and installs the origin cert on this Mac.

### 2. Create or reuse the tunnel and DNS

```sh
bin/multiagent-cloudflare named-setup multiagent <your-hostname>
```

Example:

```sh
bin/multiagent-cloudflare named-setup multiagent agent.example.com
```

This:

1. creates the tunnel if it does not exist
2. routes DNS for the hostname
3. writes `logs/cloudflare/config.yml`
4. stores metadata in `logs/cloudflare/named-tunnel.json`
5. updates `certs/public-host.txt`
6. restarts Hub

### 3. Start it

```sh
bin/multiagent-cloudflare named-start
```

### 4. Stop it

```sh
bin/multiagent-cloudflare named-stop
```
