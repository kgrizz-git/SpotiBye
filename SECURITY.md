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
- **pip-audit**: Scans Python dependencies for known vulnerabilities
- **npm audit**: Scans Node.js dependencies for known vulnerabilities
- **Dependency Review**: GitHub-native PR dependency scanning

### Infrastructure as Code (IaC) Scanning
- **Checkov**: Scans Cloudflare Workers configuration and Terraform

## CI/CD Security Workflow

Security scans run on:
- Every push to `main` or `develop` branches
- Every pull request to `main` or `develop`
- Weekly scheduled scans (Mondays at midnight UTC)
- Manual workflow dispatch

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
2. Email the maintainers directly with details
3. Allow time for assessment and patch before disclosure

## Security Hardening Checklist

- [x] Secret scanning (TruffleHog, Gitleaks)
- [x] SAST (Semgrep, Bandit)
- [x] Dependency scanning (pip-audit, npm audit)
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
| `semgrep` | Lightweight SAST security scan |
| `bandit` | Python security linting |
| `ruff` | Python linting and formatting |
| `eslint` | JavaScript/TypeScript linting |

### Pre-push Hooks (run before every push)

Longer-running checks that ensure code quality:

| Hook | Purpose |
|------|---------|
| `python-tests` | Runs Python test suite |
| `node-tests` | Runs Node.js test suite |
| `security-scan` | Full dependency security scan |

### Manual Usage

```bash
# Run all pre-commit hooks on all files
pre-commit run --all-files

# Run only pre-push hooks
pre-commit run --hook-stage pre-push --all-files

# Run specific hook
pre-commit run bandit --all-files

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
