# Deployment guide — Oracle Cloud + Neon + Upstash + Vercel

**All free, forever. No credit card charged for compute.**

| Service | What runs there | Cost |
|---|---|---|
| **Oracle Cloud** | API + Worker VMs (Arm A1 — 4 OCPU, 24 GB RAM total) | Free always |
| **Neon** | Postgres 16 + pgvector | Free (0.5 GB) |
| **Upstash** | Redis | Free (10 k commands/day) |
| **Vercel** | Next.js web app | Free (hobby) |
| **Langfuse** | Observability / tracing | Free |

Total time: ~60 minutes.

---

## Step 1 — Oracle Cloud account

1. Go to **https://cloud.oracle.com** → click **Start for free**.
2. Fill in name, email, password.
3. **Home Region** — pick one of these (Always Free capacity is most available here):
   - `US East (Ashburn)` ← best availability
   - `US West (Phoenix)`
   - `Germany Central (Frankfurt)`
   > You **cannot change your home region later**. Pick wisely.
4. Verify your email → continue.
5. Enter address and phone number for identity verification.
6. **Add Payment Verification Method**: add a credit card.
   > Oracle **does not charge** for Always Free resources. The card is identity verification only — no charge, no hold.
7. Click **Complete Sign-Up**. Wait ~2 minutes for provisioning.
8. You land on the **OCI Console** dashboard.

---

## Step 2 — Create a VCN (Virtual Cloud Network)

Your VMs need a VCN with a public subnet to be reachable from the internet.

1. In the OCI Console search bar (top centre), type **VCN** → click **Virtual Cloud Networks**.
2. Click **Start VCN Wizard**.
3. Select **Create VCN with Internet Connectivity** → click **Start VCN Wizard**.
4. Fill in:
   - **VCN name**: `repopilot-vcn`
   - Leave all CIDR blocks as default (`10.0.0.0/16`)
5. Click **Next** → review → click **Create**.
6. Wait ~30 seconds → click **View VCN**.

### Open port 8000 (API) in the security list

1. On the VCN page, click **Public Subnet-repopilot-vcn** in the Subnets list.
2. Click the Security List link (e.g. `Default Security List for repopilot-vcn`).
3. Click **Add Ingress Rules**.
4. Add this rule:
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: **TCP**
   - Destination Port Range: `8000`
   - Description: `RepoPilot API`
5. Click **Add Ingress Rules**.

---

## Step 3 — Create the API VM

1. Click **≡ hamburger menu** (top-left) → **Compute** → **Instances**.
2. Click **Create instance**.
3. **Name**: `repopilot-api`
4. **Image and shape** → click **Edit**:
   - Under **Image**: click **Change image** → select **Canonical Ubuntu** → version **22.04** → click **Select image**.
   - Under **Shape**: click **Change shape** → select the **Ampere** tab → select **VM.Standard.A1.Flex** → set:
     - OCPUs: **2**
     - Memory: **12 GB**
   - Click **Select shape**.
5. **Networking**:
   - VCN: `repopilot-vcn`
   - Subnet: `Public Subnet-repopilot-vcn`
   - **Assign a public IPv4 address**: ✓ (must be enabled)
6. **Add SSH keys**:
   - Select **Generate a key pair for me**
   - Click **Save private key** — a `.key` file downloads
   - Move it: `mv ~/Downloads/ssh-key-*.key ~/.ssh/repopilot.key && chmod 600 ~/.ssh/repopilot.key`
7. Click **Create**.

Wait ~2 minutes. Status goes `PROVISIONING` → `RUNNING`.

8. On the instance detail page, copy the **Public IP address** (e.g. `132.226.x.x`). Call this `API_VM_IP`.

> **If creation fails with "Out of host capacity"**: Oracle has capacity limits per region. Wait 5 minutes and retry. Or change the **Availability Domain** (try AD-2 or AD-3 in the Placement section).

---

## Step 4 — Create the Worker VM

Repeat Step 3 with these differences:
- **Name**: `repopilot-worker`
- Shape: same `VM.Standard.A1.Flex`, **2 OCPU / 12 GB**
- SSH keys: click **Upload public key files** → upload the `.pub` file that accompanied your API key (same file, just `.pub` extension), OR generate a new pair

Copy the Worker VM's **Public IP** → call this `WORKER_VM_IP`.

> The worker runs no HTTP server so port 8000 does not need to be open for it.

---

## Step 5 — Neon (Postgres + pgvector)

1. Go to **https://neon.tech** → **Sign Up** (GitHub login works).
2. Click **New Project**:
   - Name: `repopilot`
   - Region: closest to your Oracle region (`us-east-1` for Ashburn)
   - Postgres version: **16**
3. Click **Create Project**.
4. On the project dashboard → click **Connection Details** (top right).
5. Change the dropdown to **Connection string**.
6. Copy the string — looks like:
   ```
   postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
7. Change the scheme for asyncpg:
   ```
   postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?ssl=require
   ```
   Save this as **`DATABASE_URL`** (direct connection — use for Alembic migrations).

8. For the **runtime** `DATABASE_URL` (API + worker), use the **pooled** connection string instead. In Neon dashboard → Connection Details → toggle **"Pooled"** → copy the `-pooler` host:
   ```
   postgresql+asyncpg://user:pass@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?ssl=require
   ```
   Set this as `DATABASE_URL` on Fly.io (`flyctl secrets set DATABASE_URL="..." --app repopilot-api`). The pooler handles connection bursting under load without exhausting Neon's connection limit.
8. In left sidebar → **SQL Editor** → run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   Click **Run**. Should show `CREATE EXTENSION`.

---

## Step 6 — Upstash (Redis)

1. Go to **https://upstash.com** → **Sign Up** (GitHub login works).
2. Click **Create Database**:
   - Name: `repopilot`
   - Type: **Regional**
   - Region: closest to your Oracle region (`us-east-1` for Ashburn)
   - Enable **TLS** ✓
3. Click **Create**.
4. On the database page → click **Details** tab → copy the **Redis URL**:
   ```
   rediss://default:TOKEN@xxx.upstash.io:6379
   ```
   Save as **`REDIS_URL`**.

---

## Step 7 — Langfuse (optional but recommended)

1. Go to **https://cloud.langfuse.com** → **Sign Up**.
2. Click **New Project** → name `repopilot` → **Create**.
3. **Settings → API Keys → Create new API key**.
4. Copy:
   - Public Key → `LANGFUSE_PUBLIC_KEY`
   - Secret Key → `LANGFUSE_SECRET_KEY`
   - Host stays `https://cloud.langfuse.com` → `LANGFUSE_HOST`

---

## Step 8 — Generate shared secrets (local machine)

```bash
openssl rand -hex 32   # → INTERNAL_API_KEY
openssl rand -hex 32   # → GITHUB_WEBHOOK_SECRET
```

Save both values. You need them in Steps 9, 10, and 12.

---

## Step 9 — Set up the API VM

SSH in from your local machine:

```bash
ssh -i ~/.ssh/repopilot.key ubuntu@API_VM_IP
```

### 9a. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker ubuntu
newgrp docker
```

Verify:
```bash
docker run hello-world
```

### 9b. Open port 8000 in the OS firewall

Oracle VMs have an iptables rule that blocks incoming ports by default — the OCI security list alone is not enough.

```bash
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

### 9c. Clone the repo

```bash
git clone https://github.com/AyushCoder9/RepoPilot.git
cd RepoPilot
```

### 9d. Create the env file

```bash
nano .env
```

Paste and fill in all values:

```
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?ssl=require
REDIS_URL=rediss://default:token@xxx.upstash.io:6379
INTERNAL_API_KEY=<your-32-byte-hex-from-step-8>
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=<your-32-byte-hex-from-step-8>
GROQ_API_KEY=
GOOGLE_API_KEY=
COHERE_API_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
MAX_COST_PER_RUN_USD=0.02
MAX_RUNS_PER_INSTALL_PER_DAY=500
WEB_ORIGIN=https://your-app.vercel.app
```

(Leave `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY` blank for now — you fill them after Step 12.)

Save: `Ctrl+O` → Enter → `Ctrl+X`.

### 9e. Build and start the API container

```bash
docker build -f infra/Dockerfile.api -t repopilot-api .
docker run -d \
  --name repopilot-api \
  --restart unless-stopped \
  --env-file .env \
  -p 8000:8000 \
  repopilot-api
```

Verify locally on the VM:
```bash
curl http://localhost:8000/healthz
# → {"status":"ok"}
```

Verify from your laptop:
```bash
curl http://API_VM_IP:8000/healthz
# → {"status":"ok"}
```

### 9f. Auto-start on VM reboot

```bash
sudo tee /etc/systemd/system/repopilot-api.service > /dev/null << 'EOF'
[Unit]
Description=RepoPilot API
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker start -a repopilot-api
ExecStop=/usr/bin/docker stop repopilot-api

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable repopilot-api
```

---

## Step 10 — Set up the Worker VM

Open a new terminal on your local machine and SSH in:

```bash
ssh -i ~/.ssh/repopilot.key ubuntu@WORKER_VM_IP
```

Run the **exact same Docker install commands** from Step 9a.

Then:

```bash
git clone https://github.com/AyushCoder9/RepoPilot.git
cd RepoPilot
nano .env
```

Paste (worker doesn't need `INTERNAL_API_KEY`, `GITHUB_WEBHOOK_SECRET`, or `WEB_ORIGIN`):

```
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?ssl=require
REDIS_URL=rediss://default:token@xxx.upstash.io:6379
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GROQ_API_KEY=
GOOGLE_API_KEY=
COHERE_API_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
MAX_COST_PER_RUN_USD=0.02
```

Save and exit. Build and run:

```bash
docker build -f infra/Dockerfile.worker -t repopilot-worker .
docker run -d \
  --name repopilot-worker \
  --restart unless-stopped \
  --env-file .env \
  repopilot-worker
```

Verify it started:
```bash
docker logs repopilot-worker --tail 20
# should show: "Starting arq worker for WorkerSettings"
```

Auto-start on reboot:
```bash
sudo tee /etc/systemd/system/repopilot-worker.service > /dev/null << 'EOF'
[Unit]
Description=RepoPilot Worker
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker start -a repopilot-worker
ExecStop=/usr/bin/docker stop repopilot-worker

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable repopilot-worker
```

---

## Step 11 — Run database migrations

On your **local machine** (not the VM):

```bash
cd packages/core

DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?ssl=require" \
  uv run alembic upgrade head
```

Expected:
```
Running upgrade  -> 0001, phase1 tables
Running upgrade 0001 -> 0002, knowledge corpus
Running upgrade 0002 -> 0003, triage runs
Running upgrade 0003 -> 0004, proposed actions and feedback
```

Verify:
```bash
DATABASE_URL="postgresql+asyncpg://..." uv run alembic current
# → 0004 (head)
```

> **Migration fails?** Neon free tier routes through a pooler by default. For Alembic, use the **direct (unpooled)** connection string: Neon dashboard → Connection Details → toggle **"Pooled"** to **"Direct"** → copy that URL → use it only for migrations.

---

## Step 12 — Create the GitHub App

> If you created a GitHub App during local dev, just update the Webhook URL to your Oracle VM IP and skip to **12b**.

### 12a. Create the app

1. Go to **https://github.com/settings/apps/new**
2. Fill in:
   - **GitHub App name**: `repopilot-gh`
   - **Homepage URL**: `http://API_VM_IP:8000`
   - **Webhook URL**: `http://API_VM_IP:8000/webhooks/github`
   - **Webhook secret**: paste your `GITHUB_WEBHOOK_SECRET` from Step 8
3. **Repository permissions**:
   - Issues → **Read & Write**
   - Contents → **Read**
   - Metadata → **Read** (auto-selected)
   - Pull requests → **Read**
4. **Subscribe to events**: check **Issues**
5. **Where can this be installed**: **Any account**
6. Click **Create GitHub App**

### 12b. Get credentials

On the app settings page:
- **App ID** (shown near the top) → `GITHUB_APP_ID`
- Scroll to **Private keys** → click **Generate a private key** → a `.pem` file downloads
- **Client ID** (OAuth section) → `AUTH_GITHUB_ID`
- Click **Generate a new client secret** → `AUTH_GITHUB_SECRET`

### 12c. Add credentials to the VMs

On the **API VM**:
```bash
nano .env
# fill GITHUB_APP_ID= with the number from step 12b
# fill GITHUB_APP_PRIVATE_KEY= with the full PEM file contents
# (header line + base64 body + footer line — copy from the downloaded .pem)
docker restart repopilot-api
```

On the **Worker VM**:
```bash
nano .env
# same: fill GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY
docker restart repopilot-worker
```

---

## Step 13 — Deploy Next.js to Vercel

### 13a. Import the repo

1. Go to **https://vercel.com** → **Add New → Project**
2. Click **Import Git Repository** → find and select `AyushCoder9/RepoPilot`
3. **Configure Project**:
   - Click **Edit** next to Root Directory → type `apps/web` → **Continue**
   - Framework: auto-detected as **Next.js** ✓
4. **Environment Variables** — add all of these before clicking Deploy:

   | Key | Value |
   |---|---|
   | `AUTH_GITHUB_ID` | Client ID from Step 12b |
   | `AUTH_GITHUB_SECRET` | Client secret from Step 12b |
   | `AUTH_SECRET` | run `openssl rand -hex 32` locally and paste here |
   | `INTERNAL_API_KEY` | same value as Step 8 |
   | `API_URL` | `http://API_VM_IP:8000` |

5. Click **Deploy**. Takes ~2 minutes.
6. Copy your deployment URL: `https://repopilot-xxx.vercel.app`

### 13b. Update GitHub App callback URL

1. Go back to your GitHub App settings page
2. Find the **Callback URL** field → set it to:
   ```
   https://your-app.vercel.app/api/auth/callback/github
   ```
3. Click **Save changes**

### 13c. Update WEB_ORIGIN on the API VM

```bash
# on the API VM:
nano .env
# set: WEB_ORIGIN=https://your-app.vercel.app
docker restart repopilot-api
```

---

## Step 14 — GitHub Actions CI/CD (auto-deploy on merge)

1. Go to your GitHub repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret** for each:

   | Secret | Value |
   |---|---|
   | `ORACLE_API_VM_IP` | your API VM public IP |
   | `ORACLE_WORKER_VM_IP` | your Worker VM public IP |
   | `ORACLE_SSH_KEY` | full contents of `~/.ssh/repopilot.key` (the private key) |
   | `NEON_DATABASE_URL` | your `DATABASE_URL` value |

3. Click **New repository variable** (not secret):

   | Variable | Value |
   |---|---|
   | `DEPLOY_ENABLED` | `true` |

The deploy workflow (`.github/workflows/deploy.yml`) SSHes into each VM, pulls latest code, and rebuilds the Docker image. Triggers only on successful CI on `main`.

---

## Step 15 — Smoke test

```bash
# 1. API health
curl http://API_VM_IP:8000/healthz
# → {"status":"ok"}

# 2. DB + Redis connected
curl http://API_VM_IP:8000/readyz
# → {"status":"ok"}

# 3. Sign in to the web app
open https://your-app.vercel.app
# Click "sign in" → GitHub OAuth → lands on /dashboard

# 4. Install the GitHub App on a test repo
open https://github.com/apps/repopilot-gh/installations/new

# 5. Open a GitHub issue on that repo
# Dashboard → Runs → new entry appears within ~5 seconds
# Worker logs: ssh into worker VM → docker logs repopilot-worker -f
```

---

## VM specs

| VM | Shape | OCPU | RAM | Port open | Cost |
|---|---|---|---|---|---|
| `repopilot-api` | VM.Standard.A1.Flex | 2 | 12 GB | 8000 | **$0** |
| `repopilot-worker` | VM.Standard.A1.Flex | 2 | 12 GB | none | **$0** |

Oracle Always Free gives **4 OCPU + 24 GB RAM** Arm compute per account, permanently.

---

## Troubleshooting

**VM creation: "Out of host capacity"**
Wait 5–10 minutes, retry. Or change Availability Domain (AD-2, AD-3) in the Placement section. US East Ashburn has the most free capacity.

**`curl http://API_VM_IP:8000` times out even though OCI security list is open**
Oracle VMs have a second firewall (iptables). Run on the API VM:
```bash
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save
```

**Worker not picking up jobs**
```bash
docker logs repopilot-worker -f
# should show "Starting arq worker" — if absent, check REDIS_URL in .env
```

**Webhook delivery failing**
GitHub App settings → **Advanced** tab → **Recent Deliveries** → check response body.
```bash
docker logs repopilot-api -f | grep webhook
```

**Migration error: extension "vector" does not exist**
Run in Neon SQL Editor:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Migration error: connection refused / timeout**
Use the direct (unpooled) connection string from Neon for Alembic only.

**`GITHUB_APP_PRIVATE_KEY` multiline in .env**
Paste the full PEM block (header line, base64 body, footer line) into the `.env` file using `nano`. The downloaded `.pem` file contains everything you need — open it in a text editor, copy all lines, and paste into `.env`.
