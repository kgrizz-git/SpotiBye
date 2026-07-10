# ReccoBeats Enrichment Failure — Empty Audio Features on Playlist Analysis

**Date:** 2026-07-09
**Status:** Resolved — root cause identified and fixed locally; frontend-direct fetch deferred
**Related:** [`2026-07-05-reccobeats-enrichment-gaps.md`](2026-07-05-reccobeats-enrichment-gaps.md) (original audit; all display/aggregation gaps there are closed, but the upstream-service-reliability question was out of scope and is what this doc covers). Also relevant: [`../reccobeats-api-contract.md`](../reccobeats-api-contract.md) (verified 2026-06-19, "no auth required").

## Context

The ReccoBeats enrichment integration is fully and correctly implemented in both the backend (`src/backend/services/analysis.ts`) and the frontend popup (`src/frontend/ui/backend_playlist_card_analysis_popup.py`). Despite that, a user running playlist analysis on the **development** backend saw no audio-feature data at all. This doc records the symptoms, what was verified, and the final diagnosis for why the upstream ReccoBeats calls were not producing data.

## Final Resolution (2026-07-10)

The original all-or-nothing partial-data banners were reproducible without assuming a broad Cloudflare egress block: the backend was sending ReccoBeats batches of 50 IDs, but ReccoBeats currently enforces a maximum of 40 IDs per request. ReccoBeats returns HTTP 400 with `size must be between 1 and 40` for both `/audio-features` and `/track` at the 50-ID size.

Fixes implemented:

- Backend ReccoBeats batch size reduced from 50 to 30, with tests covering 30/30/15 splitting for a 75-track sample.
- Existing schema-current cached analyses that contain `reccobeats:*` errors now force a one-time fresh backend analysis instead of continuing to show stale missing-enrichment results.
- Partial-data popup banners now include the backend `errors[].message` text.
- Backend ReccoBeats boundary logging now reads successful responses as text, logs a 500-character body preview on JSON parse or response-shape failures, then parses/validates JSON.
- Added `scripts/check-reccobeats-ipv6.sh` to repeat the `dig AAAA` + IPv6 `curl` reachability check.

Verification:

- The failing playlist (`03YbVT4UhOxLrOAcpyCEqT`) has 106 unique tracks. With batch size 40, ReccoBeats returned data for 64/106 tracks (60.38%) for both endpoints, with no throw batches.
- `api.reccobeats.com` publishes AAAA records, and the known-good track `01K4zKU104LyJ8gMb7227B` returns HTTP 200 over IPv6.
- A temporary `wrangler dev --remote` Worker preview also fetched the known-good ReccoBeats URL successfully.

Conclusion: ReccoBeats coverage is partial but usable for the tested playlist. The concrete backend failure was oversized request batches, not a universal Cloudflare Worker egress block. Frontend-direct ReccoBeats fetch remains a deferred, opt-in enhancement rather than part of the current fix.

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

## Phase 1 Findings (2026-07-10)

The immediate UI diagnostic gap is closed: the popup now includes `errors[].message` in partial-data banners, e.g. `Partial data: audio features unavailable (HTTP 429: rate limited)`. Focused frontend tests cover representative 429, timeout, and invalid-shape messages.

IPv6 does not appear to be the current blocker for the known-good ReccoBeats example track:

- `dig AAAA api.reccobeats.com` returns two AAAA records: `2606:4700:3030::ac43:c5a4` and `2606:4700:3036::6815:d23`.
- `curl -6 https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B` returns HTTP 200 with a non-empty `content` array.
- A temporary `wrangler dev --remote` Worker preview that fetched the same ReccoBeats URL returned HTTP 200 with a non-empty JSON body preview.

This rules out a simple broken-AAAA explanation for the known-good test case and shows Cloudflare Worker remote preview egress can currently reach ReccoBeats. It does **not** fully explain the original development-backend banners. The remaining likely causes are transient upstream/egress failure, rate limiting or blocking specific to the deployed Worker/runtime path, request-shape differences for real playlist batches, or catalog coverage/shape behavior on the failing playlist's actual track set.

## Phase 2 Progress (2026-07-10)

Added `scripts/test_reccobeats_coverage.py` to run the coverage experiment with the same batch/concurrency shape as the Worker (`BATCH_SIZE=50`, `CONCURRENCY=3`). The script can either:

- fetch playlist track IDs from the backend with `--playlist-id`, `--backend-url`, and `--auth-token` / `SPOTIBYE_AUTH_TOKEN`, or
- test explicit IDs with `--track-id` / `--track-ids-file`.

The script logs per-batch states as `throw`, `200 []`, or `200 [data]` for both `/audio-features` and `/track`, and reports endpoint coverage percentages.

Important client-behavior finding: Python `urllib`'s default request headers received HTTP 403 with Cloudflare/ReccoBeats `error code: 1010` for the known-good track. Adding explicit `Accept: application/json` and `User-Agent: SpotiBye-ReccoBeats-Coverage/1.0` made the same request return HTTP 200 with data. Any future Python frontend-direct ReccoBeats fetch should set an explicit user agent instead of relying on library defaults.

Smoke test result for `01K4zKU104LyJ8gMb7227B`: both `/audio-features` and `/track` returned `200 [data]` with 100% coverage for that one-track sample.

The actual failing playlist (`03YbVT4UhOxLrOAcpyCEqT`) contains 106 unique Spotify track IDs.

Batch behavior is now understood:

- With the Worker's current `BATCH_SIZE=50`, ReccoBeats rejects the first two 50-ID batches for both `/audio-features` and `/track` with HTTP 400:
  - `/audio-features`: `{"status":4004,"errors":[{"path":"getAudioFeatures.ids","message":"size must be between 1 and 40"}]}`
  - `/track`: `{"status":4004,"errors":[{"path":"getTracks.ids","message":"size must be between 1 and 40"}]}`
- The final 6-ID batch returns `200 [data]`.

This is a concrete backend bug: `src/backend/services/analysis.ts` uses `BATCH_SIZE = 50`, but ReccoBeats' current maximum is 40. Change the backend to `BATCH_SIZE = 30` rather than 40 to keep a buffer below the upstream cap with minimal extra request overhead.

Re-running the same playlist with `--batch-size 40` separated real coverage from the batch-size failure:

- `/audio-features`: 64/106 tracks covered (60.38%), 0 throw batches, 0 empty-200 batches, 3 data-200 batches.
- `/track`: 64/106 tracks covered (60.38%), 0 throw batches, 0 empty-200 batches, 3 data-200 batches.
- Batch details: 37/40, 7/40, and 20/26 returned data on both endpoints.

Conclusion: ReccoBeats coverage for this playlist is partial but usable. The all-or-nothing banners are explained at least in part by oversized 50-ID batches, not by total Cloudflare blocking or near-zero catalog coverage.

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

- [ ] **Optional deferred:** Check more examples. The 6 empties could be coincidental to those specific IDs. Build a broader, randomized sample across eras/genres and re-test live coverage; also test a couple of the user's *actual* playlist tracks.
- [x] **Read `errors[].message`** from `GET /results` for future failures by exposing it in the popup. The confirmed local reproduction for the failing playlist was HTTP 400 from oversized 50-ID batches.
- [x] **Surface the raw `message`** in the popup (or a dev-only detail) so future failures are diagnosable instead of collapsed to "unavailable".
- [x] **Confirm whether Cloudflare egress is blocked** for the known-good ReccoBeats example track (one-off Worker `fetch` to `api.reccobeats.com`, plus IPv6 DNS/curl checks). Current result: not blocked in a Wrangler remote preview on 2026-07-10.
- [x] **Decide whether the frontend-side fetch + dual-cache workaround is needed now.**
  - Not currently needed. The frontend-direct fetch design was deferred to backlog as an optional user-choice enhancement.

## Commentary / Addendum (2026-07-09)

### The two failures are independent — don't conflate them

The doc already nails the key insight (banners = rejection, empty `200` = silent omission), but it's worth stating the separation bluntly because it changes how we read the "catalog degraded?" skepticism:

- **The user's banners are a Worker-egress failure, not a coverage signal.** A rejection (`Promise.allSettled` → `rejected`) only happens when `fetchWithRetry` throws or the response is non-2xx/non-JSON-shape (`analysis.ts:289-303`, `:340-356`). That tells us *nothing* about whether ReccoBeats has data for those tracks. So "the catalog isn't massively degraded" is **not** an explanation for the banners the user saw. The banners mean the dev Worker could not talk to `api.reccobeats.com` at all.
- **Coverage is a separate question** measured by those 6 `content: []` results from a *non-datacenter* IP. Those 200-empties are real coverage data and are exactly the kind of thing that would silently drop the Audio Features section even on a perfectly healthy Worker. Both can be true simultaneously, and we currently have evidence for *both*.

So the immediate diagnosis priority is the egress failure; the coverage question needs its own, cleaner experiment (below).

### Hypothesis (1) is the strongest, with an important refinement

If Cloudflare datacenter IPs are blocked by ReccoBeats, the symptom is exactly "every Worker fetch rejects." But before we assume a hard IP ban, rule out the **classic Cloudflare Workers egress gotcha: a broken/missing `AAAA` (IPv6) record.** Workers egress is dual-stack and will prefer IPv6 when a target publishes `AAAA`. If `api.reccobeats.com` publishes a dead `AAAA` (or mismatched) record, `fetch` fails at connect even though the host is perfectly reachable over IPv4 from a laptop. This produces a thrown network error with no 429 — matching the banners — and is trivially fixable on ReccoBeats' side but invisible to us. A quick `dig AAAA api.reccobeats.com` + a `wrangler` one-liner `fetch('https://api.reccobeats.com/v1/audio-features?ids=...')` from inside a Worker would settle egress vs. IPv6 vs. hard-ban in one shot.

### Coverage experiment should be cleaner than "6 well-known tracks"

The Action Item to test 6 more tracks is fine but easy to muddle. Recommend:

- Pull the **actual** track IDs from the failing playlist (`GET /playlists/<id>/tracks` via the backend) and test *those* against `api.reccobeats.com` from a known-good IP. These are the tracks that matter; if most return data, the user's playlist would have rendered *something* (no banners) — which further confirms their banners were egress, not coverage.
- Distinguish per-request states explicitly: `throw` (egress/IPv6/ban) vs `200 []` (genuinely uncovered) vs `200 [data]`. Log the count of each. A single randomized sample of ~30 tracks across eras is enough to put a number on coverage ("X% covered") instead of "only the doc example worked."
- Re-run the local batch test with `BATCH_SIZE=50` (the Worker's real batch size, `analysis.ts:24`), not one-id-at-a-time. The 6-empties test used single IDs; a 50-id batch might behave differently (truncation, partial `content`, or a different error mode).

### Frontend-side fetch is the right fallback — and CORS is a non-issue here

This is the most promising improvement, and the desktop (Kivy) nature of the frontend makes it unusually clean:

- The frontend is a **Python desktop app**, not a browser. Its HTTP calls (urllib/requests/aiohttp via the existing `BackendClient`) are **not subject to CORS**. ReccoBeats sends no `Access-Control-Allow-Origin` and that simply doesn't matter for a native client. So a client-side fetch sidesteps *both* failure modes at once: Cloudflare egress blocking **and** any browser-CORS wall that a web frontend would hit. This is strictly better than a web-only approach.
- We already have the plumbing: `src/frontend/services/reccobeats_backend.py` (`ReccoBeatsBackendService`, `get_reccobeats_api`) is the natural home for a direct `api.reccobeats.com` client. The endpoints and response shapes are documented in `reccobeats-api-contract.md`.
- Proposed shape (refines the doc's "Proposed Workaround"):
  1. `GET /analysis/playlist/<id>/results` gains `needs_enrichment: boolean` plus the `track_ids` the Worker failed/omitted on. Set when the `errors[]` for `reccobeats:*` is non-empty OR the cached raw-enrichment has empty `content` for some present tracks.
  2. The popup, on `needs_enrichment`, calls ReccoBeats directly from the user's machine (batched `audio-features` + `track`, respecting `Retry-After` like `spotify.ts:150-157`), then `POST`s the raw JSON to a new `PUT /analysis/playlist/<id>/enrichment` (or similar) that writes it into the same `analysis:playlist:<id>:raw-enrichment` KV key (`analysis.ts:238-245`). First local fetch benefits all users — same sharing semantics as today.
  3. Dual-write to the **local disk cache** (`~/.spotibye/cache/`-style, per the legacy monolith) so re-analysis is instant offline and the backend KV stays a shared cache, not a source of truth.
- Open concerns to resolve in the `exec-plans/active/` plan: race/dedup when two users enrich the same playlist; merging client-provided partial data with any Worker-provided partial data; keeping `schema_version` + 24h TTL consistent across both caches; and making the client fetch **opt-in / clearly labeled** (it sends the user's IP to ReccoBeats directly — no key, but still a privacy choice). Also gate it behind a flag so we can disable if ReccoBeats later adds abuse controls.

### Small, high-value fixes that don't depend on the diagnosis

- **Surface `errors[].message` in the popup.** The frontend discards it today (only `_describe_error_source` is shown, `backend_playlist_card_utils.py:14-15`). Showing the raw message (or a dev toggle) turns every future failure from "unavailable" into "HTTP 429 / Invalid shape / network" and is the single fastest way to stop guessing. Low risk, high diagnostic ROI.
- **Add a "Retry enrichment from this device" affordance** once client-side fetch exists — turns the dead-end banner into an action.
- **Log more at the boundary.** When `isReccoBeatsAudioFeaturesResponse` fails (`analysis.ts:301`), we throw `"Invalid ... response shape"` and lose the body. Capturing the first ~500 bytes would tell us if it's a Cloudflare/ReccoBeats block page vs. an empty JSON envelope.

### Doc-accuracy nit

The References cite stale paths/lines: `backend_playlist_card.py:625-635` and `:53` no longer exist. The card was refactored into mixins. Correct current locations:

- `_describe_error_source` → `src/frontend/ui/backend_playlist_card_utils.py:14-15`
- Banner/partial-data rendering → `src/frontend/ui/backend_playlist_card_analysis_popup.py` (around `:527-537` for `reccobeats_metadata`)
- Enrichment fetch + `errors[]` push → unchanged at `src/backend/services/analysis.ts:184-235`

Recommend updating those citations so the next reader doesn't hunt for a 600-line file that's now 66 lines.

---

## Additional Diagnosis Ideas & Frontend-Fetch Improvement Plan

### 1. Immediate diagnosis: surface the hidden error messages

The single highest-ROI fix is to **expose `errors[].message` in the popup**. Right now `backend_playlist_card_utils.py:14-15` collapses all failures to `"audio features unavailable"` — the actual error text (e.g. `HTTP 429`, `Request timed out after 15000ms`, `Invalid ReccoBeats audio features response shape`, or a raw network error) is available in `GET /analysis/playlist/<id>/results` but never shown.

**Minimal change:**
```python
# src/frontend/ui/backend_playlist_card_utils.py
def _describe_error_source(source: str, message: str | None = None) -> str:
    base = _ERROR_SOURCE_LABELS.get(source, source)
    return f"{base} ({message})" if message else base
```

Then pass the message through from the results payload. This turns every future failure from a guess into an immediate diagnosis.

---

### 2. Worker egress diagnosis: rule out IPv6 before assuming a ban

Hypothesis (1) (Cloudflare datacenter IPs blocked) is strongest, but **IPv6 egress failure** is a classic Workers gotcha that produces identical symptoms:

```bash
# Check if api.reccobeats.com publishes AAAA
dig AAAA api.reccobeats.com

# One-liner Worker fetch to test egress from Cloudflare
wrangler dev --remote  # then curl the dev Worker to trigger a ReccoBeats fetch
```

If `AAAA` exists but is dead/misconfigured, Workers egress will fail at connect while laptop IPs succeed over IPv4. This is trivially fixable on ReccoBeats' side but invisible to us without this check.

---

### 3. Coverage experiment: cleaner methodology

The "6 well-known tracks" test is a start but easy to misinterpret. Recommended approach:

1. **Pull actual track IDs from the failing playlist** via `GET /playlists/<id>/tracks`. These are the tracks that matter.
2. **Test all of them** against `api.reccobeats.com` from a known-good IP, batching in 50s (the Worker's real batch size).
3. **Log explicit states per track**: `throw` (egress failure) vs `200 []` (uncovered) vs `200 [data]` (covered).
4. **Report coverage %**: "X of Y tracks (Z%) returned data" is more actionable than "only the doc example worked."

A randomized sample of ~30 tracks across eras/genres is enough to quantify coverage without boiling the ocean.

---

### 4. Frontend-side fetch: the right fallback for desktop apps

If Cloudflare egress is truly blocked, **client-side fetch from the Python desktop app** is the cleanest workaround:

#### Why this works especially well for SpotiBye

- **No CORS**: The frontend is a native Python app (Kivy), not a browser. Its HTTP calls (urllib/requests/aiohttp) bypass CORS entirely. ReccoBeats sends no `Access-Control-Allow-Origin` and that simply doesn't matter.
- **Existing plumbing**: `src/frontend/services/reccobeats_backend.py` (`ReccoBeatsBackendService`, `get_reccobeats_api`) is the natural home for direct `api.reccobeats.com` calls. Endpoints and response shapes are documented in `reccobeats-api-contract.md`.
- **Dual-cache semantics**: First local fetch benefits all users via the backend KV cache (`analysis:playlist:<id>:raw-enrichment`), matching the legacy monolith's `~/.spotibye/cache/` sharing model.

#### Proposed shape

1. **Backend signals missing enrichment**: `GET /analysis/playlist/<id>/results` gains `needs_enrichment: boolean` + `missing_track_ids: string[]`. Set when `errors[]` for `reccobeats:*` is non-empty OR cached raw-enrichment has empty `content` for some tracks.

2. **Frontend fetches directly** (opt-in, gated behind a flag):
   ```python
   # src/frontend/services/reccobeats_backend.py
   def fetch_reccobeats_enrichment_direct(
       self,
       track_ids: list[str],
       batch_size: int = 50,
   ) -> dict:
       """Fetch audio-features + track metadata from user's machine."""
       # Batch requests, respect Retry-After, return raw JSON
   ```

3. **Frontend POSTs raw results back** to a new `PUT /analysis/playlist/<id>/enrichment` endpoint that writes to the same KV key (`analysis.ts:238-245`).

4. **Dual-write to local disk cache** (`~/.spotibye/cache/analysis_<playlist_id>.json`) so re-analysis is instant offline and the backend KV stays a shared cache, not a source of truth.

#### Open design questions (for `exec-plans/active/` plan)

- **Race/dedup**: What if two users enrich the same playlist simultaneously? (Answer: last-write-wins is fine; both write identical raw JSON.)
- **Partial data merging**: How to merge client-provided partial data with any Worker-provided partial data?
- **Schema/TTL consistency**: Keep `schema_version` + 24h TTL semantics identical across both caches.
- **Privacy gating**: Make client fetch **opt-in / clearly labeled** — it sends the user's IP to ReccoBeats directly (no key, but still a privacy choice). Add a settings toggle and a per-session "Fetch from this device" button.
- **Abuse controls**: Gate behind a feature flag so we can disable if ReccoBeats later adds rate-limiting or auth.

---

### 5. Small, high-value fixes independent of diagnosis

These improve debuggability and UX regardless of the root cause:

| Fix | Location | Impact |
|-----|----------|--------|
| **Surface `errors[].message`** | `backend_playlist_card_utils.py:14-15` | Turns "unavailable" into "HTTP 429 / timeout / invalid shape" — immediate diagnosis |
| **Add "Retry enrichment from this device" button** | Popup UI, after client-fetch implemented | Converts dead-end banner into action |
| **Log response body on shape mismatch** | `analysis.ts:301` (capture first ~500 bytes) | Distinguishes block page from empty JSON envelope |
| **Add IPv6 reachability check to dev script** | `scripts/backend-deploy-status.sh` or new one-liner | Rules out AAAA failure before assuming IP ban |

---

### 6. Skepticism about "catalog massively degraded" is warranted

The investigation's evidence for coverage collapse is **6 empty `200` responses from a laptop IP**. That's a tiny sample, and the user reports having seen ReccoBeats return data previously. Two cleaner signals:

1. **The user's banners prove egress failure, not coverage gaps.** Rejections (`Promise.allSettled` → `rejected`) only happen when `fetchWithRetry` throws or the response is non-2xx/non-JSON-shape (`analysis.ts:289-303`, `:340-356`). Empty `200 []` responses do **not** produce banners — they silently omit the Audio Features section. So the banners the user saw are **purely a Worker-egress signal**.

2. **Coverage is a separate question** measured by `200 []` responses from non-datacenter IPs. Both can be true: Worker egress is blocked **and** ReccoBeats has partial catalog coverage. The investigation already separates these; the emphasis bears repeating because it prioritizes the work:
   - **First:** fix egress (diagnose with error messages + IPv6 check, then implement frontend fetch if needed).
   - **Second:** quantify coverage with a real sample from the user's actual playlists.

---

### 7. Implementation sketch: frontend fetch in `reccobeats_backend.py`

If egress is confirmed blocked, here's the natural extension point in the existing service:

```python
# src/frontend/services/reccobeats_backend.py
def fetch_reccobeats_enrichment_direct(
    self,
    track_ids: list[str],
    batch_size: int = 50,
    timeout: int = 15,
) -> dict[str, typing.Any]:
    """
    Fetch ReccoBeats audio-features + track metadata from the user's machine.
    
    Returns raw JSON envelope: {
        "audio_features": [...],
        "track_metadata": [...],
        "fetched_at": "<ISO timestamp>",
        "source": "client-direct",
    }
    """
    import urllib.request
    import json
    
    base_url = "https://api.reccobeats.com/v1"
    audio_features = []
    track_metadata = []
    
    # Batch requests to avoid overwhelming ReccoBeats
    for i in range(0, len(track_ids), batch_size):
        batch = track_ids[i:i + batch_size]
        
        # Audio features
        af_url = f"{base_url}/audio-features?{'&'.join(f'ids={tid}' for tid in batch)}"
        with urllib.request.urlopen(af_url, timeout=timeout) as resp:
            data = json.loads(resp.read())
            audio_features.extend(data.get("content", []))
        
        # Track metadata
        tm_url = f"{base_url}/track?{'&'.join(f'ids={tid}' for tid in batch)}"
        with urllib.request.urlopen(tm_url, timeout=timeout) as resp:
            data = json.loads(resp.read())
            track_metadata.extend(data.get("content", []))
    
    return {
        "audio_features": audio_features,
        "track_metadata": track_metadata,
        "fetched_at": datetime.datetime.now().isoformat(),
        "source": "client-direct",
    }
```

This slots cleanly into the existing `ReccoBeatsBackendService` class and reuses the retry/network-error handling decorators already present (`@handle_network_errors`, `@retry_on_network_error`).

---

### 8. Next actions (prioritized)

- [x] **Add error message display to popup** (5-10 min, highest diagnostic ROI)
- [x] **Run `dig AAAA api.reccobeats.com`** + one-liner Worker fetch to rule out IPv6
- [x] **Test actual playlist track IDs** from the failing playlist against ReccoBeats from laptop IP; report coverage %
- [ ] **Optional future enhancement:** if backend enrichment still fails after the batch-size fix and stale-cache retry behavior, revive the frontend-direct fetch design as a user-choice plan with race handling, privacy gating, dual-cache behavior, and a feature flag.
- [x] **Optional but valuable:** add `errors[].message` logging at the boundary (`analysis.ts:301`) to capture block-page bodies on shape mismatches

## References

- `src/backend/services/analysis.ts` — enrichment fetch + `errors[]` push (`analysis.ts:184-235`, `:402-404`)
- `src/frontend/ui/backend_playlist_card_analysis_popup.py` — partial-data banner rendering
- `src/frontend/ui/backend_playlist_card_utils.py` — `_describe_error_source`
- `dev-docs/reccobeats-api-contract.md` — verified endpoint contract (no auth)
- [`2026-07-05-reccobeats-enrichment-gaps.md`](2026-07-05-reccobeats-enrichment-gaps.md) — prior audit; display/aggregation gaps closed, upstream-reliability out of scope (this doc)
