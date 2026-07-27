# OSV-Scanner Findings Playbook

> What to do when the weekly Security Scan on `main` goes red, or when the pre-push `osv-scanner` hook blocks a push with a dependency advisory.
> The policy is **fail on findings** — this guide is the decision tree for resolving each finding, not for suppressing the policy.

---

## Where OSV-Scanner runs

| Surface | Trigger | Mechanism |
|---|---|---|
| `.github/workflows/security.yml` | PR to `main`/`develop`/`WIP`, weekly schedule (Mon 00:00 UTC), manual dispatch | `google/osv-scanner-action/osv-scanner-action@<sha>` Docker action. Sub-action only accepts `scan-args`; no `fail-on-vuln` knob at this layer. Always exits non-zero on findings. |
| `.pre-commit-config.yaml` | `pre-push` stage | `google/osv-scanner` pre-commit hook rev `vX.Y.Z`. Pre-commit bootstraps Go automatically. |

Both surfaces must point at the **same scanner engine version**. Bump them together: when the GitHub Action sub-action SHA changes (typically via Dependabot PR), also update the pre-commit hook `rev` in the same PR, and vice-versa.

When the GitHub Action bumped, also check the `google/osv-scanner` (CLI repo) tag matching the Docker image tag the action uses (e.g. action docker image `v2.3.8` ↔ CLI tag `v2.3.8`). They are separate repos and are not version-locked; mismatched versions produce subtle drift between local and CI results.

---

## Decision tree for a finding

Work down the list. Stop at the first option that resolves the finding **without suppression**. Suppression (`osv-scanner.toml` `[[IgnoredVulns]]`) is a last resort, never a default.

### 1. Bump a direct dependency (preferred)

Applies when the advisory lists a fixed version and the affected package is a direct dep you constrain.

- Python (`requirements.txt`): raise the version floor, e.g. `pillow>=12.2.0` → `pillow>=12.3.0`. Verify the patched release exists (`pip index versions pillow` or PyPI JSON API) before bumping.
- npm (`package.json` `dependencies` or `devDependencies`): bump the semver range; run `npm install` in `src/backend/` to regenerate the lockfile.

Always confirm the lockfile actually moved to the patched version, not just that the manifest floor changed.

### 2. Add or bump an npm `overrides` entry

Applies when the advisory is in a transitive that the parent package's semver range won't lift on its own, and the patched version is API-compatible across majors for your usage.

Example (the 2026-07-27 PR #58): `brace-expansion` had advisories in `1.1.16`, `2.1.2`, and `5.0.7`. No patched `1.x` or `2.x` existed. The `^1` and `^2` callers (legacy `glob`/`minimatch`) only use `balanced-match` and `concat-map`, which behave identically across `brace-expansion` majors. A single unconditional override collapsed all three to `5.0.8`:

```json
"overrides": {
  "brace-expansion": "5.0.8"
}
```

Collapsing existing per-major pins (e.g. `"brace-expansion@1": ...`) to a unified override is preferred when feasible — fewer pins to keep fresh. Stale pins are how PR #58's failure happened: the prior pins were themselves vulnerable.

After changing `overrides`, re-run:

```bash
cd src/backend
npm install        # regenerates package-lock.json
npm run build && npm run test:run && npm run lint
```

Verify the lockfile resolved the patched versions (e.g. `rg "brace-expansion/-/" package-lock.json` should show one entry at the new version) and that `npm audit` reports 0 vulnerabilities.

### 3. Update the parent package

Applies when the parent is the source of the bad transitive range and a newer parent release brings in a fixed child range.

Example: `postcss@8.5.16` came via `vite@8.1.4`'s transitive range. A direct `overrides.postcss` was added in PR #58, but the alternative would have been waiting for / bumping to a `vite` release that pulls `postcss >= 8.5.18`.

Prefer option 2 (`overrides`) when the override is narrow and durable; prefer option 3 when the parent bump carries other worthwhile fixes or the override would sprawl across many packages.

### 4. Suppress with `osv-scanner.toml` (last resort)

Use **only** when all three conditions hold:

1. The advisory is in a transitive whose parent caps a range **and** a major-bump override would break the parent's API.
2. No patched version exists anywhere in the affected major line(s).
3. There is a credible, written reason the vulnerable code path is never reached by this repo (e.g. the vuln is in a feature the dep never imports, or an attack surface that doesn't exist for the way we use it).

Place `osv-scanner.toml` in the directory the scanner is invoked from (the repo root for the current `scan-args: -r ./` configuration). The file only applies to lockfiles in its own directory; it does **not** propagate to subdirectories.

```toml
[[IgnoredVulns]]
id = "GHSA-xxxx-xxxx-xxxx"
reason = "<one-sentence justification, named attack surface and why it doesn't apply>"
ignoreUntil = 2026-10-31   # YYYY-MM-DD — required by repo policy; absence is a smell
```

Rules for suppression entries:

- **Always set `ignoreUntil`.** Open-ended suppressions accrete. Default to a 30-day window; revisit before expiry.
- **Always write a specific `reason`.** Not "doesn't apply" — name the code path, attack surface, or usage restriction that makes it non-exploitable.
- **Re-evaluate on each Dependabot bump.** Often a parent update silently fixes the underlying advisory and the suppression can be deleted.
- **Track in CHANGELOG.** Adding or removing a suppression is a security-policy change; note it under `### Changed` or `### Fixed`.

When the suppression expires, either re-justify with a fresh `ignoreUntil` and updated reasoning, or move to option 1/2/3 if upstream has since shipped a fix.

---

## Verifying a fix end-to-end

1. **Local**: run `pre-commit run --hook-stage pre-push osv-scanner` (or `osv-scanner scan source -r .` if you have the binary). Must exit 0.
2. **Backend**: `cd src/backend && npm run build && npm run test:run && npm run lint`. All must pass.
3. **Lockfile audit**: `cd src/backend && npm audit` must report 0 vulnerabilities.
4. **CI**: after merge, watch the next weekly scheduled run (or trigger `workflow_dispatch` on `main`) and confirm it goes green. The Security Scan job in `security.yml` is the source of truth — the pre-push hook only covers what's in your local checkout path.
5. **CHANGELOG**: any user-visible bump or suppression gets a `### Fixed` or `### Changed` entry per the repo Changelog Rule.

---

## Anti-patterns

- **Flipping `fail-on-vuln: false` at the sub-action layer** — the sub-action doesn't accept this input; setting it is a no-op that pretends to be a fix. The reusable workflow (`osv-scanner-reusable.yml`) does accept it, but disabling failure-on-findings repo-wide violates the policy above.
- **Adding `|| true` to the OSV step in `security.yml`** — same problem, more obvious.
- **Pinning a vulnerable version "for stability"** then ignoring OSV findings on it — that's how PR #58's failure was born. Pins are not a security tool; if you pin, you inherit the responsibility to track advisories on the pinned version.
- **Suppression files without `ignoreUntil` or with boilerplate reasons** — these become invisible permanent debt. Every entry should have an owner and an expiry.
