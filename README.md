# Agent Window

Agent Window is a UNIX-philosophy **local interface for macOS** that watches, from outside, a workspace where multiple Agent CLIs are running.

Each Agent CLI launches normally inside a tmux pane. It never calls a model through an API or SDK. **It uses only the capabilities each CLI already has.**

[Design philosophy](DESIGN.md) · [日本語](README_jp.md)

<p align="center">
  <img src="media/agent-window-hero-1.png" width="100%" alt="Agent Window hero 1">
  <img src="media/agent-window-hero-2.png" width="100%" alt="Agent Window hero 2">
</p>

---

# Setup

The current implementation targets macOS.

## Requirements

* `python3`
* `tmux`
* `cargo`
* `tauri-cli`
* Xcode Command Line Tools

`./setup/preflight` checks for missing dependencies and the commands needed to install them. The script never installs anything itself.

Install whichever Agent CLIs you plan to use individually, and authenticate each one the normal way.

## Launch

Run the following from the repository root.

```bash
./tauri_app/tauri_start
```

This builds and launches the Tauri App. The Hub is started by the Tauri App and uses port `8788` by default.

# Use

## Start a session

Choose a workspace from `New Session` in the Hub.

A unified log continues across changes in session name, workspace, and participating Agents. `New Session` starts another log; when to do that is up to the human.

Archive, revive, delete, rename, and change a session's workspace from the Hub (right-click a session in the sidebar). Renaming does not restart the chat server or change the URL.

## Add an Agent

`Add / Remove Agent` in the top right adds or removes Agents from the session. Running more than one instance of the same CLI Agent produces instance names such as `Claude-2`.

* `Terminal` — opens a plain shell at the workspace root
* `tmux window` — opens a compact, pane-switching tmux terminal directly (the tmux socket name is fixed as `agent-window`)
* `Finder` — opens the current workspace in Finder

The separate reload button beside it hard-reloads the GUI server. If the source code has changed, the running server is replaced with the new implementation.

<p align="center">
  <img src="media/agent-window-menu.png" width="500" alt="Menu">
</p>

## Send

The input field is normally minimized to leave more room for the chat, and expands with the `O` button at the bottom of the screen or by pressing the scroll wheel. Which Agent icons are selected determines who a message is sent to.

Text in the input field is entered directly, via `tmux send-keys`, into the pane running the selected Agent CLI. It is not converted into an Agent Window-specific message format, so **slash commands and other native CLI commands also pass through the same input field.** A failed send is detected as `send_error`, but success is not notified. Minimal controls that CLIs don't offer by default — restarting a pane, interrupting from mobile — are wired in by Agent Window.

Agent Window also recognizes these shortcut commands:

| Command | Action |
| --- | --- |
| `/up [count]`, `/down [count]`, `/left [count]`, `/right [count]`, `/enter`, `/esc`, `/ctrlc` | Send the corresponding key to the selected pane. `count` is optional (1–100). |
| `/restart`, `/resume` | Restart / resume the CLI. |
| `/open-pane` | Open the selected Agent's tmux pane. Desktop only. |
| `/nativelog` | Reveal the selected Agent's native log in Finder. Desktop only. |
| `/log` | Insert `.agent-window/.log.jsonl` into the message. Also works in the middle of text. |

Typing `@` searches files in the workspace. Files can also be attached with the plus button or by drag-and-drop. Attached files are saved to `<workspace>/.agent-window/uploads/`, and their path is passed to the Agent as ordinary text.

## Read

The GUI displays the unified log as a single timeline across the human and all Agents.

Messages continue in the same unified log as CLIs switch, Agents run concurrently, and processes restart. Changes to the session name or workspace leave past entries unchanged.

The unified log's substance is an append-only JSONL file.

```text
~/.agent-window/session/{session_name}/.log.jsonl
```

It's also reachable from the current workspace via a symlink. It isn't a database closed inside Agent Window — it survives Agent Window stopping, and reads as an ordinary file.

The unified log isn't each CLI's detailed execution history. It's a projection, reduced to a granularity both humans and Agents can read across.

Tool calls are streamed to the screen while running, for a sense of progress, but are not kept in this timeline. Clicking the icon opens the corresponding tmux pane.

Each CLI's execution record is watched from outside, and the process/log-path mapping is re-resolved whenever necessary. So the CLI process's lifespan and the unified log's lifespan don't have to match.

Each entry records the path of its source native log, and its position within it.

## Watch the workspace

Git and workspace state are watched and projected onto the right pane. File search also uses the observed workspace information.

Clicking a file opens it in the macOS default application. The desktop version of Agent Window does not reimplement a file viewer that already exists elsewhere. Mobile can't rely on that, so a bottom-sheet-style built-in viewer opens instead.

Clicking an uncommitted change opens it in git's configured diff viewer (`git difftool`).

## Fit the window

| Key | Action |
|---|---|
| `⌥⌘0` / `⌥⌘9` | Default / compact size |
| `⌥⌘H` | Match the window height to the latest message |
| `⌥⌘P` | Keep above other windows |
| `⌥⌘↑` `←` `→` `↓` | Move to that screen edge; `↓` centers |
| `⌘B` / `⌘E` | Toggle the Hub sidebar / right pane (add `⌥` to grow the window outward instead) |

With Fit Height (`⌥⌘H`) on, the Hub and right pane become native macOS menus, so `⌘B` / `⌘E` do nothing.

<p align="center">
  <img src="media/agent-window-fit.gif" width="100%" alt="Fit Height demo">
</p>

## Connect Agents to each other

An Agent can send a message directly to another Agent in the session with `agent-send`. Place `SKILL.md` at the designated location if needed — it is the only SKILL Agent Window has committed to.

```bash
agent-send <target> <message>
```

`agent-send` is a thin wrapper around the same `tmux send-keys` a human uses. It only resolves the destination and attaches a prefix such as `[From: Claude]`.

Here, success only means the input was delivered to the runtime. It doesn't mean the target Agent understood it or acted on it.

## Give a name

Agent Window's one and only unnecessary feature.

```bash
agent-send name <target> <name>
```

An Agent can be given a name that works within the session. The name is used only as an `agent-send` address and in the `[From: ...]` prefix; existing instance names and log identities are unchanged.

## Use it from a phone

You can connect to the same screen from a mobile device on the same LAN.

First, start the Tauri App and Hub in HTTP mode. While they are running, run:

```bash
./setup/pwa/enable
```

This script checks the running Hub and prepares mkcert and a local certificate. **mkcert installs a local CA on the system.**

From then on, `~/.agent-window/state/pwa/enabled` is detected at launch and Agent Window starts in HTTPS mode.

```bash
./tauri_app/tauri_start
```

Send mkcert's `rootCA.pem` to the device that will connect, install the certificate profile, and enable trust for it. Then open either of the following in Safari:

```text
https://<Mac LAN IP>:8788/
https://<Mac name>.local:8788/
```

Add it to the Home Screen to use it as a PWA.

For reaching Hub from outside the LAN, see [`external-access/README.md`](external-access/README.md).

<p align="center">
  <img src="media/agent-window-mobile-light-1.png" width="48%" alt="Mobile UI, light 1">
  <img src="media/agent-window-mobile-dark-1.png" width="48%" alt="Mobile UI, dark 1">
  <img src="media/agent-window-mobile-light-2.png" width="48%" alt="Mobile UI, light 2">
  <img src="media/agent-window-mobile-dark-2.png" width="48%" alt="Mobile UI, dark 2">
  <img src="media/agent-window-mobile-light-3.png" width="48%" alt="Mobile UI, light 3">
  <img src="media/agent-window-mobile-dark-3.png" width="48%" alt="Mobile UI, dark 3">
  <img src="media/agent-window-mobile-light-4.png" width="48%" alt="Mobile UI, light 4">
  <img src="media/agent-window-mobile-dark-4.png" width="48%" alt="Mobile UI, dark 4">
</p>

## Supported CLIs

Claude, Codex, Antigravity, Cursor, Grok.

The receiving side needs to know where each CLI's native log lives and what format it's in, so there is per-CLI handling.
The sending side is the same for every CLI. It only enters text into a pane, so there is no CLI-specific message protocol.

# License

[0BSD](LICENSE). Do whatever you want with it.
