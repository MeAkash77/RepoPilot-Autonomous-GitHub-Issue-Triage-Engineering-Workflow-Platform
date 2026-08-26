# GitHub App setup

RepoPilot authenticates as a **GitHub App** (not an OAuth app): per-installation tokens, fine-grained permissions, and webhook delivery with HMAC signatures.

## Permissions (least privilege — never widen these)

| Permission | Access | Why |
| --- | --- | --- |
| Issues | Read & write | Read issue content; apply labels, post comments |
| Contents | Read-only | Index README/docs/source for retrieval |
| Metadata | Read-only | Mandatory baseline |

No code write access, ever. See [SECURITY.md](SECURITY.md).

## Webhook events

Subscribe to: `installation`, `installation_repositories`, `issues`.

## Create the app (manual steps)

1. GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**.
2. Name: `repopilot-<yourname>` (names are global).
3. Webhook URL: `https://<your-api-host>/webhooks/github`
   (local dev: run `smee` or `ngrok` and point it at `http://localhost:8000/webhooks/github`).
4. Webhook secret: generate one — `openssl rand -hex 32` — and save it; this becomes `GITHUB_WEBHOOK_SECRET`.
5. Set permissions and events per the tables above.
6. "Where can this app be installed?" → Any account.
7. After creation: note the **App ID** (`GITHUB_APP_ID`), then **Generate a private key** and download the `.pem`.

## Environment

```bash
GITHUB_APP_ID=123456
# The downloaded PEM, inline with literal \n escapes; settings accept raw PEM text
GITHUB_APP_PRIVATE_KEY="<contents of the .pem>"
GITHUB_WEBHOOK_SECRET=<from step 4>
```

## Local webhook tunnel

```bash
# Option A: smee (free, no signup)
npx smee-client --url https://smee.io/<channel> --target http://localhost:8000/webhooks/github
# set the smee URL as the app's webhook URL

# Option B: ngrok
ngrok http 8000
```

## Verify the plumbing

1. `docker compose -f infra/docker-compose.yml up -d postgres redis`
2. Run migrations: `cd packages/core && uv run alembic upgrade head`
3. Start api + worker (two terminals):
   `uv run uvicorn repopilot_api.main:app --reload`
   `uv run arq repopilot_worker.main.WorkerSettings`
4. Install the app on a test repo → check `installations` and `repos` tables populate.
5. Open an issue on the test repo → worker logs `issues.triage_requested`.
