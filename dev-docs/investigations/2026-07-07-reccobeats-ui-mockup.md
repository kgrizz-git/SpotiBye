# ReccoBeats Analysis Popup — UI Mockup

**Date:** 2026-07-07
**Context:** [ReccoBeats enrichment integration plan](../exec-plans/completed/2026-07-07-reccobeats-enrichment-integration.md) Phase 3. Extends `_update_analysis_ui` in `src/frontend/ui/backend_playlist_card.py` (not a new screen).

Kivy has no DOM/ARIA tree, so there is no axe-core equivalent here. "Accessibility" in this Kivy context means: labels read in a sensible top-to-bottom order for screen-reader-adjacent tools (OS-level screen readers reading widget `text` in tree order), consistent color-coded severity (errors in red-ish tones, matching the existing `(0.65, 0.4, 0.4, 1)` error color already used in the popup), and no information conveyed by color alone (every value has a text label).

## Section Order (top to bottom, within the existing `analysis_container`)

1. **Partial-failure banner** (new) — only rendered when `result.get('errors')` is non-empty. One line per error source, e.g. `"Partial data: artist genres unavailable"`. Rendered first so a user scanning top-down immediately knows the analysis may be incomplete, before reading numbers that might look complete but aren't.
2. **Genre Distribution** (existing, unchanged position/order)
3. **Artist Analysis** (existing, unchanged position/order)
4. **Audio Features** (extended) — structured multi-row layout instead of the single " · "-joined line:
   - Row 1: `Danceability: 60% · Energy: 80% · Acousticness: 30%`
   - Row 2: `Instrumentalness: 5% · Liveness: 20% · Speechiness: 8%`
   - Row 3: `Tempo: 120 BPM · Loudness: -6.0 dB`
   - Row 4: `Mood: Cheerful (valence 68%)` — mood label first (primary signal), raw percentage in parentheses (secondary/debug signal), not the reverse — a screen reader announcing this line front-to-back gets the meaningful word first.
   - Row 5 (only when `key_mode_distribution` present): `Key: C major (42% of tracks)` — combines `dominant_key` + `dominant_mode` per the export CSV convention (`export-tracks.ts`'s `"C major"` pattern), so the same vocabulary appears in both the UI and exported files.
   - Row 6: `Based on N tracks with available audio data` (existing footer line, unchanged)
5. **ReccoBeats Metadata** (new) — only rendered when `reccobeats_metadata` is present:
   - `ISRC available for N of M tracks`
   - `Popularity range: min–max` (only when `popularity_min`/`popularity_max` are both present)

## Mood Bands (valence → label)

| Range | Label |
|-------|-------|
| [0.00, 0.20) | Melancholic |
| [0.20, 0.40) | Somber |
| [0.40, 0.60) | Neutral |
| [0.60, 0.80) | Cheerful |
| [0.80, 1.00] | Euphoric |

Upper bound exclusive except the last band, which is inclusive (valence is normalized 0.0–1.0, so 1.00 must land somewhere).

## Backward Compatibility (Phase 1 → Phase 2 rollout gap)

A cached or in-flight result written by a Phase 1-only backend has no `schema_version`, `key_mode_distribution`, or `reccobeats_metadata` fields. The UI must render the same as it does today for that shape — no crash, no empty section headers for data that was never fetched. This is achieved by:

- Never indexing into `result.get('audio_features') or {}` etc. without `or {}` fallbacks at every nesting level.
- Treating `key_mode_distribution` and `reccobeats_metadata` as fully optional — omit the row/section entirely (not "N/A") when absent, since their absence pre-Phase-2 is expected/normal rather than a fetch failure.

## Color Conventions (reused, not new)

- Section headers: existing bold `(0.88, 0.88, 0.88, 1)` white-ish
- Body text: existing `(0.75, 0.75, 0.75, 1)` gray
- Muted/footer text: existing `(0.55, 0.55, 0.55, 1)` dim gray
- Partial-failure banner: existing error color `(0.65, 0.4, 0.4, 1)` (same as the "Analysis unavailable" message), signaling "something's missing" without introducing a new color meaning
