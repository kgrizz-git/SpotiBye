# Configuration Sources and Precedence

This is the canonical guide for where SpotiBye reads configuration, credentials,
and deployment settings. Read it before adding an environment variable or a
secret.

## Quick reference

| Concern | Put it here | Committed? | Read by |
|---|---|---:|---|
| Desktop-app URL, feature, or performance override | The process environment used to launch the app | No | `src/frontend/config/backend_config.py` |
| Desktop-app configuration template | `.desktop.env.example` | Yes, placeholders only | Humans; it is **not** auto-loaded |
| Desktop-app local override | `.desktop.env.local` | No | Shell/IDE only when explicitly loaded |
| Local Worker secrets | `src/backend/.dev.vars` | No | `wrangler dev` |
| Local Worker secret template | `src/backend/.dev.vars.example` | Yes, placeholders only | Humans |
| Local Worker environment-specific secrets | `src/backend/.dev.vars.development` (or another Worker environment) | No | `wrangler dev --env <environment>` |
| Deployed Worker non-secret configuration and bindings | `src/backend/wrangler.toml` | Yes | Cloudflare Worker `env` binding |
| Deployed Worker credentials | Cloudflare Worker secrets, set with `wrangler secret put --env <environment>` | No | Cloudflare Worker `env` binding |
| Backend test values | `src/backend/.env.test` and test helpers | Yes, test-only values | Vitest setup |
| Local SonarQube token | `.sonar_token` | No | Explicit shell command only |
| SonarQube Cloud token | `.sonar_cloud_token` locally; `SONAR_TOKEN` in CI | No | Explicit scanner command or CI |

Never put a real credential, access token, or account-specific secret in an
example file, `wrangler.toml`, source code, a command line, or a commit.

## Desktop application configuration

The frontend only reads the environment inherited by its process. It does not
call a dotenv loader, so creating a file alone has no effect. The committed
`.desktop.env.example` is only a template.

To use a local file as a launcher convenience, source it explicitly before
starting the app, or configure the variables in the IDE/run configuration:

```bash
set -a
source .desktop.env.local
set +a
# Run the desktop app using the normal project command.
```

`.desktop.env.example` is a portable template, not a configuration source. Copy
it to `.desktop.env.local` only when you intend to source that file yourself.

### Frontend precedence

For ordinary frontend settings, an explicitly set process environment variable
takes priority over the code default. Backend endpoint selection is intentionally
different:

1. A valid saved choice in `~/.spotibye_cache/backend_selection.json`.
2. A valid configured startup URL: `SPOTIBYE_BACKEND_URL`, or
   `SPOTIBYE_PRODUCTION_BACKEND_URL` when `SPOTIBYE_USE_PRODUCTION=true`.
3. No endpoint. The selector opens in a blank **Custom** state and the app does
   not create a backend client until the user selects a valid URL.

The backend selector can subsequently choose a URL at runtime and persists the
user's selection in the user-private `~/.spotibye_cache` directory. That choice
does not create or modify an environment variable.

Useful URL variables are:

```bash
# Optional environment startup choice
SPOTIBYE_BACKEND_URL=https://your-default-backend.example

# Optional named selector presets; Localhost is always an explicit preset.
SPOTIBYE_DEV_BACKEND_URL=https://your-dev-backend.example
SPOTIBYE_PRODUCTION_BACKEND_URL=https://your-prod-backend.example
```

Use placeholders in committed documentation and examples. Worker URLs are not
credentials, but account-specific URLs do not belong in a reusable template.
Neither a placeholder nor an absent value is treated as a usable endpoint.

## Local Cloudflare Worker configuration

The backend's Wrangler project directory is `src/backend/`, alongside
`wrangler.toml`. Put local Worker credentials in
`src/backend/.dev.vars`, for example:

```dotenv
SPOTIFY_CLIENT_ID="your-local-client-id"
SPOTIFY_CLIENT_SECRET="your-local-client-secret"
JWT_SECRET="generate-a-unique-local-secret"
```

Start it with:

```bash
cd src/backend
npm run dev
```

Use `src/backend/.dev.vars.example` as the committed template for this file.

Use one local-file family: `.dev.vars` **or** `.env`, not both. This project
uses `.dev.vars` for secrets because it makes the Worker-specific scope clear.
Wrangler does not import arbitrary shell variables into the Worker by default.

### Local Worker precedence

When using the recommended `.dev.vars` family:

1. `src/backend/.dev.vars.<environment>` is used by
   `wrangler dev --env <environment>` and replaces generic `.dev.vars`.
2. Otherwise, `src/backend/.dev.vars` supplies local values.
3. Non-secret defaults and bindings come from `wrangler.toml`.

If the `.env` family is used instead, Wrangler loads and merges files in this
order, most specific first:

1. `.env.<environment>.local`
2. `.env.local`
3. `.env.<environment>`
4. `.env`

Cloudflare documents the full local-development behavior in its
[environment variables and secrets guide](https://developers.cloudflare.com/workers/local-development/environment-variables/).

## Deployed Cloudflare Worker configuration

`src/backend/wrangler.toml` defines versioned, non-secret configuration:

- `ENVIRONMENT` and allowed redirect URIs
- KV, Queue, and Durable Object bindings
- development and production environment names/bindings

Deploy credentials are not in the repository. The Worker reads
`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `JWT_SECRET` from Cloudflare
Worker secrets. Set or rotate one interactively:

```bash
cd src/backend
npx wrangler secret put JWT_SECRET --env development
```

Use `npm run deploy:dev` or `npm run deploy:prod` for normal deployments. The
deployment script additionally supplies `RELEASE_SHA`, `RELEASE_VERSION`, and
`DEPLOYED_AT` for that release. Do not define the same sensitive name as both a
Wrangler `vars` entry and a Worker secret.

For the current Cloudflare model, see the official documentation on
[environment variables](https://developers.cloudflare.com/workers/configuration/environment-variables/)
and [environments](https://developers.cloudflare.com/workers/wrangler/environments/).

## Tests

Backend tests load `src/backend/.env.test`, then test setup and helper factories
set fixed non-production values. Do not put real credentials in test files.
Frontend tests set and restore their own environment values per test.

## Sonar tokens

The scanner does not read either desktop configuration file automatically.

- Local SonarQube: `.sonar_token` is ignored. The documented command explicitly
  maps its value to `SONAR_TOKEN`.
- SonarQube Cloud: keep a local project-specific token in the ignored
  `.sonar_cloud_token` file, then explicitly map it to `SONAR_TOKEN` for the
  scan. In CI, set `SONAR_TOKEN` as a CI secret. Do not store it in
  `sonar-project.properties`.

See [Local SonarQube Analysis](sonarqube-local.md). Sonar's guidance is to use
the `SONAR_TOKEN` environment variable rather than placing a token in scanner
configuration.

## Adding or changing a value

1. Classify it: frontend runtime setting, local-only Worker secret, deployed
   Worker configuration, deployed Worker secret, test fixture, or scanner token.
2. Put it in the source listed in the quick-reference table.
3. Add placeholders and explanatory comments to a tracked example only when a
   developer must create a local value.
4. Update the relevant type/validation and this guide.
5. Verify the affected startup, test, or deployment path without printing the
   secret.
