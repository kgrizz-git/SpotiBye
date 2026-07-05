# Peer Review: Backend URL Defaulting & Selector UI Bug

**Timestamp:** 2026-07-05T18:45:00-04:00
**Reviewing:** [2026-07-05-backend-url-defaulting-bug.md](./2026-07-05-backend-url-defaulting-bug.md)
**Status:** Agree with diagnosis and recommended fixes

---

## Verification Summary

I independently verified every factual claim in the referenced assessment and found them all to be accurate.

### Commit history
- `git show c88b3433 -- src/frontend/config/backend_config.py` confirms the exact diff cited in Section 2-A: the default `BACKEND_URL` was changed from `https://spotibye-backend-development.kevin-grizzard.workers.dev` to `http://localhost:8787` with the explicit comment intent of preventing shipped binaries from hardcoding a developer's private Worker URL.

### Current source state
- `src/frontend/config/backend_config.py` lines 15-18: `BACKEND_URL` defaults to `http://localhost:8787`.
- `src/frontend/config/backend_config.py` lines 57-61: `BACKEND_PRESETS` maps both `"Localhost"` and `"Cloudflare Dev"` to the same `BACKEND_URL` value.
- `src/frontend/ui/backend_selector_popup.py` lines 128-129: `_on_preset_changed` sets `self.url_input.text = BACKEND_PRESETS[selected]`, which is a no-op when switching between Localhost and Cloudflare Dev.

### Additional secondary symptom
The assessment correctly describes the two primary symptoms (default-to-localhost and non-functional preset button). I also observed a **third downstream UX issue** caused by the same root cause:

In `backend_selector_popup.py` lines 98-112, `_initialize_from_default_url` restores the spinner state by iterating `BACKEND_PRESETS.items()` and matching on URL string equality. Because both `"Localhost"` and `"Cloudflare Dev"` currently evaluate to `http://localhost:8787`, the first key in iteration order (`"Localhost"`) always wins. This means:
1. Even if a user previously selected `"Cloudflare Dev"` and saved it, the saved URL is still just `http://localhost:8787` (since `BACKEND_PRESETS["Cloudflare Dev"]` resolves to the same string).
2. On the next launch, the popup restores the spinner to `"Localhost"` instead of `"Cloudflare Dev"`, effectively losing the user's explicit preset choice.

This reinforces the assessment's conclusion: the concepts of **"default startup fallback"** and **"Cloudflare Dev preset URL"** must be decoupled.

---

## Evaluation of Recommended Fixes

I agree with **Option 1** (introduce `DEV_BACKEND_URL`, keep `BACKEND_URL` defaulting to localhost) for the following reasons:

1. **Preserves FT-2's security intent.** The shipped binary still does not hardcode a developer-specific Cloudflare Worker URL as the runtime default.
2. **Restores selector functionality.** Once `"Cloudflare Dev"` maps to a distinct URL, `_on_preset_changed` will produce a visible update, `_initialize_from_default_url` will correctly restore the spinner state, and saved preferences will round-trip accurately.
3. **Minimal blast radius.** The change is limited to one new constant and one dictionary entry update in a single file. No UI logic needs to change.
4. **Adds useful flexibility.** The `SPOTIBYE_DEV_BACKEND_URL` environment variable override is a natural extension of the existing override pattern (`SPOTIBYE_BACKEND_URL`, `SPOTIBYE_PRODUCTION_BACKEND_URL`).

I do not see any safer or simpler alternative. Reverting `BACKEND_URL` back to the dev Worker URL would undo FT-2's binary-hardening goal. Making the popup match on preset names instead of URLs would require persisting preset metadata and refactoring `save_backend_url`, which is unnecessary when the real fix is simply giving the preset its own URL constant.

---

## Suggested Additions to the Execution Plan

When the assessment's recommended fix is executed, I suggest also adding the following minor verification step that was not explicitly listed:

- **Verify preset restore on restart:** After selecting `"Cloudflare Dev"` and clicking Continue, close and relaunch the application. Confirm the `Choose Backend` popup opens with `"Cloudflare Dev"` pre-selected (not `"Localhost"`). This validates that the secondary symptom described above is also resolved.

---

## Conclusion

The original assessment is **correct, complete, and actionable**. I endorse its diagnosis and its recommended implementation (Option 1) without reservation.
