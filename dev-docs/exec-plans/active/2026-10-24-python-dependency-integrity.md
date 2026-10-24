# Python Dependency Integrity — installed-env audit, exact versions, local drift checks

**Date:** 2026-10-24
**Branch:** `chore/python-dependency-integrity`
**Status:** draft v1 — pending external review (cursor grok-4.7 high)
**Backlog link:** `dev-docs/backlog/TO_DO.md` → "Python dependency integrity" under **Security & Dependency Integrity**
**Origin:** PR #64 (Pillow 13.0.0 / urllib3 2.8.0 / undici 7.30.1)

## Problem

Every finding below was reproduced on 2026-10-24; commands are in PR #64 and the review threads.

1. **OSV-Scanner cannot evaluate a `>=` spec.** `pillow==12.3.0` → 41 findings. `pillow>=12.3.0` → "No issues found". Our only enforced Python dependency gate was therefore vacuous for every floored package.
2. **`pip-audit -r requirements.txt` audits a hypothetical fresh install.** It resolved 18 packages and picked `pillow 13.0.0` / `urllib3 2.8.0` (newest allowed) while the actual `.venv` held `12.2.0` / `2.7.0`. It was not wrong about which packages matter — it was scanning the wrong versions.
3. **GitHub cannot see our Python versions either.** The dependency graph reports `versionInfo: None` for `pillow` and `urllib3` (exact pin `requests 2.34.2` resolves fine). A dependency with no version cannot raise a Dependabot alert; the only alerts on the repo are three stale, already-fixed `brace-expansion` entries.
4. **`build.yml` resolves versions at build time.** It installs `-r requirements.txt` on every release run, so two builds of the same commit can bundle different Pillow/urllib3 versions, and nothing audits what was actually bundled.
5. **`SECURITY.md` contradicts `.pre-commit-config.yaml`.** The doc says pre-push runs `check-dependencies.py --security` (pip-audit); the hook config says OSV-Scanner is canonical and `check-dependencies.py` is ad hoc only.

One root cause: **no exact Python version exists anywhere in the repo**, so OSV, Dependabot, the SBOM and the release build all either guess or resolve upward. Adding a fourth scanner would not have changed any of the five findings above.

## Goal

Three properties, in priority order:

1. The environment a developer runs, and the environment `build.yml` ships, contain the versions the repo declares.
2. Something fails when they do not.
3. Every shipped version has an exact identity that external scanners can evaluate.

## Non-goals

- No new scanning vendors. OSV-Scanner, pip-audit, Bandit, Semgrep and TruffleHog already cover dependency, code and secret surfaces; the gap is resolution, not coverage.
- No npm work. The backend lockfile already gives exact versions — undici was caught the day its advisories published.
- No routine dependency upgrades beyond what integrity requires.

## On the "check the venv when entering the directory" proposal

The goal is right; the mechanism is not. A `cd` hook (direnv `.envrc` or a `chpwd`/`PROMPT_COMMAND` function) is rejected because:

- it needs direnv or a per-user shell function — not in the prerequisites, not shared with contributors, invisible to CI, and awkward on Windows;
- it fires at directory entry, which is not when correctness matters, and it fires constantly — a warning at `cd` is precisely the signal people learn to ignore;
- it can only warn. Blocking a `cd` on a dependency mismatch is hostile.

What the hook is trying to prevent is a **stale `.venv`**, and the repo already has two triggers that are shared, visible and CI-mirrored: `./scripts/verify-all.sh` and pre-push. The check belongs there (Phase 1).

Second nuance: "meets floors" is not sufficient. The stale venv held `pillow 12.2.0`, which *violated* the declared `>=12.3.0` floor and still ran fine for weeks. The check must compare installed versions against exact pins as well, and report drift above a pin.

## Phases

### Phase 1 — Installed-vs-declared check, shareable and always-on

- [ ] Extend `scripts/check-dependencies.py` with an installed-environment mode (`--verify-installed`, plus `--json`) instead of adding a second dependency-check script. It parses `requirements.txt`, reads versions via `importlib.metadata`, and reports: missing package, version below floor, version above an exact pin, exact-pin mismatch. Extra installed packages are warnings, not failures.
- [ ] Failure output ends with the one copy-pasteable remediation: `.venv/bin/pip install -r requirements.txt`.
- [ ] Add `scripts/tests/test_check_dependencies_venv.py` covering: clean environment, below-floor, missing package, exact-pin mismatch, extra package (warn only), and a pinned package installed *newer* than declared.
- [ ] Call it from `scripts/verify-all.sh` before the frontend suite (honour the existing `--dry-run` short-circuit).
- [ ] Add a `language: system` pre-push hook in `.pre-commit-config.yaml` that runs the same mode with `.venv/bin/python`. No network, sub-second.
- [ ] Document the check in `AGENTS.md` ("Running Tests & Verification") and `SECURITY.md`.

### Phase 2 — Audit the environment that actually runs and ships

- [ ] `ci.yml` frontend job: after `pip install -e ".[development]"`, run `python -m pip_audit --skip-editable` (pip-audit is already a dev extra). Blocking.
- [ ] `build.yml`: after `Install Python dependencies`, run the same audit against the exact environment PyInstaller bundles. Blocking, because this is the artifact users receive.
- [ ] Make the audit resilient: bounded retries and a distinct exit path for "the check could not run" versus "a vulnerability was found", so an OSV/PyPI outage fails loudly instead of silently passing.
- [ ] `scripts/check-dependencies.py`: audit the current environment by default; keep manifest resolution behind an explicit `--manifest` flag so the existing `-r` behaviour stays available but is no longer the default.

### Phase 3 — Give Python exact versions (decision + implementation)

- [ ] Decide between the two options below and record the choice in `dev-docs/architecture/design-decisions/`.
- [ ] Option A — exact pins in `requirements.txt`/`pyproject.toml` for every direct dependency plus the transitives we have had advisories in. ~10 lines, no new tooling, makes OSV/Dependabot/SBOM work for those packages. Leaves unlisted transitives unpinned, so the drift returns the next time someone adds a dependency.
- [ ] Option B (recommended) — generate a lockfile from `pyproject.toml` with `uv pip compile` (`requirements.lock`, `requirements-dev.lock`), and consume it in `build.yml` and `ci.yml`. Exact versions for the whole tree, hash-pinnable, visible to OSV, Dependabot and the SBOM, and reproducible across builds of the same commit. Costs: `astral-sh/setup-uv` pinned by SHA on the runners, a regeneration step, and platform-marker handling (see Risks).
- [ ] If B: add a drift gate so a lock that no longer matches `pyproject.toml` fails CI (regenerate-and-diff, or the tool's `--check` equivalent).
- [ ] If B: document lock regeneration next to the Dependabot bump instructions; a Dependabot PR that bumps `pyproject.toml` without regenerating the lock must fail the gate.
- [ ] Re-run the Phase 2 audit against the locked environment and confirm it is clean before landing.

### Phase 4 — Prove the alerting surfaces now work

- [ ] After Phase 3 lands, confirm the SBOM records versions: `gh api repos/kgrizz-git/SpotiBye/dependency-graph/sbom` should show non-null `versionInfo` for `pillow`/`urllib3`.
- [ ] Confirm Dependabot evaluates them (`gh api repos/kgrizz-git/SpotiBye/dependabot/alerts`) and enable Dependabot security updates in repo settings if they are off.
- [ ] Record before/after output in the PR so the next reader can tell the difference between "no findings" and "not evaluated".

### Phase 5 — Documentation truth

- [ ] Reconcile `SECURITY.md` with `.pre-commit-config.yaml` on what pre-push actually runs.
- [ ] Add a short layered-model table to `SECURITY.md`: exact-version scanning (OSV-Scanner, lockfile/pins), installed-environment audit (pip-audit), code SAST (Bandit/Semgrep), secrets (TruffleHog) — with the stated limitation of each.
- [ ] Cross-link from `dev-docs/guides/osv-scanner-findings-playbook.md`.

## Acceptance criteria

- A stale environment fails `./scripts/verify-all.sh` and names the remediation command. Demonstrated by a unit test, not only by manual downgrade.
- CI fails when a known-vulnerable version is installed; demonstrated once with a throwaway commit (downgrade `pillow`, watch the job go red, revert).
- `build.yml` audits the environment it bundles, and a vulnerable version there blocks the release.
- After Phase 3, `pillow`/`urllib3` have non-null `versionInfo` in the SBOM, and OSV-Scanner's Python result stops being vacuous.
- `verify-all.sh` wall time grows by < 5 s on a warm environment.

## Risks

- **Kivy on Windows.** `kivy-deps.*` wheels are Windows-only and are not installed from `requirements.txt` today. A lock generated on Linux/macOS may not resolve on the Windows runner. Verify `build.yml`'s Windows path before choosing Option B; may require a universal lock or a per-platform lock.
- **Hash-pinned lock vs editable install.** `pip install -e ".[development]"` conflicts with a fully pinned tree unless installed with `--no-deps` after the lock.
- **New CI network dependency.** pip-audit calls the OSV/PyPI APIs; needs bounded retries and a clear distinction between "could not check" and "check found a vulnerability".
- **Dependabot cannot regenerate pip lockfiles.** Without the Phase 3 drift gate the lock rots and every check stays green — worse than no lock, because it looks authoritative.
- **Pinning transitives slows security response.** Every advisory bump becomes a lock edit; document `uv lock` refresh so it is routine rather than a puzzle.

## Open questions for review

1. Is the diagnosis right, or is there a cheaper fix that gets the same three properties?
2. Is Phase 3 Option B (lockfile) justified given the Kivy/Windows complication, or does Option A (exact pins) capture most of the value at a fraction of the risk?
3. Is rejecting the `cd` hook correct, or is a lightweight opt-in `direnv` snippet worth shipping as developer ergonomics alongside the enforced pre-push check?
4. What is missing that would still let a vulnerable version reach a user?
