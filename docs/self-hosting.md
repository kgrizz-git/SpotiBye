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

## Secondary Path — Deploy the Backend to Cloudflare

If you would rather run the backend in the cloud (your own Worker instead of localhost):

Cloudflare's free tier covers personal use with room to spare (100,000 Worker requests/day, Workers KV and Queues included, no credit card required).

1. Create a Cloudflare account and API token, then follow [`dev-docs/guides/build-and-deploy-guide.md`](../dev-docs/guides/build-and-deploy-guide.md).
2. Set the Worker secrets (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `JWT_SECRET`) via `wrangler secret put`.
3. Configure `ALLOWED_REDIRECT_URIS` for your environment **before** deploying: `src/backend/routes/auth.ts` rejects any `redirect_uri` not present in that allowlist, so it must contain your frontend's exact callback URI — including the default `http://127.0.0.1:8080/callback` when the desktop app talks to your Worker. (The shipped production default only allows `https://app.spotibye.com`.) This is a `wrangler.toml` `[vars]` value, not a secret — set it in the `[env.production]` vars, not via `wrangler secret put`.
4. Point the frontend at your Worker URL: set `SPOTIBYE_BACKEND_URL` (or use the Custom backend option in the app's backend selector).

## Commercial Hosting

A managed hosted version of SpotiBye may be offered later, which would remove the need to register your own Spotify app. Until then, self-hosting above is the supported path.
