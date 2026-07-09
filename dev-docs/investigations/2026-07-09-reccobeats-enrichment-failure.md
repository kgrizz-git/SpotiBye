# ReccoBeats Enrichment Failure — Empty Audio Features on Playlist Analysis

**Date:** 2026-07-09
**Status:** Open — investigation, not yet root-caused
**Related:** [`2026-07-05-reccobeats-enrichment-gaps.md`](2026-07-05-reccobeats-enrichment-gaps.md) (original audit; all display/aggregation gaps there are closed, but the upstream-service-reliability question was out of scope and is what this doc covers). Also relevant: [`../reccobeats-api-contract.md`](../reccobeats-api-contract.md) (verified 2026-06-19, "no auth required").

## Context

The ReccoBeats enrichment integration is fully and correctly implemented in both the backend (`src/backend/services/analysis.ts`) and the frontend popup (`src/frontend/ui/backend_playlist_card.py`). Despite that, a user running playlist analysis on the **development** backend saw no audio-feature data at all. This doc records the symptoms, what was verified, and the leading hypotheses for why the upstream ReccoBeats calls are not producing data.

## Symptoms

- Playlist analyzed: `03YbVT4UhOxLrOAcpyCEqT` on `spotibye-backend-development.kevin-grizzard.workers.dev`.
- Popup shows partial-data banners:
  - `Partial data: audio features unavailable`
  - `Partial data: track metadata unavailable`
- The **Audio Features** section is entirely absent — no Energy, Mood, Key, or Mode. Only the genre breakdown and artist analysis render.
- Client console log is clean: `POST /analysis/playlist/...` → 200 (job started), status polls `queued` → `completed` (100%), `GET /results` → 200. No client-side errors.

## What Was Verified

1. **The integration code is correct and matches the deployed worker.**
   - Deployed dev `release_sha` = `863ac88` (confirmed via `/health` and `src/backend/.deployed-commit.json`).
   - `git diff 863ac88 HEAD -- src/backend/services/analysis.ts` is empty → the deployed worker runs exactly the enrichment code in the working tree.

2. **ReccoBeats is reachable and returns data for *some* tracks, with no API key.**
   - Base URL `https://api.reccobeats.com/v1`, no auth (per `reccobeats-api-contract.md`).
   - The exact example track from our contract doc, `01K4zKU104LyJ8gMb7227B` (Taylor Swift – Nothing New), returns full audio-features **and** track metadata live.
   - 12 rapid requests to that track returned `200` every time — no `429` rate-limiting observed from a non-datacenter IP.

3. **Catalog coverage looks near-zero outside that example.**
   - Tested 6 additional well-known tracks (e.g. `4uLU6hMCjMI75M1A2tKUQC`, `7qiZfU4J3Ycmut4sDYwjdB`, and 4 more) → all returned `content: []` empty.
   - Only the single contract-doc example returned data among the 7 tried.

## Key Insight — What the Banners Actually Mean

In `analysis.ts`, the `audio features unavailable` / `track metadata unavailable` banners are only pushed when the ReccoBeats fetch **rejects** (throws) — see `errors.push({ source: 'reccobeats:audio-features', ... })` at `analysis.ts:202` and `:215`.

An **empty-but-`200`** response does **not** push an error. `isReccoBeatsAudioFeaturesResponse()` accepts an empty `content: []` (the `.every()` guard passes vacuously), so the code yields `[]` → `aggregateReccoBeatsAudioFeatures` returns `undefined` → no `audio_features` key → the UI simply omits the section with **no banner**.

Therefore: the user seeing **both** banners proves the Worker-side ReccoBeats fetch is **rejecting**, not returning empty. From a non-datacenter IP, valid tracks return `200` (data or empty) with no rejections and no `429`. So the rejections are specific to the **Cloudflare Worker egress**.

## Leading Hypotheses

1. **ReccoBeats blocks/fails requests from Cloudflare datacenter IP ranges** (common for free/experimental APIs). The Worker's `fetch()` to `api.reccobeats.com` would then throw (network error, non-JSON/block-page body that fails `isReccoBeatsAudioFeaturesResponse` → `"Invalid ReccoBeats audio features response shape"`, or a non-2xx). This matches both banners appearing together.
2. **Some other Worker-egress failure** — DNS, TLS/cert, or timeout — producing a thrown error rather than a `200` empty body.
3. **Independent of (1)/(2): catalog coverage has collapsed.** Even a fully successful fetch returns `[]` for most tracks, so the Audio Features section would be empty regardless (silently, without banners) for many real playlists.

> Note: the user reports having seen ReccoBeats return a fair amount of data previously, so coverage may be *partial* rather than strictly zero. Hypothesis (3)'s severity is not yet quantified — see Action Items.

## Definitive Diagnosis Pending

The real error text is available but hidden by the UI. Each `errors[]` entry carries a `message` field (e.g. `HTTP 429: rate limited`, `Request timed out after 15000ms`, `Invalid ReccoBeats audio features response shape`, or a raw fetch network error). The popup only shows `_describe_error_source(source)`, discarding `message`. Reading `GET /analysis/playlist/<id>/results` → `errors[].message` will disambiguate the cause immediately.

## Proposed Workaround (if Cloudflare egress is truly blocked)

If (1) is confirmed, a viable path: **have the backend instruct the frontend to perform the ReccoBeats fetches from the user's local machine** (browser/laptop IP, which works), then return the results to the backend to be cached on **both** the local disk cache and the backend KV. This:
- Restores enrichment without depending on Worker→ReccoBeats reachability.
- Reuses the existing `analysis:playlist:<id>:raw-enrichment` cache key (playlist-derived, user-agnostic) so the first local fetch benefits everyone.
- Mirrors the legacy monolith pattern where audio features were fetched client-side and cached under `~/.spotibye/cache/`.

Open design questions (belongs in an `exec-plans/active/` plan, not a quick fix):
- Who triggers the fetch — backend returns a `needs_enrichment` signal in `/results`, frontend fetches and `POST`s raw enrichment back?
- Dedup / race handling when multiple users analyze the same playlist.
- Keeping `schema_version` and the 24h TTL semantics consistent across both caches.
- Avoiding any secret/IP leakage; ReccoBeats needs no key, so this stays client-only.

## Action Items

- [ ] **Check more examples.** The 6 empties could be coincidental to those specific IDs. Build a broader, randomized sample across eras/genres and re-test live coverage; also test a couple of the user's *actual* playlist tracks. Confirm whether coverage is "only the doc example" vs. "partial but real" (the user has seen data before).
- [ ] **Read `errors[].message`** from `GET /results` for the failing playlist to confirm the Worker-side failure mode (429 / timeout / invalid shape / network).
- [ ] Optionally **surface the raw `message`** in the popup (or a dev-only detail) so future failures are diagnosable instead of collapsed to "unavailable".
- [ ] **Confirm whether Cloudflare egress is blocked** (e.g., a one-off Worker `fetch` to `api.reccobeats.com`, or inspect Worker logs / TLS reachability).
- [ ] **If blocked:** open an execution plan for the frontend-side fetch + dual-cache workaround described above.

## References

- `src/backend/services/analysis.ts` — enrichment fetch + `errors[]` push (`analysis.ts:184-235`, `:402-404`)
- `src/frontend/ui/backend_playlist_card.py` — banner rendering (`backend_playlist_card.py:625-635`, `_describe_error_source` at `:53`)
- `dev-docs/reccobeats-api-contract.md` — verified endpoint contract (no auth)
- [`2026-07-05-reccobeats-enrichment-gaps.md`](2026-07-05-reccobeats-enrichment-gaps.md) — prior audit; display/aggregation gaps closed, upstream-reliability out of scope (this doc)
