# Gemini Direct API Probe

This repo now includes [`bin/multiagent-gemini-api-stream`](../bin/multiagent-gemini-api-stream), a minimal helper for probing the Gemini Developer API directly instead of going through the Gemini CLI.

The point of this helper is not to replace the existing Gemini pane workflow. It is a first upstream test surface for the longer-term goal of building provider-specific adapters above generic pane capture.

## Requirements

- `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- network access from the current shell

For free-tier testing, Google AI Studio can issue an API key without requiring Gemini Advanced. See the official docs:

- https://ai.google.dev/gemini-api/docs/api-key
- https://ai.google.dev/gemini-api/docs/pricing

## Basic usage

```bash
bin/multiagent-gemini-api-stream "Say hello in one short sentence."
```

stdin also works:

```bash
printf '%s' 'Explain why structured streams matter.' | bin/multiagent-gemini-api-stream
```

## Useful options

Use a different model:

```bash
bin/multiagent-gemini-api-stream --model gemini-2.5-pro "Summarize the task."
```

Add a system instruction:

```bash
bin/multiagent-gemini-api-stream \
  --system "You are terse and technical." \
  "Explain SSE in two sentences."
```

Get normalized event JSONL instead of plain text:

```bash
bin/multiagent-gemini-api-stream --format jsonl "Return a short answer."
```

See raw SSE lines:

```bash
bin/multiagent-gemini-api-stream --format raw "Return a short answer."
```

## Output modes

- `text`: prints extracted text only
- `jsonl`: emits normalized event JSONL with `response.started`, `response.output_text.delta`, `response.completed`, and `response.error`, including the Gemini payload
- `raw`: prints the raw SSE lines exactly as received

## Why this exists

For generic external agent CLIs, multiagent usually only has access to PTY output, sidecar logs, or pane capture. Direct provider APIs are different: they can expose a more upstream structured stream. This helper is the first small step toward that adapter layer.

## Minimal runner that bridges into chat

[`bin/multiagent-gemini-direct-run`](../bin/multiagent-gemini-direct-run) is the minimal runner that stores the Gemini direct stream as normalized event JSONL under the session log directory while also appending the final response into `.agent-index.jsonl`.

```bash
bin/multiagent-gemini-direct-run \
  --session multiagent \
  --reply-to <msg_id> \
  "Reply in one short paragraph."
```

It currently does three things:

- writes the normalized event stream under `normalized-events/gemini-direct/...jsonl`
- keeps only the latest 5 normalized event sidecar JSONL files per session and prunes older ones automatically
- appends `kind="provider-run"` system entries to the chat timeline for start / completion / failure
- writes the latest provider runtime snapshot into `.provider-runtime.json` while the run is active
- appends the successful final response as a `sender="gemini"` chat entry

This is intentionally minimal. The chat message body itself does not yet mutate in place per chunk; for now the sidecar event log is the structured stream, and chat receives the bridged final result.

## Minimal chat entry point

Inside chat, the runner can now be started with this slash command:

```text
/gemini Explain the current task in one short paragraph.
```

That path currently does the following:

- records the user prompt as a normal `[From: User]` chat entry in `.agent-index.jsonl`
- starts the runner asynchronously
- stores the normalized Gemini events under `normalized-events/gemini-direct/...jsonl`
- shows a live structured thinking row such as `response.output_text.delta · chunk 4 · 4.5k tok`
- lets the user click or tap that thinking row to open the normalized event viewer for the current run
- appends the final `gemini -> user` response to chat on success
