# Multiagent Chat

[日本語](README.ja.md)

A local, HTTPS-only chat hub that lets multiple command-line AI agents — for
example Claude, Codex, Gemini, Copilot, Cursor, OpenCode, Kimi, and Qwen — work
side by side in one conversation. Sessions live on your own machine, each
agent runs inside a supervised `tmux` pane, and you talk to them through the
same interface from:

- **a browser** on this Mac,
- **the native macOS desktop app**, or
- **an iPhone / iPad PWA** over your LAN (optionally exposed with Cloudflare
  Tunnel).

All three routes share one local `Hub` process, one session store, and the
same mkcert-signed HTTPS certificate. There is no plain-HTTP mode.

## Supported Agent CLIs

The Hub integrates any combination of these CLIs once they are installed and
logged in locally:

- Claude (`claude`)
- Codex (`codex`)
- Gemini (`gemini`)
- Copilot (`copilot`)
- Cursor (`cursor-agent`)
- OpenCode (`opencode`)
- Kimi (`kimi`)
- Qwen (`qwen`)

You only need the CLIs you plan to use. `quickstart` and `desktop-quickstart`
offer to install the missing ones via Homebrew / npm on first run.

## Prerequisites

Installed before running any `quickstart` script:

- macOS with Homebrew available as `brew`
- Xcode Command Line Tools: `xcode-select --install`
- Rust with `cargo` (desktop app only): <https://rustup.rs>
- `~/.local/bin` on your `PATH` (the scripts install `multiagent`,
  `agent-index`, and `agent-send` symlinks there)

The quickstart scripts install small runtime dependencies (`python3`, `tmux`,
`mkcert`) automatically through Homebrew when missing, but they will not
install Homebrew, Rust, or any agent CLI vendor account for you.

## Route 1 — Browser (Web)

Single command, setup plus Hub:

```bash
./bin/quickstart
```

When setup finishes the Hub binds to:

```text
https://127.0.0.1:8788/
```

The first run installs the mkcert local CA into the system trust store, so
Safari / Chrome / Firefox all accept the certificate without warnings.

Useful variants:

```bash
./bin/quickstart --setup-only   # prepare the machine, do not launch the Hub
./bin/quickstart --no-open      # launch the Hub but do not open a browser
```

## Route 2 — Desktop App (macOS)

Single command, setup plus build plus open:

```bash
./bin/desktop-quickstart
```

The desktop app launches and supervises its own Hub, so you do not run
`quickstart` separately. On first build the script caches `tauri-cli` under
`.multiagent/tools/tauri-cli/`.

Useful variants:

```bash
./bin/desktop-quickstart --dev          # cargo tauri dev
./bin/desktop-quickstart --build-only   # build the .app, do not open it
./bin/desktop-quickstart --setup-only   # prepare the machine, skip the build
./bin/tauri-build                       # rebuild only (skip interactive setup)
```

## Route 3 — Mobile PWA (iPhone / iPad)

The PWA uses the same Hub. Pick one of two deployments.

### 3a. Same LAN (LAN-only access)

1. Run `./bin/quickstart` on the Mac so the Hub is up on port `8788`.
2. On the Mac, locate `rootCA.pem` printed by the quickstart output (or run
   `mkcert -CAROOT`).
3. Send `rootCA.pem` to the iPhone / iPad via AirDrop, Files, or Mail.
4. On the device, install the certificate profile, then enable it in
   `Settings > General > About > Certificate Trust Settings`.
5. Open `https://<Mac-LAN-IP>:8788/` in Safari and choose
   `Share > Add to Home Screen`.

Never share `rootCA-key.pem`.

### 3b. Public access via Cloudflare Tunnel

Use this when the phone is off your LAN or you want a stable public URL.

```bash
brew install cloudflared
./bin/multiagent-cloudflare quick-start
```

For a fixed hostname:

```bash
./bin/multiagent-cloudflare named-login
./bin/multiagent-cloudflare named-setup <tunnel-name> <hostname>
./bin/multiagent-cloudflare named-start
```

Cloudflare issues its own HTTPS certificate, so the iOS mkcert profile from
`3a` is not required for tunnel access.

Check or stop the tunnel:

```bash
./bin/multiagent-cloudflare status
./bin/multiagent-cloudflare quick-stop   # or named-stop
```

## Troubleshooting

- `multiagent: command not found` → add `~/.local/bin` to `PATH`, or re-run
  the quickstart to recreate the symlinks.
- Browser shows a cert warning after a macOS update → re-run `mkcert -install`
  or `./bin/quickstart --setup-only`.
- Port `8788` already in use → set `AGENT_INDEX_HUB_PORT=<port>` before
  launching the Hub.
- Desktop build fails on `cargo install tauri-cli` → make sure Xcode CLT and
  Rust are current (`rustup update`).
