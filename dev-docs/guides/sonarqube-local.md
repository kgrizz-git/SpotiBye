# Local SonarQube Analysis

Run SonarQube Community Build locally to get static-analysis reports (bugs,
vulnerabilities, code smells, security hotspots) for this repo. Useful for a
quick quality check without CI.

## Prerequisites

- Docker (this setup uses [Colima](https://github.com/abiosoft/colima) for a
  headless VM on macOS; Docker Desktop works too)
- `sonar-scanner` CLI (`brew install sonar-scanner`)

## Start SonarQube

```bash
# One-time: start the headless Docker VM with enough RAM for SonarQube
colima start --memory 4 --cpu 2 --disk 20

# Start the SonarQube Community container (first boot takes ~1-2 min)
docker run -d --name sonarqube -p 9000:9000 \
  -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true sonarqube:community
```

Web UI: <http://localhost:9000> (default login `admin` / `admin`).

To bring it back after a reboot:

```bash
colima start --memory 4 --cpu 2 --disk 20
docker start sonarqube
```

## Scanner token

The scanner token lives in **`.sonar_token`** at the repo root. That file is
git-ignored (see `.gitignore`), so it never gets committed. If the token is
lost or the container was recreated, regenerate one:

```bash
curl -u admin:admin -X POST \
  "http://localhost:9000/api/user_tokens/generate?name=local-scanner" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])"
```

…then overwrite `.sonar_token` with the new value.

## SonarQube Cloud token

Keep the project-specific cloud token in the ignored `.sonar_cloud_token` file
at the repository root. The scanner does not read this file itself; map it to
`SONAR_TOKEN` only for the command that needs it. In CI, store the same value
as the CI secret `SONAR_TOKEN` instead.

```bash
SONAR_TOKEN="$(cat .sonar_cloud_token)" sonar-scanner \
  -Dsonar.host.url=https://sonarcloud.io
```

The cloud project key and organization must be configured separately; never add
the token to `sonar-project.properties`.

## Run an analysis

```bash
export SONAR_TOKEN="$(cat .sonar_token)"
sonar-scanner -Dsonar.host.url=http://localhost:9000
```

The scanner reads project settings from `sonar-project.properties`
(`sonar.projectKey=spotibye`). The project is auto-provisioned on first run.
Results: <http://localhost:9000/dashboard?id=spotibye>

## Coverage (optional)

Community Edition imports per-language coverage but does **not** show a single
merged coverage % (that is an Enterprise feature). Generate coverage before
scanning:

```bash
# Backend (TypeScript) — writes src/backend/coverage/lcov.info
cd src/backend && npm run test:coverage

# Frontend (Python) — writes coverage-python.xml at repo root
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 \
  .venv/bin/pytest src/frontend/tests/ \
  --cov=src/frontend --cov-report=xml:../../coverage-python.xml
```

The report paths are already wired in `sonar-project.properties`.

## Reset

```bash
docker rm -f sonarqube   # drops the in-container H2 database
colima stop              # stop the VM when done
```
