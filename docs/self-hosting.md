# Self-Hosting SpotiBye

## Why Self-Host?

Spotify allows 5 users total (including you) on an unapproved developer app ([quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)), and approval requires an already-large user base. Until a managed hosted option exists (which may be offered commercially later), each person runs their own Spotify app and backend. It takes about 15 minutes.

You will run two pieces locally:

- **Backend** — the Cloudflare Worker codebase, running on your machine via `wrangler dev` (no Cloudflare account needed; storage is emulated locally)
- **Frontend** — the Python desktop app, pointed at your local backend

## Prerequisites

- Python 3.10+ with `venv`
- Node 24 + npm (the repo pins this in `.nvmrc`)
- A Spotify account with an active Premium subscription (Spotify requires the app owner to hold Premium for Development Mode apps — the app stops working if it lapses)
- A Cloudflare account — only needed for the secondary Cloudflare-deploy path below

## Step 1 — Create a Spotify App (5 min)

Your Spotify account must hold an active **Premium** subscription — Spotify requires the app owner to have Premium for Development Mode apps, and the app stops working if it lapses.

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. **Create app**: give it a name (e.g. `SpotiBye-local`) and description, accept the terms.
3. Open the app's **Settings**, and under **Redirect URIs** add exactly:
   ```
   http://127.0.0.1:8080/callback
   ```
   Use the IP literal `127.0.0.1` — the backend allowlist includes this exact URI. Click **Add**, then **Save**.
4. On the same Settings page, copy your **Client ID** and **Client Secret**. Keep the secret private.
5. Allowlist yourself (and anyone sharing your backend): **Settings → Users and Access → Add new user**, entering each person's name and Spotify email. Only allowlisted accounts can authorize — anyone else gets an error from Spotify's API on login.

When you later log in through SpotiBye, Spotify asks you to approve read-only access (`user-read-private`, `user-read-email`, `playlist-read-private`, `playlist-read-collaborative`). The app cannot modify your playlists or see your password.

## Step 2 — Run the Backend Locally (5 min)

```bash
cd src/backend
npm install
cp .dev.vars.example .dev.vars
```

Edit `.dev.vars` and set the three values (this file is gitignored — never commit it):

```ini
SPOTIFY_CLIENT_ID="paste-from-spotify-dashboard"
SPOTIFY_CLIENT_SECRET="paste-from-spotify-dashboard"
JWT_SECRET="<output of: openssl rand -hex 32>"
```

Start it:

```bash
npm run dev
```

The backend serves at `http://localhost:8787` with KV storage and the analysis queue emulated on your machine.

## Step 3 — Run the Frontend (5 min)

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
spotibye
```

In the app's backend selector, choose the **Localhost** preset, then **Login with Spotify**. Your browser opens Spotify's authorization page for *your* app; approve it and return to SpotiBye. Your playlists load and exports work end to end.

## Guided Setup (Recommended)

The steps above can be driven by an interactive script that checks prerequisites, opens the right portal pages, validates your Spotify credentials before writing anything, and generates your local config:

```bash
python3 scripts/setup-selfhost.py
```

Useful flags:

- `python3 scripts/setup-selfhost.py --check` — verify prerequisites only.
- `python3 scripts/setup-selfhost.py --dry-run` — print what would happen without writing anything or opening browsers.
- `python3 scripts/setup-selfhost.py --force` — allow overwriting an existing `src/backend/.dev.vars`.

The script never prints secret values — prompts hide input, dry runs show redacted placeholders, and Cloudflare uploads pipe values via stdin. It currently automates the local path end to end (Spotify app credentials + `.dev.vars`); the Cloudflare helpers (KV provisioning, secret upload, per-user config generation) are implemented and tested but not yet wired into the interactive flow — follow the manual Cloudflare steps above for now.

## Secondary Path — Deploy the Backend to Cloudflare

If you would rather run the backend in the cloud (your own Worker instead of localhost):

Cloudflare's free tier covers personal use with room to spare (100,000 Worker requests/day, Workers KV and Queues included, no credit card required).

1. Create a Cloudflare account and log in locally (`wrangler login`), or create an API token with Workers deploy permissions and export it as `CLOUDFLARE_API_TOKEN`. Then follow [`dev-docs/guides/build-and-deploy-guide.md`](../dev-docs/guides/build-and-deploy-guide.md) for the full deploy reference.

All `wrangler` commands below run from `src/backend`:

```bash
cd src/backend
```

2. Provision your own KV namespaces (your Worker cannot use the IDs shipped in the repo's `wrangler.toml` — those belong to another account):
   ```bash
   wrangler kv namespace create CACHE_KV
   wrangler kv namespace create CACHE_KV --preview
   wrangler kv namespace create SESSIONS_KV
   wrangler kv namespace create SESSIONS_KV --preview
   ```
   Queues must be created explicitly — deploy fails without them:
   ```bash
   wrangler queues create spotibye-analysis
   wrangler queues create spotibye-analysis-dlq
   wrangler queues create spotibye-analysis-dev
   wrangler queues create spotibye-analysis-dev-dlq
   ```
3. Create your own config file: copy the tracked `src/backend/wrangler.toml` to `src/backend/wrangler.selfhost.toml` (gitignored — never edit the tracked file itself), replace every KV namespace ID occurrence with the new IDs from step 2 — `id` and `preview_id` for `CACHE_KV` and `SESSIONS_KV` in the top-level, `[env.development]`, and `[env.production]` blocks (12 slots, 4 distinct new IDs) — and set `ALLOWED_REDIRECT_URIS` in the `[env.production]` vars block — **not** the top-level `[vars]`, which only applies to deploys without `--env` — to include your frontend's exact callback URI, including the default `http://127.0.0.1:8080/callback` when the desktop app talks to your Worker. (`src/backend/routes/auth.ts` rejects any `redirect_uri` absent from that allowlist, and the shipped default only allows `https://app.spotibye.com`.)
4. Upload the three secrets against your config, scoped to your environment (replace `production` with `development` for a dev Worker). On a brand-new account, run the step-5 deploy once first so the Worker exists, then upload secrets:
   ```bash
   wrangler secret put SPOTIFY_CLIENT_ID --env production -c wrangler.selfhost.toml
   wrangler secret put SPOTIFY_CLIENT_SECRET --env production -c wrangler.selfhost.toml
   wrangler secret put JWT_SECRET --env production -c wrangler.selfhost.toml
   ```
5. Deploy with your config and point the frontend at the Worker URL:
   ```bash
   wrangler deploy -c wrangler.selfhost.toml --env production
   ```
   Then set `SPOTIBYE_BACKEND_URL` (or use the Custom backend option in the app's backend selector).

## Sharing Your Backend with Friends

A deployed Cloudflare backend — not localhost, which isn't reachable from another machine — can serve a small circle: each friend runs only the frontend and points it at your Worker URL. No backend setup on their side.

1. Deploy your Worker using the Cloudflare path above.
2. In your Spotify app's **Settings → Users and Access**, add each friend's name and Spotify email. The 5-user Development Mode cap (including you) applies per app, so this covers up to 4 friends.
3. Keep the loopback callback (`http://127.0.0.1:8080/callback`) in both your Spotify app settings and your `ALLOWED_REDIRECT_URIS` — friends run the frontend locally, so their OAuth flow uses the same local callback.
4. Share your Worker URL. Each friend sets `SPOTIBYE_BACKEND_URL` to it (or uses the Custom backend option), then logs in with Spotify as usual.

Trust note: your friends' Spotify tokens live in *your* backend's storage — share only with people you trust.

## Troubleshooting

- **Backend port busy (`http://localhost:8787`)** — another `wrangler dev` (or another app) is already on 8787. Stop it, or run `npx wrangler dev --port 8788` from `src/backend` and launch the frontend with `export SPOTIBYE_LOCALHOST_BACKEND_URL=http://localhost:8788` so the Localhost preset points at the new port.
- **OAuth callback port busy (`:8080`)** — the frontend's local callback server needs port 8080. Free it, or set `SPOTIBYE_OAUTH_PORT` — but then you must also register the matching URI in Spotify's dashboard *and* in the backend allowlist.
- **`DISALLOWED_REDIRECT_URI`** — the callback URI sent at login isn't in the backend's `ALLOWED_REDIRECT_URIS` (the `ALLOWED_REDIRECT_URIS` vars in `wrangler.toml` locally, your `wrangler.selfhost.toml` on Cloudflare). Compare the exact strings: Spotify dashboard entry vs backend value. Scheme, host, port, and path must all match.
- **Login loops back to Spotify** — stale browser tokens from a previous app conflict with the new one. Clear site data for Spotify or use an incognito window.
- **Expired or revoked secrets** — a rotated Spotify Client Secret or revoked Cloudflare token fails with auth errors on next use. Re-copy the value into `.dev.vars` (local) or re-run `wrangler secret put` (Cloudflare) and restart/redeploy.
- **`wrangler dev` behaving oddly** — local emulation state can go stale. Stop it, delete `.wrangler/` under `src/backend`, and restart.

## Commercial Hosting

A managed hosted version of SpotiBye may be offered later, which would remove the need to register your own Spotify app. Until then, self-hosting above is the supported path.
