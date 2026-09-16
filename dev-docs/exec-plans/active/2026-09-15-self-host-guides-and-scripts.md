# Plan: Complete Self-Host Guides and Setup Scripting

**Status:** draft — not yet executed
**Branch:** `feat/self-host-guides-and-scripts`
**Created:** 2026-09-15
**Motivation:** Spotify limits unapproved developer apps to a small number of users, so self-hosting is the supported path until a managed hosted option exists. `docs/self-hosting.md` covers the local path end to end, but the Cloudflare path is a pointer, Spotify-app details are thin, and the interactive setup script from `dev-docs/backlog/TO_DO.md` does not exist yet.

**Ground facts (verified 2026-09-15):**
- OAuth scopes requested: `user-read-private`, `user-read-email`, `playlist-read-private`, `playlist-read-collaborative` (`src/backend/services/spotify-auth.ts:23-28`) — read-only, no playlist modification.
- Local callback: `http://127.0.0.1:8080/callback` (frontend builds it; backend allowlists it).
- Backend required bindings: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `JWT_SECRET`, `ALLOWED_REDIRECT_URIS` (`src/backend/validation/schemas/env.ts`).
- Frontend backend selection already documented in `docs/configuration-options.md` ("Choose a backend").
- Related backlog items: "Consider releasing as public open-source…" sub-items in `dev-docs/backlog/TO_DO.md` (Cloudflare setup, Spotify registration, env/secrets guide, frontend config, hosted-option evaluation, interactive setup script).

---

## Phase 1 — Guide gaps (docs only)

- [ ] Spotify app registration detail: exact Redirect URI per mode (local loopback vs deployed Worker URL), where to find Client ID/Secret, and the read-only scope list above so users know what they are approving.
- [ ] Cloudflare deploy path: expand beyond the pointer — account + API token permissions; provisioning via wrangler (`wrangler kv:namespace create` incl. `--preview`, queue creation) *before* deploy; `wrangler secret put` for the three secrets (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `JWT_SECRET`); `ALLOWED_REDIRECT_URIS` per environment uploaded as a secret override (a secret shadows the committed `[vars]` value, so the tracked `wrangler.toml` is never modified); deploy commands for dev vs prod.
- [ ] Frontend configuration: verify `docs/configuration-options.md` covers everything a self-hoster needs (backend URL env vars, Localhost/Custom presets); fill gaps and cross-link from `docs/self-hosting.md`.
- [ ] Self-host troubleshooting section with explicit per-port entries — backend `http://localhost:8787` conflicts, OAuth callback `:8080` conflicts — plus `DISALLOWED_REDIRECT_URI` (allowlist vs Spotify dashboard mismatch), expired/revoked secrets, `wrangler dev` local-state reset, and OAuth login loops (stale browser tokens vs newly registered app — clear cache or use incognito).
- [ ] Shared-backend-for-friends guide (Cloudflare path required — a localhost backend is not reachable from another machine):
  - [ ] Host: deploy the Worker, share the backend URL; friends point their frontend at it via `SPOTIBYE_BACKEND_URL` or the Custom backend option — no backend setup on their side.
  - [ ] Spotify user cap still applies per app: the host must add each friend's Spotify account email under the Spotify app's User Management. Working hypothesis per Spotify docs is 25 total including the owner — re-confirm the current limit during execution and state the verified number.
  - [ ] Redirect URIs: friends run the frontend locally, so the loopback callback (`http://127.0.0.1:8080/callback`) must be covered — upload it as an `ALLOWED_REDIRECT_URIS` secret override on the host's Worker (shadows the shipped `https://app.spotibye.com` production default without touching tracked `wrangler.toml`), alongside the Spotify app settings entry.
  - [ ] Trust note: friends' Spotify tokens live in the host's backend storage — share only with people you trust.
- [ ] Update `docs/index.md` and README links for any new pages.

## Phase 2 — Interactive setup script

Goal: a user who wants to run the backend registers their own Spotify app and gets everything running with the script doing as much as possible, as simply as possible. Manual steps are the fallback, not the default.

- [ ] Design the UX: prompted flow (no args needed for the happy path), `--dry-run` / `--check` mode, per-step validation with actionable errors, never echoes secrets.
- [ ] Simplicity requirements (non-negotiable for this phase):
  - [ ] Prerequisite check first: Python/Node versions, `npm`, `wrangler`, network reachability — one summary, copy-pasteable fixes.
  - [ ] Open each portal page automatically (`webbrowser` module) instead of pasting URLs for the user to open.
  - [ ] Sensible defaults everywhere (ports, redirect URI, env names); prompt only for values the script cannot know (Client ID/Secret, choices with a recommended default).
  - [ ] Validate each input immediately (format checks + live smoke checks where possible) so a typo fails fast at the right step, not at first launch.
  - [ ] End-to-end success check: backend responds on localhost, frontend entry point resolves, OAuth callback URL is reachable — print a final "you're ready, run X" summary.
- [ ] Implement (Python, stdlib only, lives in `scripts/`):
  - [ ] Open Spotify/Cloudflare portal URLs and collect credentials.
  - [ ] Validate credentials before writing anything (Spotify: auth URL construction/smoke check; Cloudflare: `wrangler whoami`-equivalent token check).
  - [ ] Provision Cloudflare resources via wrangler before deploy (KV namespaces incl. `--preview`, analysis queue); fail with actionable errors if provisioning fails.
  - [ ] Generate `src/backend/.dev.vars` from the existing `src/backend/.dev.vars.example` template (local path). Never template or modify the tracked `wrangler.toml` — committed KV/queue/DO bindings must survive untouched.
  - [ ] For the Cloudflare path, upload credentials programmatically via subprocess piping into `wrangler secret put <KEY>` (three secrets, plus `ALLOWED_REDIRECT_URIS` as a secret override when the user needs a custom callback URI) so no manual secret upload is required.
  - [ ] Refuse to overwrite an existing `.dev.vars` without `--force`; assert `.dev.vars` is gitignored (verify, don't assume) and ensure generated files stay gitignored.
- [ ] Add tests for the script (arg parsing, validation, file generation with temp dirs, no-secret-leak assertions).
- [ ] Wire into docs (`docs/self-hosting.md`, `docs/index.md`) and repo hooks if appropriate (never as a required gate).

## Phase 3 — Verify and ship

- [ ] Fresh-machine walkthrough of the full guide (or checklist review if no spare machine): local path end to end, Cloudflare path at least to a successful `wrangler deploy`.
- [ ] Full verification: `./scripts/verify-all.sh` from repo root (plus pre-push hooks on commit).
- [ ] Two-reviewer pass (kilo stepfun free + agy gemini high) before opening the PR, per repo practice for user-facing changes.
- [ ] Open PR (one logical change; split guide vs script into two PRs if the diff exceeds ~400 lines).
- [ ] On merge, check off the corresponding `dev-docs/backlog/TO_DO.md` sub-items.

---

## Out of scope

- Managed/commercial hosting itself (separate decision; tracked in backlog).
- Spotify quota-extension application process.
- README screenshots (separate tracked item).
