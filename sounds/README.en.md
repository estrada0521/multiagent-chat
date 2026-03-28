# Notification Sounds

This directory holds personal OGG files for notification playback and related audio cues.

The repository does not ship audio binaries. Cloning without these files is fine: the UI still works, only sound playback is skipped.

## File names

| File name | Usage |
|------|------|
| `commit.ogg` | played for commit-related chat entries |
| `awake.ogg` | preview sound for the Awake toggle in Hub Settings |
| `mictest.ogg` | preview sound for the Sound notifications toggle |
| `notify_*.ogg` | regular chat notifications; one file is chosen at random each time. `/notify-sounds` exposes this set, and `/notify-sound` without `?name=` also picks randomly from the same set |
| `HH-MM.ogg` | scheduled daily playback at that local time, for example `8-00.ogg` or `20-30.ogg` |
| `auto.ogg` | auxiliary sound that may be referenced by scheduled or related flows |

If a matching file does not exist, only that sound is skipped. Chat operation itself is not affected.

## Replacing sounds

1. Prepare any source audio you want to use.
2. Convert it to OGG Vorbis if needed.
3. Save it into `sounds/` using one of the file names above.

For normal message notifications, add one or more `notify_*.ogg` files such as `notify_default.ogg` or `notify_alt.ogg`. If no `notify_*.ogg` files exist, ordinary chat notifications stay silent.

## Licensing

If you add your own sound files, use material that you are allowed to store and redistribute in your own environment.
