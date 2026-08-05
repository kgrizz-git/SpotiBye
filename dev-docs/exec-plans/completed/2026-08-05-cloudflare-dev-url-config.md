# Plan: Make the Cloudflare Dev Endpoint Explicitly Configured

**Date:** 2026-08-05
**Status:** Completed

## Goal

Stop shipping the account-specific Cloudflare development Worker URL as the
fallback value of `SPOTIBYE_DEV_BACKEND_URL`, without silently selecting
localhost when no endpoint has been configured or selected.

## Current behavior

`src/frontend/config/backend_config.py` currently defaults
`SPOTIBYE_DEV_BACKEND_URL` to the project's deployed development Worker. The
backend selector always displays a **Cloudflare Dev** preset that uses that
default. This couples every desktop build to one account-specific endpoint even
when the user has not configured it.

The URL is not a credential, but it is deployment-specific configuration. It
should come from the launch environment, not a shipped source-code fallback.

## Target behavior

- A saved endpoint remains the first startup choice and opens in the selector.
- An explicitly configured `SPOTIBYE_BACKEND_URL` is the next startup choice.
- With neither value, the selector opens in an unconfigured **Custom** state;
  no backend connection is made until the user chooses a valid endpoint.
- **Localhost** remains an explicit selectable preset, but is never an automatic
  fallback.
- **Cloudflare Dev** and **Cloudflare Prod** appear only when their respective
  URL variables are valid configured URLs.
- **Custom** remains available at all times, so users can select any backend
  endpoint without changing a file.
- Cancelling the initial selector leaves the app unconfigured rather than
  applying localhost. Opening the selector later still allows a choice.

## Configuration contract

Developers who want named Dev and Prod presets will create the ignored desktop
configuration file and load it before launching the app:

```bash
cp .desktop.env.example .desktop.env.local
# Set SPOTIBYE_DEV_BACKEND_URL and/or SPOTIBYE_PRODUCTION_BACKEND_URL.
set -a && source .desktop.env.local && set +a
```

The app does not auto-load `.desktop.env.local`; an IDE launch configuration is
an equivalent source. See
[`dev-docs/guides/environment-setup.md`](../../guides/environment-setup.md).

## Implementation steps

- [x] Confirm the selector's persisted-selection fallback behavior in
  `src/frontend/ui/backend_selector_popup.py` and the caller that restores the
  saved backend URL.
- [x] Change `BACKEND_URL`, `DEV_BACKEND_URL`, and `PRODUCTION_BACKEND_URL` in
  `src/frontend/config/backend_config.py` to represent absent configuration
  without embedding a real endpoint or placeholder as a usable selection.
- [x] Build named presets conditionally: always include **Localhost**, keep
  **Custom** available in the selector, and include named Cloudflare presets
  only for valid explicitly configured URLs.
- [x] Update selector initialization, cancellation, and matching logic so an
  unconfigured launch remains unconfigured; never initialize a localhost client
  merely because the selector was dismissed.
- [x] Preserve saved custom and configured-preset URLs, while handling an old
  saved Cloudflare Dev URL that is no longer configured as an explicit custom
  choice rather than silently substituting another endpoint.
- [x] Update frontend configuration and selector tests for unconfigured,
  localhost-preset, configured Dev/Prod, custom, saved, and cancelled flows.
- [x] Update desktop configuration documentation and
  `.desktop.env.example` with the opt-in behavior.
- [x] Add a concise user-visible entry to `CHANGELOG.md` because the available
  selector presets change.
- [x] Run frontend verification:
  `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
  and `.venv/bin/basedpyright src/frontend src/shared --level error`.
- [x] Verify the no-selection, Localhost, configured Dev/Prod, Custom, saved,
  cancellation, and disabled-selector paths with headless selector/app tests.
  An interactive GUI smoke test remains appropriate on a developer desktop;
  this automated environment has no display.

## Completion notes

- `git diff --check` passed, and the frontend type checker reported 0 errors.
- Focused configuration, selector, app-startup, and cache-explorer coverage:
  50 passed, 6 display-dependent tests skipped.
- The full frontend suite ran with 228 passed and 7 display-dependent skips.
  Its 21 failures are existing integration-style tests that issue live requests
  to a localhost Worker; no Worker can run in this sandbox. The changed paths'
  unit coverage passes independently of those requests.

## Completion criteria

No source or shipped configuration defaults to the account-specific development
Worker URL or automatically connects to localhost. Named Cloudflare presets are
present only through explicit configuration, Localhost and Custom remain
selectable, all selector paths are covered by tests, documentation explains the
opt-in flow, and the active plan is moved to `dev-docs/exec-plans/completed/`.
