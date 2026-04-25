# Source

`multiagent_chat/` is the core Python implementation package. The historical
`lib/agent_index/` package path has been removed from the runtime.

`src/` owns backend runtime truth: session state, storage, sync, transport
boundaries, process/runtime orchestration, and UI-independent presentation
assembly. Concrete HTML, CSS, browser JavaScript, and PWA/static app assets live
under `apps/`.

Important subdomains:

- `multiagent_chat/presentation/` assembles Hub/Chat presentation output from
  app fragments and runtime settings without owning concrete app source files.
- `multiagent_chat/transport/` owns HTTP request boundary helpers such as
  forwarded base path and desktop/mobile view variant resolution.

The former `src/multiagent_chat/web/` bucket has been retired. Do not add new
frontend surface files under `src/`.
