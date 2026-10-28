# SpotiBye ↔ SpotiByeMatcher Integration Plan

**Status:** Phase 0 complete (ISRC export column shipped in PR #71 on 2026-10-26); Phases 1–3 deferred pending decision on Option A vs B

**Date:** 2026-10-25

**Source:** [Backlog TO_DO.md](../../backlog/TO_DO.md#apple-music-matching)

## Goal

Let a user take a Spotify playlist exported by SpotiBye, match each track to
Apple Music, and add the matches to a new or existing Apple Music playlist.

## Background

[SpotiByeMatcher](https://github.com/kgrizz-git/SpotiByeMatcher) (private;
package name `tunebridge`) is a React + Vite app generated with Google AI
Studio. As of 2026-10-25 it can:

- Import SpotiBye CSV and Excel exports, including the playlist metadata
  header lines (`src/lib/fileImport.ts`).
- Match each track against the iTunes Search API, which needs no key
  (`src/lib/appleMusic.ts`). It searches by ISRC first, then by title,
  artist, and album, and scores candidates 0–100 with fuzzy matching plus
  duration.
- Let the user review, approve, or reject matches, with an auto-approve
  threshold and bulk actions.
- Cache high-confidence matches in Firestore and export results to Excel.

It cannot write to Apple Music. That is listed under "Apple Music Native
Integration" in its `ROADMAP.md`.

SpotiBye's Apple Music API research is in
[apple-music-api-analysis.md](../../investigations/apple-music-api-analysis.md).

## Phase 0 — ISRC in SpotiBye exports

An ISRC lets the Matcher use its exact lookup instead of fuzzy text search.

- [x] Add an `ISRC` column to every export format, appended last so existing
      column positions stay the same
- [x] Fill it from the ReccoBeats audio-features row already resolved for
      enriched exports, so no new upstream calls are made
- [x] Leave it empty, not `N/A`, when unknown. The Matcher treats any
      non-empty value as an ISRC to search for.

Plain (unenriched) exports have an empty ISRC column, because they skip
ReccoBeats entirely.

## Phase 1 — Verify the file handoff

Keep the two apps separate: SpotiBye exports, and the Matcher imports.

- [ ] Confirm the Matcher maps the `ISRC` header to `Track.isrc`. If its
      header mapping needs a change, make it in the Matcher repo.
- [ ] Export a real playlist with enrichment on, import it into the
      Matcher, and record the ISRC hit rate versus text-search matches
- [ ] Decide whether plain exports should also resolve ISRCs, which would
      mean ReccoBeats calls for every export
- [ ] Check whether Spotify still returns `external_ids.isrc` on playlist
      items for Development Mode apps after the February 2026 changes (see
      [february-2026-spotify-migration-findings.md](../../investigations/february-2026-spotify-migration-findings.md)).
      If it does, use it as a fallback when ReccoBeats has no row.

## Phase 2 — Decide where matching lives

Pick one option before building anything further.

- **Option A: keep separate apps.** This has the lowest cost and is already
  working. The user has to move a file between apps.
- **Option B: port matching into SpotiBye's backend.** Add
  `services/apple-music-match.ts` to the Worker, based on `appleMusic.ts`.
  Cache matches in KV under a global key such as
  `global:applematch:isrc:{isrc}`, following the documented
  `global:reccobeats:*` exception to user-namespaced keys. Add a match route
  and a review screen to the Kivy app.

Risks for Option B:

- The iTunes Search API is rate limited to roughly 20 requests per minute
  per IP, and Cloudflare's shared egress IPs may hit that limit sooner.
  Large playlists would need queue-based batching like analysis fan-out.
- The review UI would have to be rebuilt in Kivy.

- [ ] Choose Option A or B and record the decision in
      `dev-docs/architecture/design-decisions/`

## Phase 3 — Write to Apple Music

Both options need this for "add to a new or existing playlist".

- [ ] Join the Apple Developer Program and create a MusicKit key
- [ ] Sign the developer token (ES256 JWT) on the backend. Store
      `APPLE_MUSIC_KEY_ID`, `APPLE_MUSIC_TEAM_ID`, and
      `APPLE_MUSIC_PRIVATE_KEY` as Worker secrets with `--env` set.
- [ ] Get a Music User Token. MusicKit JS `authorize()` runs only in a
      browser, so the desktop app needs a Worker-served page that runs it
      and hands the token back over the loopback callback, like Spotify
      login does today.
- [ ] Create playlists with `POST /v1/me/library/playlists` and add tracks
      in batches with `POST /v1/me/library/playlists/{id}/tracks`
- [ ] Confirm which existing library playlists accept added tracks. Apple's
      library API does not support removing or reordering tracks.

## Open Questions

- What does the Matcher use `@google/genai` for, and is that needed in
  SpotiBye?
- Should Firestore's match cache be replaced by KV, or shared between the
  two apps?
