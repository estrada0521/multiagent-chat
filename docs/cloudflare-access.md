# Cloudflare Access for Public Hub

This repo can require Cloudflare Access in front of the named public hostname without changing the local Hub/chat path.

## What this protects

- Public Hub: `https://hub.example.com/`（ここは **自分のパブリック用ホスト名** に読み替える）
- Public chat under `/session/<name>/...`

Local URLs stay unchanged:

- `https://127.0.0.1:8788/`
- `https://127.0.0.1:8226/?follow=1` or the session-specific local chat port

## 1. Create the Access app in Cloudflare

In Cloudflare Zero Trust:

1. Go to `Access` -> `Applications`
2. Create a `Self-hosted` application
3. Set the application domain to:

```text
hub.example.com
```

（Cloudflare Access に登録する **FQDN** と、named tunnel で公開しているホスト名を一致させる）

4. Add an allow policy for your own identity

Recommended first pass:

- Action: `Allow`
- Selector: your email address

For easier day-to-day use on your own Mac/iPhone:

- Set a long session duration such as `30 days`
- Use the same browser on each device so the Access cookie persists

## 2. Copy the Access audience value

Open the Access application you created and copy its `AUD` / audience tag.

You also need your Zero Trust team name.

If your Zero Trust URL is something like:

```text
https://example.cloudflareaccess.com
```

then the team name is:

```text
example
```

## 3. Apply it to the named tunnel config

Run:

```sh
bin/multiagent-cloudflare access-enable <team-name> <aud-tag>
```

Example:

```sh
bin/multiagent-cloudflare access-enable example 01234567-89ab-cdef-0123-456789abcdef
```

This writes:

- `logs/cloudflare/access.json`
- `logs/cloudflare/config.yml`

and injects the Cloudflare Access requirement into the named tunnel origin config.

## 4. Restart the named tunnel

Run:

```sh
bin/multiagent-cloudflare named-start
```

## 5. Check status

Run:

```sh
bin/multiagent-cloudflare status
```

You should see:

- `access_enabled=yes`
- `access_team_name=...`
- `access_aud_tag=...`

## Disable Access requirement

```sh
bin/multiagent-cloudflare access-disable
bin/multiagent-cloudflare named-start
```

This only affects the public named tunnel path. Local Hub/chat are not changed.
