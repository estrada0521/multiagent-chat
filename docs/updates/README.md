# Release Notes / 更新履歴

This folder collects milestone update notes that can be linked from the README.
このフォルダには、README からリンクする節目ごとの更新ノートを置いています。

- [beta 1.0.7](beta-1.0.7.md)
- [beta 1.0.7 日本語](beta-1.0.7.ja.md)
- [beta 1.0.6](beta-1.0.6.md)
- [beta 1.0.6 日本語](beta-1.0.6.ja.md)
- [beta 1.0.5](beta-1.0.5.md)
- [beta 1.0.5 日本語](beta-1.0.5.ja.md)
- [beta 1.0.4](beta-1.0.4.md)
- [beta 1.0.4 日本語](beta-1.0.4.ja.md)
- [beta 1.0.3](beta-1.0.3.md)
- [beta 1.0.3 日本語](beta-1.0.3.ja.md)
- [beta 1.0.2](beta-1.0.2.md)
- [beta 1.0.2 日本語](beta-1.0.2.ja.md)
- [beta 1.0.1](beta-1.0.1.md)
- [beta 1.0.1 日本語](beta-1.0.1.ja.md)

## Publishing GitHub Releases / GitHub Release 公開手順

Use `bin/multiagent-release` to publish a GitHub Release from these notes.
このノート群から GitHub Release を公開するには `bin/multiagent-release` を使います。

Example / 例:

```bash
bin/multiagent-release 1.0.7 --create-tag
```

Default mapping:

- tag: `beta-<version>`
- notes file: `docs/updates/beta-<version>.md`

The repository also includes `.github/workflows/publish-release.yml`, which publishes releases automatically on `beta-*` tag push and can be run manually with `workflow_dispatch`.
