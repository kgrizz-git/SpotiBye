# Plan: App Icon at Runtime, README Branding, a Source Launcher, and Public-Repo CI Posture

**Status:** not started — plan authored on `feat/app-icon-and-source-launcher`
**Branch:** `feat/app-icon-and-source-launcher`
**Created:** 2026-10-18
**Motivation (branding):** The repo ships exactly one icon design (`resources/`) and wires it into the *packaged* app only. Three gaps follow from that: (1) running from source (`python run_frontend_backend.py`) shows Kivy's default icon and an "Untitled"-looking title bar, so the app is unrecognizable in Mission Control/Dock/Alt-Tab; (2) the README — the project's front door on GitHub — has no logo and no badges; (3) a source user has no double-clickable entry point and no branded icon in Finder, which is exactly the "just run it" experience every other desktop app has.
**Motivation (CI posture):** The repo is now **public**, which retroactively invalidates the cost model behind `2026-07-22-reduce-github-actions-billable-minutes.md` (Actions minutes are free for public repos) and leaves three concrete gaps: a stale `push`-trigger + secret-scanning hole in `security.yml`, a stale private-repo justification on SARIF upload in `dependency-review.yml`, and a pre-existing gap where `scripts/tests/` is verified locally but never runs in CI — which directly affects Phase 3's launcher test.

**Ground facts (verified 2026-10-18):**

- Icon assets live in `resources/` only: `SpotiBye black edited 1.png` (1024×1024, square, transparent corners) and `SpotiBye black edited 1-modified.png` (1024×1024, squircle black background). `.icns` (1.8 MB, verified `Mac OS X icon`, type `ic12`) and `.ico` (727 KB) exist for the modified variant only.
- Packaging already consumes the icon: `spotibye.spec:58` (`.ico`, Windows), `spotibye.spec:97` (`.icns`, macOS), `spotibye.spec:99` (`.png`, Linux); `packaging/linux/install-desktop-entry.sh:7` uses the PNG.
- Nothing sets a runtime window icon: `rg -i icon src/frontend -g '*.py'` matches only `UIConstants` (unrelated). Window setup lives in `set_window_basics()` — `src/frontend/utils/platform_utils.py:366-390` — called from `BackendSpotifyExporterApp.build()` at `src/frontend/app/backend_app.py:134`. The failure path `_fallback_window_setup()` (`platform_utils.py:417-428`) sets title/size only.
- Kivy is 2.3.1. The SDL2 provider sets the icon from `self.icon or Config.get('kivy', 'window_icon')` *before* `set_mode` (`.venv/.../kivy/core/window/window_sdl2.py:375-385`) and exposes `Window.set_icon()` → `SDL_SetWindowIcon` (`:456`), so assigning `Window.icon` after `build()` still works. Kivy's own default is `kivy-icon-64.png` on Windows / `kivy-icon-512.png` on macOS (`:376-384`), which confirms PNG is accepted on every desktop platform.
- The PyInstaller entry point is `run_frontend_backend.py` (`spotibye.spec:114`), so the launcher must drive that same file, not a second entry.
- macOS per-file custom icons: `/usr/bin/SetFile` exists here (Xcode CLT at `/Applications/Xcode.app`) and `SetFile -a C <icns> <file>` exits 0, setting the `com.apple.FinderInfo` has-icon flag byte `0x0a`. It reports failures loudly (`-43` missing file, `-5000` unreadable icon). **Unverified:** that Finder actually renders the result — no resource-fork xattr appeared and this environment has no `AppKit` (pyobjc) or visual check available. `SetFile` also requires Xcode Command Line Tools, which a stock user Mac does not have, so a fallback is mandatory.
- No `.gitattributes` in the repo, so a committed `.command` file must be LF-only and mode `100755` or bash will reject it.
- There is no test module for `platform_utils` today (`ls src/frontend/tests | rg -i platform` → no match).
- `dev-docs/guides/frontend-distribution-guide.md:25-28` documents the icons as `src/frontend/assets/icon.{ico,icns,png}` — a path that does not exist. Stale; fix it while here.
- README has no image and no badges. Workflow names for badges: `CI` (`ci.yml`), `Build Executables`, `Security Scan` (`security.yml`), `OSV PR Scan` (`dependency-review.yml`). Triggers matter: `ci.yml` runs on push **and** PR to `main`/`develop`/`WIP` with no path filter, whereas `security.yml` and `dependency-review.yml` are **PR-only with path filters** — a status badge for either reports "skipped" or stale most of the time and is misleading.
- Repo guardrails that constrain this plan: `scripts/check-repo-structure.sh:59-73` requires active plans to use `- [ ]` tracking; `scripts/check_docs_hygiene.py` requires the plan to be indexed in `active/README.md` and to have a `TO_DO.md` backlink. Docs are capped at 300 lines by the file-length hook, hence five tight phases.

**Public-repo ground facts (verified 2026-10-18 via `gh api`):**

- `gh repo view --json visibility` → `PUBLIC`, `isPrivate: false`. GitHub-hosted Actions minutes are therefore free; this repo is all `ubuntu-latest`, so the billable-minutes optimization target no longer exists.
- **Code Scanning is already enabled and running** — 4 CodeQL alerts on `refs/heads/main` (2 fixed, 2 dismissed as false positives). There is **no `codeql.yml`** in `.github/workflows/`, so this is GitHub's automatic default setup for public repos. Do **not** add a CodeQL workflow: it would duplicate analysis and can conflict with the default setup.
- **Dependabot alerts: 3 open** (free on public repos). Secret scanning endpoint responds (0 alerts).
- **Branch protection is now unblocked**: `gh api repos/kgrizz-git/SpotiBye/branches/main/protection` returns `404 Branch not protected`, where the billable-minutes plan recorded a `403 "Upgrade to GitHub Pro or make this repository public to enable this feature"` (`:126`). The tier blocker is gone; the feature is simply unconfigured.
- `security.yml` **already scans `main`** via `schedule: cron '0 0 * * 1'` (`:20-22`) plus `workflow_dispatch`; most recent schedule run 2026-10-19, `success`. The gap is immediacy on merge, not coverage.
- **The `push` trap:** adding `push: branches: [main]` to `security.yml` as written would skip *both* TruffleHog steps — the PR-diff step is gated on `github.event_name == 'pull_request'` and the full-history step on `schedule`/`workflow_dispatch`. A push-to-main run would report `TruffleHog | skipped` in the step summary while looking green: zero secret scanning on merges. Both conditions must widen in the same change.
- `dependency-review.yml` is **not** `actions/dependency-review-action`; it calls OSV's PR-diff reusable workflow, chosen *because* of the old private status (`:24-26`). Its contract is a base↔head diff, so a `push` trigger is semantically meaningless — and `merge_group` (`:15-16`) is already the correct GitHub mechanism for "code landed on `main`".
- `dependency-review.yml:31` sets `upload-sarif: false` with the rationale "private personal repos do not have GitHub Code Scanning enabled". Code Scanning is now live, so that justification is dead.
- **CI never runs `scripts/tests/`**: the frontend job's only test step is `pytest src/frontend/tests/ -v` (`.github/workflows/ci.yml:81`), while `scripts/verify-frontend.sh:26` runs `scripts/tests/` locally only. This is pre-existing (the setup-selfhost tests are in the same boat) and means Phase 3's launcher test would be dead weight in CI unless the job is extended.
- CI badge viability is therefore phase-dependent: `ci.yml` runs on push **and** PR with no path filter (always-valid badge), `security.yml`/`dependency-review.yml` are PR-only with path filters (misleading badge) — and Phase 4 changes that for `security.yml` if it lands.

---

## Phase 1 — Window icon when running from source

- [ ] Decide the source variant: use the **unmasked** `SpotiBye black edited 1.png` for the window, keeping the squircle `-modified` variant for Finder/Dock/installed bundles (macOS applies the squircle itself to real app icons; double-masking makes the window icon look shrunken). Record the choice here and in the guide.
- [ ] Add a pure, side-effect-free resolver in `src/frontend/utils/platform_utils.py`: `resolve_window_icon() -> Path | None` that walks up from `Path(__file__).resolve().parents[3]` to the repo root, checks `resources/` for the chosen PNG, and returns `None` when the file is absent **or** when running frozen (`getattr(sys, "frozen", False)` → the PyInstaller bundle already owns its icon via `spotibye.spec`, and `resources/` is not bundled, so this guard prevents a missing-file path in production builds).
- [ ] Add `apply_window_icon()` next to it: lazily fetch `Window` via the existing `_window()` helper, assign `Window.icon = str(path)` inside the try/except that `set_window_basics` already uses, and on failure `logger.warning(...)` with the reason — never raise. Icon failure must never block app startup.
- [ ] Call `apply_window_icon()` from `set_window_basics()` (so the normal path is covered) **and** from `_fallback_window_setup()` (so the icon survives the exception path); the helper's internal guard makes the double call cheap.
- [ ] Keep `platform_utils.py` under the 700-line code cap; if the two functions plus docstrings push it over, extract to a sibling module rather than exempting.
- [ ] Tests: new `src/frontend/tests/test_window_icon.py` covering (a) resolver returns the PNG when present, (b) returns `None` when the file is missing (monkeypatched root), (c) returns `None` when `sys.frozen` is set, (d) `apply_window_icon()` swallows a `Window.icon` assignment failure without raising. Pure-function tests only — do not open a real window in the suite.
- [ ] Manually verify on macOS that the Dock/Alt-Tab entry and the window title-bar-adjacent icon show SpotiBye, and record the result in this plan.

## Phase 2 — README icon and badges

- [ ] Add a repo-relative `<img>` logo under the `# SpotiBye` heading in `README.md`.
- [ ] Generate a **small** README copy rather than linking the 1.38 MB source PNG: `sips -Z 320 "resources/SpotiBye black edited 1-modified.png" --out resources/spotibye-logo-320.png`, committed. Record the exact regeneration command in `dev-docs/guides/frontend-distribution-guide.md` so the copy is not mistaken for a new source of truth. Use the masked (`-modified`) variant here — README is not a window, so the squircle is correct there.
- [ ] Add badges under the heading in this conservative set, each verified against the workflow file before it is committed: CI status (`https://github.com/kgrizz-git/SpotiBye/actions/workflows/ci.yml/badge.svg?branch=main`, link to the Actions run) and license (`GPL-3.0`, link to `LICENSE`).
- [ ] Deliberately **omit** `Security Scan` and `OSV PR Scan` badges, and note why inline as an HTML comment: both workflows are PR-only with path filters (`security.yml:4-11`, `dependency-review.yml:3-11`), so a badge shows a misleading permanent "skipped". Re-evaluate this decision in the same PR as Phase 4 — if `security.yml` gains a `main` push trigger it becomes badge-eligible, and `dependency-review.yml` never does while it stays PR-diff scoped.
- [ ] Re-check badge URLs render (no 404, correct branch) before the PR — a red-for-the-wrong-reason badge is worse than none.

## Phase 3 — Double-clickable launcher with first-run icon association

- [ ] Add `SpotiBye.command` at the repo root, committed with LF endings and mode `100755` (`git update-index --chmod=+x`); add a `.gitattributes` rule (`*.command text eol=lf`) so the executable bit and line endings survive other contributors' checkouts. Confirm with `git ls-files -s SpotiBye.command` (expect `100755`) and `file SpotiBye.command`.
- [ ] Launcher body: `cd "$(dirname "$0")"` first — Finder opens Terminal with `$HOME` as cwd, not the script's directory, which is the classic double-click bug; then prefer `.venv/bin/python`, fall back to `python3`, and print an explicit "run `python3 -m venv .venv && pip install -r requirements.txt`" message and exit non-zero if neither exists; then `exec "$PY" run_frontend_backend.py` so signals and the exit code pass through and the app is the last process.
- [ ] First-run icon association, run **once** and never allowed to block the launch:
  - [ ] Guard: skip when `com.apple.FinderInfo` already carries the has-icon flag (`0x0a`) — read via `/usr/bin/xattr`, which needs no extra toolchain — and fall back to a gitignored sentinel file next to the launcher when `xattr` is unavailable. Keep the sentinel out of git (`.gitignore`).
  - [ ] Mechanism ladder, first one that succeeds wins: (1) `SetFile -a C resources/SpotiBye black edited 1-modified.icns SpotiBye.command` when `/usr/bin/SetFile` exists; (2) `osascript` telling Finder to set the icon of the file (works without Xcode CLT but needs a one-time Automation permission grant — accept the prompt, document it); (3) give up with a one-line "install Xcode CLT (`xcode-select --install`) to brand this launcher" hint.
  - [ ] Every branch is `|| true`-style: a failed icon must never stop the app from starting, and the message must name the failure so a user can act.
- [ ] Scope: macOS gets the launcher. Other platforms get a short "run `python3 run_frontend_backend.py`" line and no icon work — Windows Explorer cannot set per-file icons from a script, and inventing `.bat`/`.desktop` variants here is scope creep (see Out of scope).
- [ ] Phase 1 and Phase 3 compose deliberately: the launcher brands the Finder file, and the app now brands its own window, so a source run looks branded at both layers without touching packaging.
- [ ] Test: add a Python test under `scripts/tests/` asserting `SpotiBye.command` exists, is LF-only, is executable, drives `run_frontend_backend.py`, and that the icon block is guarded by the already-set check. (Shell-level behavior is verified manually, not in CI, which runs on Linux/Windows.)
- [ ] Manual verification, recorded here: double-click from Finder with cwd ≠ repo root, confirm it launches; confirm the Finder icon appears after first run; confirm a second run does not re-apply the icon and does not re-prompt; confirm `git status` is clean afterward.

## Phase 4 — Public-repo CI posture

Bundled from the "repo is public now" review. **Ship as its own PR**, separate from the branding work — different logical change per `AGENTS.md`, and it must not gate the Phase 1–3 icon PR.

- [ ] `security.yml`: add `push: branches: [main]` **and** widen both TruffleHog conditions in the same edit — PR-diff step `github.event_name == 'pull_request'` → also `'push'`; full-history step `schedule`/`workflow_dispatch` → also `'push'`. Without the second half the new trigger silently reports `TruffleHog | skipped` and ships merges with zero secret scanning, which is the exact hole this phase closes. Keep the weekly cron (it covers full-history scanning that a push-only full-history run would duplicate per merge).
- [ ] `dependency-review.yml`: do **not** add a `push` trigger (PR-diff contract has no base to diff on). Instead flip `upload-sarif: false` → `true` now that Code Scanning is live, and delete/replace the stale private-repo comments at `:24-26` and `:29-31`. Confirm the reusable workflow's `with:` surface still accepts `upload-sarif` before flipping.
- [ ] Extend the `frontend` job in `ci.yml` to run `pytest scripts/tests/ -v` alongside `src/frontend/tests/` (same `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1` env). This closes a pre-existing gap and is what makes Phase 3's launcher test meaningful in CI. Prefer one extra step over a new job so the existing required-check name stays stable. If the pre-existing `scripts/tests/` failures block a green run, land the job change as its own PR and record the failures rather than skipping the directory.
- [ ] Do **not** add a CodeQL workflow — GitHub's automatic default setup already analyzes `main` (4 alerts to date), and a second setup duplicates work and can conflict.
- [ ] Do **not** add a dependency-review job for `main`; `merge_group` already covers batched merges, and `dependency-review-action` is deliberately not in use.
- [ ] Retire the cost premise in `2026-07-22-reduce-github-actions-billable-minutes.md`: the repo is public, so its 503-min/month model and its "low risk because no required-checks on a Free private repo" reasoning (`:126`, `:176`) are obsolete. Read it as *already delivered and no longer worth executing* — the Security Scan consolidation in it is still good for wall-clock feedback — then close the plan and drop its `TO_DO.md:63` entry rather than executing the remaining phases.
- [ ] Record the newly-available, currently-unconfigured capability in `TO_DO.md` rather than silently enabling it: branch protection on `main` is now permitted (tier blocker lifted; `404 Branch not protected` today). Enabling it is a judgment call about required checks — decide separately, do not bundle it here.
- [ ] Verify by opening a throwaway PR touching `**.py` and one touching only `**.md`, and confirm `Security Scan` and `OSV PR Scan` run/skip as the path filters intend.

## Phase 5 — Docs, verification, and ship

- [ ] Add a `CHANGELOG.md` **Unreleased → Added** entry: window icon when running from source, README logo/badges, and the `SpotiBye.command` launcher. User-visible, so `CHANGELOG.md` is required (any internal-only leftovers go to `dev-docs/backlog/maintenance-log.md` instead).
- [ ] Log the Phase 4 CI changes in `dev-docs/backlog/maintenance-log.md`, not `CHANGELOG.md` — trigger/SARIF changes are internal tooling with no user-facing behavior change.
- [ ] Fix the stale icon paths in `dev-docs/guides/frontend-distribution-guide.md:25-28` to point at `resources/` instead of the nonexistent `src/frontend/assets/`, and add a short "running from source" section pointing at `SpotiBye.command` and the runtime window icon.
- [ ] Mention the launcher in the README Development section next to the existing `verify-all.sh` line.
- [ ] Link this plan from `dev-docs/backlog/TO_DO.md` (backlink added at authoring time; remove the entry when the plan completes) and index it in `dev-docs/exec-plans/active/README.md` (done at authoring time).
- [ ] Run, from the repo root: `./scripts/verify-all.sh`, `.venv/bin/basedpyright src/frontend src/shared scripts --level error`, `scripts/check-repo-structure.sh`, and `scripts/check_docs_hygiene.py`. Frontend tests must use `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v` from the repo root.
- [ ] Two-reviewer pass before opening the PR, per repo practice for user-facing changes.
- [ ] Open the PR as one logical change; split Phase 3 into its own PR if the diff exceeds ~400 lines. **Phase 4 ships as a separate PR** and must not gate the Phase 1–3 branding PR.
- [ ] On merge: move this plan to `dev-docs/exec-plans/completed/`, index it in `completed/README.md`, drop the `TO_DO.md` backlink, and confirm the active-plan hygiene checks are quiet.

---

## Open decisions (resolve in the phase named, record the outcome here)

- [ ] Window icon from the masked or unmasked PNG — recommendation: unmasked (Phase 1 step 1 rationale).
- [ ] Whether the `SetFile` path can be trusted as the primary mechanism, or whether `osascript`/Finder should lead. Depends on the Finder rendering check in Phase 3; `SetFile` was never observed to produce a readable icon payload in this environment.
- [ ] Whether the icon sentinel file or the `xattr` flag check is the primary idempotency guard.
- [ ] Phase 4: whether full-history TruffleHog should run on **every** `main` push or only on the weekly cron once a `push` trigger exists. Running it per-merge is the safer default but noticeably slower; decide from the first push-trigger run's wall time.

## Out of scope

- New or redesigned icon artwork, and regenerating a fresh `.icns`/`.ico` from an iconset (`iconutil` rejected a locally built iconset during authoring; the shipped `.icns` is valid and is reused as-is).
- Changing the icon wiring in `spotibye.spec` or the Linux `.desktop` entry — both already work.
- Windows `.bat`/`.cmd` and Linux `.desktop` launchers (Windows cannot set per-file icons from a script).
- An `.app` bundle for source runs (that is the packaging path's job).
- README banner art beyond the logo; the 320 px copy is the whole scope.
- Adding a CodeQL workflow — GitHub's automatic default setup already analyzes `main`; a second setup duplicates work and can conflict.
- Enabling branch protection on `main`. The tier blocker is gone, but required-check selection is a separate judgment call (recorded as a Phase 4 `TO_DO.md` entry, not done here).
- Restoring Actions minute budgeting of any kind — public repos are unmetered, so the whole optimization category is moot.

## Deferred (recorded here, per repo rule)

- Compressing or replacing the 1.8 MB `.icns` and 727 KB `.ico` with modern-format equivalents — separate packaging task.
- `dev-docs/guides/frontend-distribution-guide.md` is broadly stale beyond the icon paths (it references `src/spotify_playlist_exporter_v2`, iOS/Kivy-ios, and an older spec layout). A full refresh is its own plan; this plan only fixes the lines it touches.
- `src/frontend/utils/platform_utils.py` has no dedicated test module; Phase 1 adds one for the icon path only, not a general suite.
- The 3 open Dependabot alerts and the weekly full-history TruffleHog scan's runtime on `main` are untouched — Phase 4 changes trigger timing only, not scan policy.
- `SECURITY.md` still describes the repo's private-era posture; Phase 4 updates the workflow rationale comments but a doc-wide refresh is separate.
