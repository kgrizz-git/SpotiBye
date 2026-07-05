# Assessment: Backend URL Defaulting & Selector UI Bug

**Timestamp:** 2026-07-05T16:27:49-04:00
**Status:** Investigation Completed (No code changes executed yet)
**Related Documents:**
- [dev-docs/exec-plans/completed/2026-06-21-bug-fix-critical-high.md](../exec-plans/completed/2026-06-21-bug-fix-critical-high.md) (item `FT-2`)
- [src/frontend/config/backend_config.py](../../src/frontend/config/backend_config.py)
- [src/frontend/ui/backend_selector_popup.py](../../src/frontend/ui/backend_selector_popup.py)

---

## 1. Executive Summary & Observed Symptoms

When launching `run_frontend_backend.py`, two unintended behaviors were observed:
1. **Defaulted to localhost causing errors:** Instead of defaulting to the deployed Cloudflare development worker (`https://spotibye-backend-development.kevin-grizzard.workers.dev`) as it previously did, the application defaulted to `http://localhost:8787`. Because no local Cloudflare Worker instance was running on port `8787`, repeated health checks failed.
2. **Preset button non-functional:** In the startup popup (`Choose Backend`), selecting the **"Cloudflare Dev"** preset button/spinner did not change the displayed URL; the URL field remained stuck on `http://localhost:8787`.

### Observed Error Log Trace
When running the launcher, the application emitted the following connection retry and initialization errors:
```log
[INFO   ] [Detected screen resolution] 2560x1440, Mobile: False
[INFO   ] [Calculated desktop window size] 1800x1200 (2176x1296 before constraints)
[WARNING] Both Window.minimum_width and Window.minimum_height must be bigger than 0 for the size restriction to take effect.
[INFO   ] [Desktop window configured] 1800x1200
[INFO   ] [GL          ] NPOT texture support is available
[INFO   ] [Base        ] Start application main loop
[INFO   ] [Desktop window positioned at] 380, 120 (centered)
[DEBUG  ] [Making GET request to http]//localhost:8787/health
[WARNING] [Retrying (Retry(total=1, connect=1, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[WARNING] [Retrying (Retry(total=0, connect=0, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[ERROR  ] [Connection error] HTTPConnectionPool(host='localhost', port=8787): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused"))
[DEBUG  ] [Making GET request to http]//localhost:8787/health
[INFO   ] [Backend initialized with URL] http://localhost:8787
[DEBUG  ] No valid cached token found
[WARNING] [Retrying (Retry(total=1, connect=1, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[WARNING] [Retrying (Retry(total=0, connect=0, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[ERROR  ] [Connection error] HTTPConnectionPool(host='localhost', port=8787): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused"))
[DEBUG  ] [Making GET request to http]//localhost:8787/health
[WARNING] [Retrying (Retry(total=1, connect=1, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[WARNING] [Retrying (Retry(total=0, connect=0, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[ERROR  ] [Connection error] HTTPConnectionPool(host='localhost', port=8787): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused"))
[DEBUG  ] [Making GET request to http]//localhost:8787/health
[WARNING] [Retrying (Retry(total=1, connect=1, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[WARNING] [Retrying (Retry(total=0, connect=0, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[ERROR  ] [Connection error] HTTPConnectionPool(host='localhost', port=8787): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused"))
[DEBUG  ] [Making GET request to http]//localhost:8787/health
[INFO   ] [Backend initialized with URL] http://localhost:8787
[DEBUG  ] No valid cached token found
[WARNING] [Retrying (Retry(total=1, connect=1, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[WARNING] [Retrying (Retry(total=0, connect=0, read=2, redirect=None, status=0)) after connection broken by 'NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused")'] /health
[ERROR  ] [Connection error] HTTPConnectionPool(host='localhost', port=8787): Max retries exceeded with url: /health (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8787): Failed to establish a new connection: [Errno 61] Connection refused"))
```

---

## 2. Root Cause Analysis

### A. Why it defaulted to localhost
In commit `c88b3433` (which implemented item **FT-2** of the [Critical & High Bug Fix Plan](../exec-plans/completed/2026-06-21-bug-fix-critical-high.md#L135-L140)), the fallback default for `BACKEND_URL` in `src/frontend/config/backend_config.py` was modified:

```diff
 # Backend API configuration. Default to localhost so the shipped binary does
 # not hardcode the developer's Cloudflare Worker URL. Set
 # `SPOTIBYE_BACKEND_URL` to point at a deployed worker.
 BACKEND_URL: Final[str] = os.environ.get(
     "SPOTIBYE_BACKEND_URL",
-    "https://spotibye-backend-development.kevin-grizzard.workers.dev",
+    "http://localhost:8787",
 )
```

When no environment variable (`SPOTIBYE_BACKEND_URL`) is exported and no saved preference exists in `~/.spotibye_cache/backend_selection.json`, `resolve_startup_backend_url()` evaluates to `BACKEND_URL`, now `"http://localhost:8787"`.

### B. Why the "Cloudflare Dev" button did not update the URL
In `src/frontend/config/backend_config.py`, the preset options dictionary for the UI selector is defined as:

```python
BACKEND_PRESETS: Final[dict[str, str]] = {
    "Localhost": LOCALHOST_BACKEND_URL,      # "http://localhost:8787"
    "Cloudflare Dev": BACKEND_URL,           # Evaluates to "http://localhost:8787"
    "Cloudflare Prod": PRODUCTION_BACKEND_URL,
}
```

When the user selects `"Cloudflare Dev"` in the UI dropdown, `BackendSelectorPopup._on_preset_changed` (`src/frontend/ui/backend_selector_popup.py:129`) sets:
```python
self.url_input.text = BACKEND_PRESETS[selected]
```
Because `BACKEND_URL` was changed to `http://localhost:8787`, both `"Localhost"` and `"Cloudflare Dev"` in `BACKEND_PRESETS` point to the identical localhost URL. Selecting **"Cloudflare Dev"** re-assigns `http://localhost:8787` to the input field, resulting in no visual change or URL switch.

---

## 3. Recommended Fixes

To resolve the UI selector bug while respecting the architectural intention of FT-2 (preventing shipped binaries from hardcoding a developer's private worker URL as the primary default), we should separate the concept of **"default startup fallback"** from **"Cloudflare Dev preset URL"**.

### Recommended Implementation (Option 1)

1. **Define a dedicated development URL constant in `src/frontend/config/backend_config.py`:**
   ```python
   DEV_BACKEND_URL: Final[str] = os.environ.get(
       "SPOTIBYE_DEV_BACKEND_URL",
       "https://spotibye-backend-development.kevin-grizzard.workers.dev",
   )
   ```

2. **Update `BACKEND_PRESETS` to reference `DEV_BACKEND_URL`:**
   ```python
   BACKEND_PRESETS: Final[dict[str, str]] = {
       "Localhost": LOCALHOST_BACKEND_URL,
       "Cloudflare Dev": DEV_BACKEND_URL,
       "Cloudflare Prod": PRODUCTION_BACKEND_URL,
   }
   ```

3. **Export `DEV_BACKEND_URL` in `__all__`:**
   Ensure `DEV_BACKEND_URL` is included in the module's exported symbols list.

4. **Startup Default Behavior Choice:**
   - **Keep Localhost Default (if shipped binary safety is priority):** Leave `BACKEND_URL` defaulting to `"http://localhost:8787"`. When launching in development without a saved choice, users will see the selector popup and can select **"Cloudflare Dev"**, which will now correctly update the field to `https://spotibye-backend-development.kevin-grizzard.workers.dev`.
   - **Revert to Dev Worker Default (if seamless local dev is priority):** Change `BACKEND_URL` back to defaulting to `DEV_BACKEND_URL`. Shipped binaries would instead rely on an explicit build-time/packaging environment override (`SPOTIBYE_BACKEND_URL`).

---

## 4. Verification Plan (for execution phase)

When these recommendations are approved for execution:
1. **Verify Unit Tests:**
   Run frontend tests to ensure configuration changes and UI popup bindings pass:
   ```bash
   KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v
   ```
2. **Verify Type Safety:**
   Check Pyright across frontend and shared modules:
   ```bash
   .venv/bin/basedpyright src/frontend src/shared --level error
   ```
3. **Manual Verification:**
   - Launch `python3 run_frontend_backend.py`.
   - In the popup selector, toggle between `"Localhost"`, `"Cloudflare Dev"`, and `"Cloudflare Prod"`. Confirm the text box updates to the respective URLs.
   - Click **"Test Connection"** when `"Cloudflare Dev"` is selected and verify `Backend reachable / Connection successful` status.
