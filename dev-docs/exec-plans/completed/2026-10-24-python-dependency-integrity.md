# Python Dependency Integrity — exact pins, fail-closed build audit

**Date:** 2026-10-24
**Branch:** `chore/python-dependency-integrity`
**Status:** completed 2026-10-24 — all three phases shipped in PR #65
**Backlog link:** removed from `TO_DO.md` on completion (PR #65)
**Origin:** PR #64 (Pillow 13.0.0 / urllib3 2.8.0 / undici 7.30.1)

## What actually failed (v1 got this wrong)

v1 claimed a single root cause: "no exact Python version exists anywhere in the repo." That is false — `requirements.txt` already pins `kivy==2.3.1`, `kivymd==1.2.0`, `requests==2.34.2` and `pyinstaller==6.22.3`. There are **two independent gaps plus two contributing defects**:

| # | Gap | Evidence |
|---|---|---|
| A | **The two packages that carried advisories were range-specified.** `pillow>=12.3.0`, `urllib3` unpinned. | `osv-scanner` on `pillow==12.3.0` → 41 findings; on `pillow>=12.3.0` → "No issues found" |
| B | **Nothing audited the installed or shipped closure.** `pip-audit -r requirements.txt` resolves upward to the newest allowed versions and audits a hypothetical fresh install. | It resolved `pillow 13.0.0` / `urllib3 2.8.0` while `.venv` held `12.2.0` / `2.7.0` |
| C | **Dual-manifest drift.** CI installs `-e ".[development]"` from `pyproject.toml` (kivy unpinned, no pyinstaller); `build.yml` installs `-r requirements.txt` (kivy pinned, pyinstaller included). The two paths resolve different trees. | `pyproject.toml:15` `"kivy"` vs `requirements.txt:1` `kivy==2.3.1` |
| D | **Trigger gap.** `security.yml` path filters list `requirements.txt` but not `pyproject.toml`, so a pyproject-only dependency change skips the whole Security Scan. `dependency-review.yml` lists both — asymmetric gates. | `security.yml:10-20`, `dependency-review.yml:6-12` |

**And a correction on framing:** Aikido *did* surface these advisories — that report is what started this work. It is a non-gating, off-pipeline signal, so detection existed while enforcement did not. The failure is "no enforced gate", not "no signal".

## Non-goals

- No new scanners. Detection worked; gating and resolution did not.
- No npm changes; the backend lockfile already gives exact versions and proved it (undici found the day its advisories published).
- No `cd`/direnv dependency check. Rejected: needs direnv or a per-user shell hook, invisible to CI and Windows, warns at the wrong moment, and can only warn. Releases build on clean runners, so a stale local venv is contributor ergonomics — not a release control. Recorded as a deferred item below.
- **No wholesale audit of the CI dev environment.** Measured with `.venv/bin/python -m pip_audit`: **38 advisory rows in `virtualenv` (19), `pip` (12), `filelock` (3), `setuptools` (3), `black` (1) — and zero in project dependencies.** A blanket installed-env check is red on day one for tooling users never receive, so it would be disabled rather than fixed.

## Phase 1 — Exact pins + dual-manifest drift gate (closes gap A and C)

- [x] Pin the security-relevant packages exactly in **both** manifests, matching the existing `requests==2.34.2` / `pyinstaller==6.22.3` style: `pillow==13.0.0`, `urllib3==2.8.0`.
- [x] Resolve the kivy divergence: either pin `kivy==2.3.1` in `pyproject.toml` or record why it stays unpinned. Silence here is how CI and the release build drift apart.
- [x] Add a drift check (extend `scripts/check-dependencies.py` rather than adding a second dependency script) that fails when a package is constrained differently in `requirements.txt` and `pyproject.toml`, or appears in one and not the other, with a small explicit allowlist for intentionally single-manifest entries (`pyinstaller` is build-only; dev extras are CI-only).
- [x] Wire it into `./scripts/verify-all.sh` and the CI hygiene job; add `scripts/tests/` coverage for mismatch, one-sided entry, and allowlisted entry.
- [x] Verify the payoff: GitHub's PR dependency diff (`gh api repos/kgrizz-git/SpotiBye/dependency-graph/compare/main...<branch>`) now reports `added pillow 13.0.0` / `added urllib3 2.8.0` in both manifests, replacing entries that carried `>= 13.0.0` / `>= 2.8.0` with no version (and `kivy` with an empty version). OSV-Scanner extracts both at exact versions and reports 0 advisories, so Dependabot has something to alert on.

**Acceptance:** on a branch with `pillow==12.3.0`, OSV-Scanner reports the 41 advisories. On `14.x`-style range-only specs it must not silently pass.

## Phase 2 — Fail-closed audit of the shipped closure (closes gap B)

The v1 command (`python -m pip_audit --skip-editable`) was wrong: it audits the whole interpreter including tooling. The verified recipe audits exactly what PyInstaller bundles:

```bash
python -m pip freeze --exclude-editable > "${RUNNER_TEMP}/frozen.txt"
python -m venv "${RUNNER_TEMP}/audit-env"          # auditor lives elsewhere
"${AUDIT_PY}" -m pip install "pip-audit==2.10.1"
"${AUDIT_PY}" -m pip_audit -r "${RUNNER_TEMP}/frozen.txt" --strict
```

Why each part is load-bearing (all verified locally on 2026-10-24):

- `pip freeze` omits `pip`, `setuptools` and `wheel` — installer tooling users never receive.
- `--exclude-editable` is required, not cosmetic: without it the frozen file carries the editable `spotibye` git reference and `pip-audit` fails to build it (`git fetch … not our ref`), so the audit errors out instead of auditing.
- `--strict` means "fail the entire audit if dependency collection fails"; without it a collection failure can look like a pass.
- The auditor is installed into **its own venv** rather than the build environment: installing `pip-audit` there would install its dependencies after the snapshot, mutating the tree that is about to be bundled.

Steps:

- [x] Add the recipe to `build.yml` after `Install Python dependencies`, on **every** matrix OS. Windows matters specifically: `kivy-deps.*` requirements are `sys_platform == "win32"` gated in Kivy's metadata, so only the Windows job audits what Windows bundles.
- [x] Keep it out of the ci.yml dev environment (see Non-goals) — one meaningful gate beats two, one of which is permanently red.
- [x] Prove it goes red once: a simulated build environment (`python -m venv` + `pip install -r requirements.txt`) audits green (`No known vulnerabilities found`, exit 0); downgrading Pillow to 12.3.0 in that environment makes the same command report `Found 37 known vulnerabilities in 1 package` and exit 1. Re-confirm on the real runner at the next tag build.
- [x] Record exit-code semantics in the workflow comment so a future reader knows a network/tooling failure is a hard failure, not a skip.

**Acceptance:** a vulnerable resolved closure fails the release build on every platform; a clean closure passes.

## Phase 3 — Docs truth and trigger coverage (closes gap D)

- [x] `SECURITY.md`: remove the claim that pre-push runs a `security-scan` / `check-dependencies.py --security` hook — `.pre-commit-config.yaml` runs OSV-Scanner only. Document the actual layers and the stated limitation of each: exact-version scanning (OSV), manifest drift, shipped-closure audit (pip-audit), code SAST (Bandit/Semgrep), secrets (TruffleHog).
- [x] `security.yml`: add `pyproject.toml` to the path filters so dependency-only changes cannot skip the scan.
- [x] Cross-link `dev-docs/guides/osv-scanner-findings-playbook.md` → this plan for the enforcement model.

## Deferred (recorded here, not dropped)

- **Universal lockfile** (`uv pip compile --universal --python-version 3.11` → `requirements.lock`, consumed by `build.yml` and `ci.yml`). Deferred, not rejected: it is the only option that makes non-vulnerable transitive versions reproducible, but it adds a tool to the runners, an editable-install/`--no-deps` interaction, and a drift gate that rots if Dependabot cannot regenerate it. Revisit when reproducibility is required or when a transitive advisory ships.
- **Local stale-venv check** in `verify-all.sh` / pre-push. Contributor ergonomics only (the release path never uses a developer's checkout). Revisit if a local-build release path is ever added.
- **Pinning the remaining transitives** (`charset-normalizer`, `kivy-deps.*`). Covered at ship time by Phase 2.

## Evidence (reproducible)

```text
pip-audit -r requirements.txt (before PR #64)  -> "No known vulnerabilities found"
                                                (resolved urllib3 2.8.0 / pillow 13.0.0)
.venv/bin/python -m pip_audit                  -> 38 rows: virtualenv 19, pip 12,
                                                filelock 3, setuptools 3, black 1;
                                                0 project deps
osv-scanner, pillow==12.3.0                    -> 41 findings, 5 critical (9.8, 9.2x4)
osv-scanner, pillow>=12.3.0                    -> "No issues found"
SBOM (pillow, urllib3)                         -> versionInfo: null
```
