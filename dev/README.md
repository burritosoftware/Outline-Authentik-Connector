# Dev stack

End-to-end test environment: real Authentik + real Outline + the connector, all wired together in docker compose. Exists so reviewers can verify the webhook + group-sync flow without standing up cloud infra.

## What you get

- Authentik on `http://localhost:9000` — login `akadmin` / `akadmin`
- Outline on `http://localhost:3000` — sign in via "Continue with Authentik (dev)"; the first OIDC user becomes admin
- Connector on `https://localhost:8430/sync` — addressable from inside the compose network as `https://oa-connector.internal:8443/sync`

Authentik is provisioned via blueprint with three groups (`outline-admins`, `outline-editors`, `unrelated-team`), three users (`alice`/`bob`/`carol`), an OIDC application for Outline, and a service-account token the connector uses.

## Bring it up

```sh
cd dev
./setup.sh            # generates self-signed cert, creates .env
docker compose up -d
```

The connector container will restart-loop until you complete steps 1–4 below — that's the M3 startup-validation fix refusing to run with an empty `OUTLINE_WEBHOOK_SECRET`.

## Wire Outline → connector

Outline rejects webhook URLs that aren't HTTPS, so the connector listens on HTTPS with a self-signed cert. Outline is launched with `NODE_TLS_REJECT_UNAUTHORIZED=0` so it trusts that cert for this dev stack. Never set that in production.

1. **Sign into Outline** at `http://localhost:3000` via "Continue with Authentik (dev)". Use `alice` / `alice-dev` — first user becomes admin.
2. **Create an Outline API key**: profile (bottom-left) → Preferences → API Keys → "New API Key…". Copy it.
3. **Create the webhook**: Preferences → Webhooks → "New webhook…". URL: `https://oa-connector.internal:8443/sync`. Tick `users.signin`. Save. Copy the signing secret.
4. **Drop both into `.env`** and recreate the connector:
   ```sh
   # edit .env, then:
   docker compose up -d --force-recreate oa-connector
   ```
5. **Watch the log**: `docker compose logs -f oa-connector` — it should stop restart-looping.

## What to verify

Once the connector is running, sign each user in and observe:

| User | Authentik groups | Connector behavior | Expected Outline groups for user |
|---|---|---|---|
| `alice` | `outline-admins`, `outline-editors` | auto-creates both groups, adds alice | `outline-admins`, `outline-editors` |
| `bob` | `outline-editors`, `unrelated-team` | adds to `outline-editors` only — `unrelated-team` excluded by `SYNC_GROUP_REGEX=^outline-.*` | `outline-editors` |
| `carol` | (none) | logs `Got 0 groups`, no group ops | (none) |

### B1 destructive-default demo

1. Sign in alice. Confirm she's in `outline-admins` + `outline-editors` in Outline.
2. In Outline UI, create a group called `manual-only` and add alice. This is "operator-managed state outside the connector's scope."
3. Sign alice out and back in. With `SYNC_GROUP_REGEX=^outline-.*` set, `manual-only` survives — the regex scopes sync to a prefix the connector owns.
4. To prove the footgun without the regex: stop the connector, blank `SYNC_GROUP_REGEX` in `docker-compose.yml`, recreate the connector, sign alice in again. `manual-only` is silently removed because alice isn't in any Authentik group of that name.

### Force-test the security fixes

```sh
SECRET=$(grep ^OUTLINE_WEBHOOK_SECRET .env | cut -d= -f2-)

# H1: stale timestamp → 401 stale-timestamp
SIG=$(echo -n "1700000000.{}" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -k -s -o /dev/stderr -w 'HTTP %{http_code}\n' \
  -X POST -H "outline-signature: t=1700000000,s=$SIG" -d '{}' \
  https://localhost:8430/sync

# H3: malformed signature header → 400 invalid-signature
curl -k -s -o /dev/stderr -w 'HTTP %{http_code}\n' \
  -X POST -H "outline-signature: garbage" -d '{}' \
  https://localhost:8430/sync

# H4: oversized body → 413 body-too-large
head -c 2000000 </dev/zero | base64 | curl -k -s -o /dev/stderr -w 'HTTP %{http_code}\n' \
  -X POST --data-binary @- \
  https://localhost:8430/sync

# M3: empty secret refuses startup (proven on first `docker compose up -d`)
```

## Tear down

```sh
docker compose down -v   # -v also removes pgdata/redisdata/etc — wipes state
```

## Files

- `docker-compose.yml` — the full stack
- `authentik-blueprints/dev.yaml` — groups, users, OIDC for Outline, connector service account
- `setup.sh` — generates self-signed cert and seeds `.env` (idempotent)
- `.env.example` — template; `.env` is gitignored
- `certs/` — generated self-signed cert; gitignored

## Caveats

- `NODE_TLS_REJECT_UNAUTHORIZED=0` is dev-only. Real deployments terminate TLS at a reverse proxy with a real cert.
- Outline image is pinned to `0.81.1`. Bump deliberately if you want to test against a newer Outline.
- Authentik image is pinned to `2024.12.3`. Same applies.
