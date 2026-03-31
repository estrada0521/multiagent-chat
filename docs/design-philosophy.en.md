# multiagent-chat Design Philosophy

Japanese version: [docs/design-philosophy.md](design-philosophy.md)

This document sits next to the feature overview in [README.md](../README.md) and the implementation notes in [docs/technical-details.en.md](technical-details.en.md). Its goal is to explain what this system is trying to become. `multiagent-chat` is not a browser terminal manager with chat added on top. It is an attempt to separate the agent side, the human side, and the path back into the physical world, then shape each layer differently.

Here, pure versus impure does not mean "few features" versus "many features." A Hub, structured logs, session continuity, and mobile access are not anti-pure by themselves. The real boundary is whether the system hardens temporary compensations for current model weakness, such as rigid protocols, skill catalogs, workflow engines, or ceremonial orchestration, into its core architecture.

The core asymmetry is this:

- the agent side should move toward a purer substrate
- the human side should move toward a more natural conversational interface
- the whole system should stay open to the physical world rather than remain trapped inside one screen

The design choices below follow from that asymmetry.

## 1. Do not force the agent side to live inside human-shaped tools

Terminals, editors, and desktop UI conventions are useful for people, but they are not necessarily the right long-term shape for agents. This is why the execution layer here is kept as low-flavor as possible.

tmux is used less as a polished terminal product and more as a runtime substrate. Sessions, panes, sockets, environment variables, and pane capture all remain directly accessible. Primitives such as `send-keys` and `capture-pane` can be used without building a heavier abstraction first. The point is not that tmux is inherently beautiful. The point is that it stays simple enough to act as an execution base.

## 2. Make chat, not the pane grid, the human-facing primary surface

What people usually need from a multi-agent system is not constant exposure to raw pane output. They need to see who said what, who replied to whom, what files were referenced, and what results came back. That structure is closer to a message stream than to a pane mosaic.

This is why the human-facing surface is a chat UI. The chat layer organizes senders, targets, reply relationships, attachments, brief, memory, Pane Trace, and file preview around the message. Pane Trace and terminal popups still exist, but they exist as windows into the execution layer rather than as the primary workspace.

## 3. Keep transport thin and push meaning outward

The system deliberately avoids turning `agent-send` into a large protocol surface. The center of the transport remains close to `agent-send <target>` plus text payload, while richer behaviors are expressed through message conventions and interpreted later by the UI.

That is why `[Attached: path]` stays part of the message body rather than becoming a separate transport-level feature. The message stays simple, the agent can read the path when needed, and the human-facing layer can still show file cards and previews. The guiding idea is that the bus should remain thin even when the viewing layer becomes richer.

## 4. Do not confuse durable substrate with temporary scaffolding

What this environment values is not a giant built-in substitute for intelligence, but a substrate that lets stronger models work in place. Session continuity, state preservation, structured logs, observability, and easy human intervention are durable. Large fixed skill systems or workflow engines are often temporary scaffolding.

This does not mean skills or workflows are forbidden. They can still be given ad hoc when needed, and a stronger agent can assign temporary sub-roles to weaker ones. The problem begins when those temporary instructions become the architecture itself. Once that happens, the whole system starts encoding the limitations of today's models. The goal here is the opposite: keep the substrate stable enough that model improvement makes the system stronger without forcing a rewrite of its basic shape.

## 5. Protect session continuity more than process continuity

The continuity model is centered on the session, not on one immortal process. If a live tmux session survives, it can be resumed directly. If the process stops, the system still aims to preserve enough state through the session name, workspace, logs, brief, and memory to make revival meaningful.

This is why the Hub separates `Kill` from `Delete`. `Kill` stops the current runtime while preserving the basis for `Revive`. `Delete` removes the log directory and related state, which removes that basis. The goal is not to keep every process alive forever. The goal is to make the session recoverable.

## 6. Do not collapse all context into one mutable note

Long-running work becomes harder to reason about when rules, summaries, history, and terminal state all get pushed into one mutable file. This project keeps those layers separate from the start.

- `docs/AGENT.md`: stable repo-level or environment-level rules
- brief: semi-static session-local instructions
- memory: evolving per-agent summaries
- `.agent-index.jsonl`: structured conversation history
- `.log` / `.ans` / Pane Trace: pane-side records

This layered model matters because continuity here does not come from one universal memo. It comes from preserving several different kinds of records without forcing them to overwrite one another.

## 7. Treat mobile as a precondition, not a secondary client

The system is not meant to be usable only while sitting in front of one desktop machine. The same Hub and chat UI are expected to remain usable on both desktop and mobile browsers.

That is why New Session, Resume, workspace-path entry, message sending, file preview, and Pane Trace are all available from the phone side as well. Public access and local HTTPS are not separate product lines. They are additional layers that make the same workspace reachable under more conditions and from more places.

## 8. Do not trap the system inside the screen

The project is also shaped by the fact that people live in the physical world. Useful context does not arrive only as typed text. Camera input, voice input, and remote access therefore matter here not just as convenience features, but as ways to let reality enter the workspace.

The point is not to simulate embodiment for its own sake. The point is to let meaningful slices of the physical world enter the session in durable forms: photos, voice, files, and access from outside the desk. These are forms that can be stored, attached to messages, revisited later, and shared across agents.

## 9. Build local-first and add public reach later

Session creation, message transport, logging, and the core Hub / chat workflow are all designed to work locally or over a LAN first. Public access is treated as an added layer, not as the foundation of the system.

That is why the repository includes Cloudflare commands and docs without making outside services part of the core runtime model. The same distinction appears between local HTTPS and public HTTPS. Local HTTPS exists for secure browser features on the local network. Public HTTPS exists for external reachability.

## 10. Summary

The design can be reduced to four statements:

- keep the agent side close to a low-flavor execution substrate
- give the human side a message-and-attachment-centered chat interface
- separate durable substrate from temporary scaffolding, and do not make the latter the core
- keep the interaction open to mobile use and to input from the physical world

tmux, the chat UI, layered logs, the Hub, mobile access, and the camera / voice / remote-access discussions are therefore not separate additions. They are expressions of the same underlying direction.
