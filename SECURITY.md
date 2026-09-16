# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Tools and Scanning

This project uses multiple security scanning tools integrated into CI/CD:

### Secret Detection
- **TruffleHog**: Scans for hardcoded secrets in commits and PRs
- **Gitleaks**: Pre-commit hook to prevent secrets from being committed

### Static Application Security Testing (SAST)
- **Semgrep**: Multi-language SAST with OWASP Top 10, CWE Top 25, and custom rules
- **Bandit**: Python-specific security linter
- **ESLint**: TypeScript/JavaScript security rules (via @typescript-eslint)

### Dependency Scanning
- **OSV-Scanner**: Unified Python + Node.js dependency vulnerability scanning (CI and pre-push)
- **Dependency Review**: GitHub-native PR dependency scanning

### Infrastructure as Code (IaC) Scanning
- **Checkov**: Scans Cloudflare Workers configuration and Terraform

## CI/CD Security Workflow

Security scans run on:
- Every push to `main` or `develop` branches
- Every pull request to `main` or `develop`
- Weekly scheduled scans (Mondays at midnight UTC)
- Manual workflow dispatch

**Path-filter note:** PR workflows only run when changed files match the `paths:` filters in `security.yml` (source, manifests, workflow). PRs that touch only docs or unrelated config may not re-run dependency scans; the weekly schedule still scans installed dependencies for newly disclosed CVEs.

### Workflow Files
- `.github/workflows/security.yml` - Main security scanning workflow
- `.github/workflows/dependency-review.yml` - PR dependency review
- `.pre-commit-config.yaml` - Local pre-commit security hooks

## Local Development Security

Install pre-commit hooks to catch security issues before commit:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Report it through a [private security advisory](https://github.com/kgrizz-git/SpotiBye/security/advisories/new) with details (Security tab → Advisories → Report a vulnerability)
3. Allow time for assessment and patch before disclosure

## Security Hardening Checklist

- [x] Secret scanning (TruffleHog, Gitleaks)
- [x] SAST (Semgrep, Bandit)
- [x] Dependency scanning (OSV-Scanner)
- [x] Automated dependency updates (Dependabot)
- [x] IaC scanning (Checkov)
- [x] Pre-commit hooks (secrets, linting, SAST)
- [x] Pre-push hooks (tests, full security scan)
- [x] CODEOWNERS for security-sensitive files
- [x] Branch protection with required reviews
- [x] Concurrency controls to prevent conflicting deployments

## Automated Dependency Updates (Dependabot)

Dependabot is configured in `.github/dependabot.yml` to automatically:

- Monitor Python (`pip`) dependencies weekly
- Monitor Node.js (`npm`) dependencies weekly
- Monitor GitHub Actions weekly
- Monitor Docker images weekly (if applicable)
- Create grouped PRs for minor/patch updates to reduce noise

### Enable Dependabot in GitHub

1. Go to **Settings → Security → Code security and analysis**
2. Enable **Dependabot alerts**
3. Enable **Dependabot security updates** (auto-create PRs for CVEs)
4. Enable **Dependabot version updates** (auto-create PRs for outdated deps)

### Dependabot Groups

To reduce PR noise, updates are grouped by:
- **Minor/Patch updates**: Grouped into single PRs
- **Major updates**: Separate PRs (require manual review)
- **Development vs Production**: Separate groups for Node.js deps

## Pre-commit and Pre-push Hooks

Git hooks run automatically at certain points in the git workflow to catch issues before they reach the repository.

### Installation

**Quick setup (recommended):**
```bash
# Run the setup script
./scripts/setup-hooks.sh
```

**Manual setup:**
```bash
# Install pre-commit framework
pip install pre-commit

# Install hooks (one-time setup)
pre-commit install --hook-type pre-commit --hook-type pre-push

# Verify installation
pre-commit --version
```

### Pre-commit Hooks (run on every commit)

Fast checks that run on staged files:

| Hook | Purpose |
|------|---------|
| `detect-private-key` | Blocks private keys from being committed |
| `detect-aws-credentials` | Blocks AWS credentials |
| `check-added-large-files` | Prevents committing files >500KB |
| `gitleaks` | Comprehensive secret scanning |
| `semgrep-secrets` | Secrets scan on staged files only |
| `ruff` | Python linting and formatting |
| `eslint` | JavaScript/TypeScript linting |
| `check-repo-structure` | Enforces repo structure/placement conventions |
| `prune-backups` | Removes `backups/` files older than 5 commits (staged for deletion; re-run the commit after a prune) |

### Pre-push Hooks (run before every push)

Longer-running checks that ensure code quality:

| Hook | Purpose |
|------|---------|
| `python-tests` | Runs Python test suite |
| `node-tests` | Runs Node.js test suite |
| `semgrep-sast` | Full SAST scan (OWASP Top 10, CWE Top 25) |
| `bandit-full` | Full-tree Python SAST scan (project `pyproject.toml` policy) |
| `osv-scanner` | Dependency vulnerability scan (OSV-Scanner; pre-commit bootstraps Go, no Docker needed) |
| `security-scan` | Dependency security check (`check-dependencies.py --security --ci`) |
| `basedpyright` | Python type checking of `src/frontend` and `src/shared` (`--level error`) |

### Manual Usage

```bash
# Run all pre-commit hooks on all files
pre-commit run --all-files

# Run only pre-push hooks
pre-commit run --hook-stage pre-push --all-files

# Run specific hook
pre-commit run bandit-full --hook-stage pre-push --all-files

# Skip hooks temporarily (emergency only)
git commit --no-verify -m "emergency fix"
git push --no-verify
```

### Bypassing Hooks

In emergencies, you can bypass hooks (not recommended):

```bash
git commit --no-verify  # Skip pre-commit
git push --no-verify      # Skip pre-push
```

### Dependabot vs local checks

Dependabot runs **only on GitHub** — there is no supported way to run the full Dependabot version-update engine locally against this repo. Use the mapping below instead:

| What Dependabot does | Local equivalent |
|----------------------|------------------|
| **Version updates** (weekly PRs for outdated deps) | `python scripts/check-dependencies.py --outdated` — uses `pip-review` and `npm outdated` |
| **Security updates** (CVE PRs; enable in repo settings) | `python scripts/check-dependencies.py --security` — uses `pip-audit` and `npm audit` today; OSV-Scanner (pre-push + CI) is the planned replacement |
| **Apply updates yourself** | Python: `pip-review --local --auto` · Node: `npm update` or `npx npm-check-updates -i` in `src/backend/` |

OSV-Scanner (once wired per the security tooling plan) is the best local CVE scan — it covers Python and Node lockfiles in one pass:

```bash
# Run the OSV-Scanner pre-push hook directly (pre-commit bootstraps Go for you):
pre-commit run --hook-stage pre-push osv-scanner

# Or, if you have the osv-scanner binary installed locally:
osv-scanner scan source -r .
```

Until OSV-Scanner lands, the existing script is the one-command local check:

```bash
pip install -e ".[development]"
python scripts/check-dependencies.py --security    # CVEs only
python scripts/check-dependencies.py --outdated    # version drift only
python scripts/check-dependencies.py               # both
python scripts/check-dependencies.py --security --ci  # blocking (pre-push uses this)
```

## Local Dependency Checking

For local development, use the provided script or individual tools:

### Quick Check Script
```bash
# Install development dependencies first
pip install -e ".[development]"
cd src/backend && npm install

# Run full dependency check
python scripts/check-dependencies.py

# Check only security issues
python scripts/check-dependencies.py --security

# Check only outdated packages
python scripts/check-dependencies.py --outdated

# CI mode (fails on any finding)
python scripts/check-dependencies.py --ci
```

### Individual Tools
```bash
# Unified dependency CVE scan (same engine as the CI + pre-push hook)
osv-scanner scan source -r .

# Legacy per-ecosystem security scans (still used by check-dependencies.py)
# Python security vulnerabilities
pip-audit --requirement=requirements.txt

# Python outdated packages
pip-review --local

# Node.js security vulnerabilities
cd src/backend && npm audit

# Node.js outdated packages
cd src/backend && npm outdated

# Update Node.js packages interactively
npx npm-check-updates -i
```

### Update Commands
```bash
# Auto-update Python packages
pip-review --local --auto

# Update Node.js packages
npm update

# Update Node.js to latest (including major versions)
npx npm-check-updates -u && npm install
```

## Custom Security Rules

### Semgrep Custom Rules
The project includes custom Semgrep rules in `semgrep.yml`:
- `spotify-api-key-hardcoded`: Detects hardcoded Spotify API keys
- `jwt-secret-hardcoded`: Detects hardcoded JWT secrets
- `cloudflare-api-token-hardcoded`: Detects hardcoded Cloudflare API tokens

### Bandit Configuration
Configured in `pyproject.toml`:
- Excludes: tests/, .venv/, build/, dist/
- Severity threshold: medium
- Confidence threshold: medium

## SonarCloud Security Tradeoffs

SonarCloud flags several issues that are **intentional, documented tradeoffs** for this project. They are acknowledged with inline `# NOSONAR(<rule>)` comments at the relevant `pip install` sites rather than silently suppressed.

### Python build supply chain (S8541, S6505)

- **Decision:** Omit `--only-binary=:all:` on `pip install` for the frontend (Kivy/KivyMD) and omit `--ignore-scripts` on the pinned build tool (PyInstaller).
- **Rationale:** Kivy and KivyMD do not ship binary wheels for all Linux targets and require source compilation; `--only-binary` breaks Linux/PyInstaller builds. PyInstaller is a trusted, version-pinned build dependency.
- **Mitigations:**
  - `pyproject.toml` and `requirements.txt` declare matching pinned versions; unused `pandas`/`openpyxl` were dropped so `pip install -e ".[development]"` (ci.yml) and `pip install -r requirements.txt` (build.yml) resolve deterministically and agree.
  - OSV-Scanner (CI + pre-push) and Dependabot scan all Python and Node dependencies for CVEs.
- **Risk:** Medium — accepted for cross-platform desktop build support.

### Node.js supply chain (S8541, S6505, S8544)

- **Decision:** Use `npm ci` (fully locked via `package-lock.json`) without `--only-binary`/`--ignore-scripts` overrides.
- **Rationale:** `npm ci` is deterministic; the backend dependency tree is trusted and scanned by OSV-Scanner and Dependabot.
- **Risk:** Low.

### Python path traversal (S8707)

- **Status:** Fixed. `scripts/check_file_lengths.py` validates the exemptions path against the repo root (configurable via `ALLOWED_FILE_ROOTS`) before access.

### Workflow permissions (S8233)

- **Status:** Fixed. `deployments: write` is scoped to the `deploy-dev` / `deploy-prod` jobs only; workflow-level permissions are read-only.
