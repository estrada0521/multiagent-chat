# Chat Commands

This is the supplementary command and pane-control reference for the chat UI. README keeps the overview; this file keeps the current list.

## Pane Trace

- mobile: tap a thinking row to open the embedded Pane Trace viewer
- desktop: click a thinking row to open the selected agent's Pane Trace in a popup window
- on desktop, `Terminal` opens the real terminal window
- on mobile, `Terminal` routes to Pane Trace instead

## Slash Commands

Type `/` at the start of the composer to open command suggestions.


| command             | behavior                                                                              |
| ------------------- | ------------------------------------------------------------------------------------- |
| `/memo [text]`      | self memo to `user`; Import attachments alone are enough even without body text (and normal sends with no selected target also default to self) |
| `/cron`             | open the Cron creation flow with the current session / target prefilled               |
| `/load`             | send the current `memory.md` to the selected agent                                    |
| `/memory`           | ask the selected agent to refresh `memory.md`                                         |
| `/model`            | send `model` to the selected pane                                                     |
| `/up [count]`       | send up-navigation to the selected pane; default count is 1                           |
| `/down [count]`     | send down-navigation to the selected pane; default count is 1                         |
| `/restart`          | restart the selected agent pane                                                       |
| `/resume`           | resume the selected agent pane                                                        |
| `/ctrlc`            | send `Ctrl+C` to the selected agent pane                                              |
| `/interrupt`        | send `Esc` to the selected agent pane                                                 |
| `/enter`            | send `Enter` to the selected agent pane                                               |


`count` for `/up` and `/down` is clamped into the 1..100 range.

## Quick Actions

These are the controls exposed under the composer and its `Cmd` / `Command` menus.


| UI                       | behavior                                                      |
| ------------------------ | ------------------------------------------------------------- |
| `Import`                 | add local-device files into the session uploads area          |
| `Load` / `Load Memory`   | send the current `memory.md` to the selected agent            |
| `Memory` / `Save Memory` | update `memory.md` from the current conversation              |
| `Save` / `Save Log`      | save a pane-log snapshot immediately                          |
| `Restart`                | restart the selected agent pane                               |
| `Resume`                 | resume the selected agent pane                                |
| `Ctrl+C`                 | send `Ctrl+C` to the selected agent pane                      |
| `Enter`                  | send `Enter` to the selected agent pane                       |
| `Esc` / `Interrupt`      | send `Esc` to the selected agent pane                         |

## Header Menu

| UI           | behavior                                                                  |
| ------------ | ------------------------------------------------------------------------- |
| `Finder`     | open the current session workspace in Finder                              |
| `Camera`     | open the mobile-first camera overlay with direct capture / voice sending  |
| `Pane Trace` | open the dedicated Pane Trace window on desktop; mobile keeps it embedded |


## Notes

- pane-control commands and quick actions require at least one selected target
- commands are expected to grow over time, so this file is intended to be the update point rather than README
