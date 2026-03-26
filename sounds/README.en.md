# Notification Sounds

This directory holds personal OGG files for notification playback and related audio cues.

The repo can be cloned without these files. In that case the UI still works, but sound playback is skipped.

## File names

| File name | Usage |
|------|------|
| `commit.ogg` | played for commit-related chat entries |
| `awake.ogg` | preview sound for the Awake toggle in Hub Settings |
| `mictest.ogg` | preview sound for the Sound notifications toggle |
| `notify_*.ogg` | regular chat notifications; one file is chosen at random each time |
| `HH-MM.ogg` | scheduled daily playback at that local time, for example `8-00.ogg` or `20-30.ogg` |
| `auto.ogg` | reserved fallback or auxiliary sound when referenced by related flows |

If a matching file does not exist, only that sound is skipped. Chat operation itself is not affected.

## Replacing sounds

1. Prepare any source audio you want to use.
2. Convert it to OGG Vorbis if needed.
3. Save it into `sounds/` using one of the file names above.

For normal message notifications, add one or more `notify_*.ogg` files such as `notify_default.ogg` or `notify_alt.ogg`.

## Licensing

If you add your own sound files, use material that you are allowed to store and redistribute in your own environment.
