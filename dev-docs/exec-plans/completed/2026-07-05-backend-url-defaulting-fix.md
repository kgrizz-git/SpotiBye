# Fix Backend URL Defaulting & Selector UI Bug

> **Source assessment:** [dev-docs/assessments/2026-07-05-backend-url-defaulting-bug.md](../../assessments/2026-07-05-backend-url-defaulting-bug.md)
> **Peer review:** [dev-docs/assessments/2026-07-05-backend-url-defaulting-bug-peer-review.md](../../assessments/2026-07-05-backend-url-defaulting-bug-peer-review.md) — both agreed the diagnosis is correct and Option 1 (new `DEV_BACKEND_URL` constant) is the right fix.
> **Root cause:** Commit `c88b3433` (FT-2) repointed `BACKEND_URL`'s default from the Cloudflare dev Worker URL to `http://localhost:8787` for shipped-binary safety, but `BACKEND_PRESETS["Cloudflare Dev"]` still aliases `BACKEND_URL`. This collapses "Localhost" and "Cloudflare Dev" to the same string, breaking the preset spinner, the startup default, and preset restore-on-relaunch.
> **Verification:** `./scripts/verify-all.sh`, plus the targeted commands under each section below.

---

## 1. Config fix — `src/frontend/config/backend_config.py`

- [x] Add a dedicated dev-Worker constant, decoupled from the shipped-binary default. Include a comment explaining the distinction — the two constants being conflated is exactly what caused this bug:
  ```python
  # Cloudflare development worker, used only by the "Cloudflare Dev" preset in
  # the selector UI. Deliberately decoupled from BACKEND_URL: BACKEND_URL is
  # the shipped-binary startup default (kept as localhost per FT-2's security
  # intent) and must not be aliased to this preset's URL again.
  DEV_BACKEND_URL: Final[str] = os.environ.get(
      "SPOTIBYE_DEV_BACKEND_URL",
      "https://spotibye-backend-development.kevin-grizzard.workers.dev",
  )
  ```
  Place it directly below `LOCALHOST_BACKEND_URL` (~line 24).
- [x] Update `BACKEND_PRESETS` (~line 57-61) to reference the new constant instead of `BACKEND_URL`:
  ```python
  BACKEND_PRESETS: Final[dict[str, str]] = {
      "Localhost": LOCALHOST_BACKEND_URL,
      "Cloudflare Dev": DEV_BACKEND_URL,
      "Cloudflare Prod": PRODUCTION_BACKEND_URL,
  }
  ```
- [x] Leave `BACKEND_URL` (~line 15-18) and `CURRENT_BACKEND_URL` untouched — the shipped-binary safety default from FT-2 must be preserved.
- [x] Add `DEV_BACKEND_URL` to `__all__` (~line 288-315).

## 2. Re-export — `src/frontend/config/__init__.py`

- [x] Add `DEV_BACKEND_URL` to both the `from .backend_config import (...)` block and `__all__` list, matching the existing `LOCALHOST_BACKEND_URL` / `PRODUCTION_BACKEND_URL` pattern.

## 3. Regression tests — `src/frontend/tests/test_configuration.py`

- [x] Add `"SPOTIBYE_DEV_BACKEND_URL"` **and** `"SPOTIBYE_LOCALHOST_BACKEND_URL"` to the `_ENV_KEYS` list (~line 20-28) so `TestConfiguration.restore_env` cleans up both — `SPOTIBYE_LOCALHOST_BACKEND_URL` is a pre-existing env var that was already missing from this list; add it now for consistency since we're touching the list anyway. Note this fixture is scoped to `TestConfiguration` only — it does not apply to the new `TestBackendPresetsDistinct` class below, which must handle its own env cleanup via `monkeypatch`.
- [x] Add a new test class covering the aliasing bug directly. **Use `monkeypatch.setenv`, not raw `os.environ[...] =`, for the override test** — this class does not inherit `TestConfiguration`'s `restore_env` fixture (that fixture is scoped to `TestConfiguration` only), so a raw env mutation would leak into later tests/files. `monkeypatch` self-cleans regardless of class:
  ```python
  class TestBackendPresetsDistinct:
      """Regression test: BACKEND_PRESETS entries must not alias each other,
      or the selector spinner and preset-restore-on-relaunch silently break.

      Assumes SPOTIBYE_LOCALHOST_BACKEND_URL is unset for the duration of
      this class (nothing in TestConfiguration currently sets it, but if a
      future test does, test_presets_are_pairwise_distinct_by_default could
      spuriously fail if the localhost override happens to collide with the
      dev URL)."""

      def test_presets_are_pairwise_distinct_by_default(self):
          import importlib
          from ..config import backend_config

          importlib.reload(backend_config)
          urls = list(backend_config.BACKEND_PRESETS.values())
          assert len(urls) == len(set(urls)), (
              f"BACKEND_PRESETS has duplicate URLs: {backend_config.BACKEND_PRESETS}"
          )

      def test_cloudflare_dev_preset_uses_dev_backend_url(self):
          import importlib
          from ..config import backend_config

          importlib.reload(backend_config)
          assert (
              backend_config.BACKEND_PRESETS["Cloudflare Dev"]
              == backend_config.DEV_BACKEND_URL
          )

      def test_dev_backend_url_reexported_from_config_package(self):
          # Regression check for the Section 2 re-export in config/__init__.py.
          # config/__init__.py does `from .backend_config import DEV_BACKEND_URL`,
          # a name binding captured at *its own* import time — reloading
          # backend_config alone does not update it. Reload both, in
          # dependency order, so this actually exercises the re-export wiring
          # rather than comparing two values from the same stale snapshot.
          import importlib
          from ..config import backend_config
          from .. import config as config_pkg

          importlib.reload(backend_config)
          importlib.reload(config_pkg)
          assert config_pkg.DEV_BACKEND_URL == backend_config.DEV_BACKEND_URL

      def test_dev_backend_url_env_override(self, monkeypatch):
          monkeypatch.setenv("SPOTIBYE_DEV_BACKEND_URL", "https://custom-dev.example.com")

          import importlib
          from ..config import backend_config

          importlib.reload(backend_config)
          assert (
              backend_config.BACKEND_PRESETS["Cloudflare Dev"]
              == "https://custom-dev.example.com"
          )
  ```
  After this test's `importlib.reload`, `backend_config` module state reflects the monkeypatched env var until the next reload — `monkeypatch` restores the env var itself at teardown, but if a later test in the same file depends on `backend_config` reflecting *unset* `SPOTIBYE_DEV_BACKEND_URL`, it must reload the module itself first (same convention `TestConfiguration` already follows for its own env vars).
- [x] Run: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/test_configuration.py -v` — 12/12 passed.

## 4. New popup test file — `src/frontend/tests/test_backend_selector_popup.py`

No test file currently exists for `BackendSelectorPopup`.

**Correction to an earlier draft of this plan:** that draft claimed `test_backend_cache_explorer.py` "establishes the precedent for instantiating real Kivy popups directly under `KIVY_WINDOW=headless`." This is backwards. `_kivy_display_available()` in that file returns `False` whenever `KIVY_WINDOW` is `headless`/`mock`, and every test that constructs a real widget calls `self.skipTest(...)` in that case. `.github/workflows/ci.yml:58-65` documents why: *"importing kivy.uix widgets calls sys.exit() (code 102) and kills pytest before any tests run [under headless]. Tests that require a real window are skipped via `KIVY_DISPLAY_AVAILABLE` checks."*

This was independently verified on this machine, not just taken from the comment: running `.venv/bin/python` with `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1` and constructing a bare `kivy.uix.label.Label()` — no `Popup` involved — aborts with `[CRITICAL] [Window] Unable to find any valuable Window provider` / `[CRITICAL] [App] Unable to get a Window, abort.`. The same crash was reproduced specifically for `BackendSelectorPopup`: even with the `kivy.uix.*` widget classes stubbed out, `_build_ui()`'s calls to `kivy.metrics.dp(...)` still resolve `Window` and still abort — `dp` must be stubbed too, not just the widget classes.

Since CI (`ci.yml`) and `scripts/verify-frontend.sh` both run headless, a test that skips under headless gives **zero** regression coverage for this bug — not acceptable here. The verified approach: stub every Kivy name `backend_selector_popup.py` touches at construction time (`kivy.metrics.dp`, and the `kivy.uix.popup/spinner/textinput/button/label/boxlayout` classes) via `sys.modules`, force-overriding rather than `sys.modules.setdefault` (confirmed by direct test: if `test_backend_cache_explorer.py` — alphabetically earlier, so collected first in a full `pytest src/frontend/tests/` run — has already imported the real `kivy.uix.popup` etc., `setdefault` is a no-op and the real classes leak through, reproducing the same abort), then restoring the original `sys.modules` entries immediately after the import completes so later test files in the same session are unaffected (also verified: the restored module continues to work normally for whichever test imports it next). Write the file in **pytest style** (bare `assert`), matching `test_configuration.py`.

**`kivy.clock` deliberately not stubbed.** `backend_selector_popup.py:8` does `from kivy.clock import Clock, mainthread`, and `__init__` → `_initialize_from_default_url` → `_schedule_auto_health_check` calls `Clock.schedule_once(...)` for real during construction. This was run end-to-end with the exact stub set above (no `kivy.clock` entry) and it completed cleanly — real `kivy.clock` does not touch `Window`/`kivy.metrics` in a way that aborts headless. Don't add a `kivy.clock` stub speculatively; it isn't needed and adds a module to keep in sync with the real one for no verified benefit.

```python
"""Tests for BackendSelectorPopup: preset switching and default-URL matching.

Constructing real Kivy widgets under KIVY_WINDOW=headless aborts the
process (kivy.metrics.dp() and any real widget's __init__ resolve Window,
which doesn't exist headless — see .github/workflows/ci.yml's comment on
kivy sys.exit(102)), and CI / scripts/verify-frontend.sh always run
headless. Stub every kivy name this module's _build_ui() touches, import
under the stub, then restore sys.modules immediately so later test files
in the same session see the real kivy modules.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock, patch


class _FakeWidget:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def bind(self, **_kwargs):
        pass

    def add_widget(self, *_args, **_kwargs):
        pass


class _FakePopup(_FakeWidget):
    def dismiss(self):
        pass


def _fake_module(name: str, **attrs) -> types.ModuleType:
    # A real ModuleType instance, not MagicMock: accessing any attribute
    # other than the ones set below correctly raises AttributeError instead
    # of silently auto-vivifying a mock, so a typo'd import from one of
    # these stubs fails loudly instead of masking a real bug.
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


_STUB_MODULES = {
    "kivy.metrics": _fake_module("kivy.metrics", dp=lambda value: value),
    "kivy.uix.popup": _fake_module("kivy.uix.popup", Popup=_FakePopup),
    "kivy.uix.spinner": _fake_module("kivy.uix.spinner", Spinner=_FakeWidget),
    "kivy.uix.textinput": _fake_module("kivy.uix.textinput", TextInput=_FakeWidget),
    "kivy.uix.button": _fake_module("kivy.uix.button", Button=_FakeWidget),
    "kivy.uix.label": _fake_module("kivy.uix.label", Label=_FakeWidget),
    "kivy.uix.boxlayout": _fake_module("kivy.uix.boxlayout", BoxLayout=_FakeWidget),
}
_original_modules = {name: sys.modules.get(name) for name in _STUB_MODULES}
sys.modules.update(_STUB_MODULES)
try:
    from ..config.backend_config import BACKEND_PRESETS
    from ..ui.backend_selector_popup import BackendSelectorPopup
finally:
    for _name, _orig in _original_modules.items():
        if _orig is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _orig
```

- [x] Mock `BackendClient` at its **point of use in the popup module**, not its definition module — `backend_selector_popup.py` does `from ..services.backend_client import BackendClient`, which binds the name into `backend_selector_popup`'s own namespace. Patch the **absolute** path, matching the codebase's existing convention (`test_backend_cache_explorer.py` uses `@patch("src.frontend.ui.backend_cache_explorer._backend_client_cls")`, not a relative dotted path): use `@patch("src.frontend.ui.backend_selector_popup.BackendClient")`, and configure `mock_backend_client.return_value.health_check.return_value = {"status": "healthy"}` so `_start_health_check`'s background thread doesn't make real network calls if it happens to run. Applied to every test, e.g.:
  ```python
  @patch("src.frontend.ui.backend_selector_popup.BackendClient")
  def test_preset_switch_updates_url_input(self, mock_backend_client):
      mock_backend_client.return_value.health_check.return_value = {"status": "healthy"}
      popup = BackendSelectorPopup(
          default_url="http://localhost:8787", on_apply=Mock(), on_cancel=Mock()
      )
      popup._on_preset_changed(popup.preset_spinner, "Cloudflare Dev")
      assert popup.url_input.text == BACKEND_PRESETS["Cloudflare Dev"]
      assert popup.url_input.text != BACKEND_PRESETS["Localhost"]
  ```
- [x] `test_preset_switch_updates_url_input` (shown above): call `popup._on_preset_changed(popup.preset_spinner, "Cloudflare Dev")` **directly** — do not assign `popup.preset_spinner.text = ...` and rely on a bound callback firing; the stub widgets' `.bind()` is a no-op, so no dispatch happens, and this also sidesteps any question of whether real Kivy property-observer dispatch is synchronous under headless. Calling the handler directly also matches the codebase's existing pattern in `test_backend_cache_explorer.py::test_backend_toggle_functionality`, which calls `explorer.on_backend_toggle(...)` directly rather than mutating `.active` and waiting for a dispatch. This is the direct regression test for the non-functional preset button.
- [x] `test_initialize_from_default_url_matches_correct_preset`: construct the popup with `default_url=BACKEND_PRESETS["Cloudflare Dev"]` and assert `popup.preset_spinner.text == "Cloudflare Dev"` (not `"Localhost"`) — this runs synchronously inside `__init__` via `_initialize_from_default_url`, no dispatch involved. Regression test for the peer review's third symptom (preset-restore-on-relaunch picking the first dict key on aliasing). Note this assertion depends on `_initialize_from_default_url()` being called after `_build_ui()` inside `__init__` (it mutates `preset_spinner.text` after the initial `self._preset_names[0]` default set during construction) — if a future refactor reorders those two calls, this test's premise changes.
- [x] `test_custom_url_not_misidentified_as_preset`: construct with `default_url="https://example.com/custom"` and assert `popup.preset_spinner.text == "Custom"` and `popup.url_input.readonly is False`.
- [x] Run both in isolation and as part of the full directory (CI runs the latter): `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/test_backend_selector_popup.py -v` and `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v` — both must show these three tests `passed`, not `skipped`, and must not abort the process. Confirmed: all 3 `passed`; full frontend suite is 133 passed, 7 skipped (pre-existing, unrelated).

> **Note:** `_schedule_auto_health_check` goes through `Clock.schedule_once`, which needs the Kivy clock to be pumped (e.g. via `App.run()`) to actually fire — it does not crash headless (verified: `kivy.clock.Clock.schedule_once` works fine without a `Window`), it just won't invoke the callback synchronously in a test. The three tests above don't depend on it firing. Don't extend these tests to assert on `status_label.text` without first pumping `Clock` or calling `_start_health_check` directly.

## 5. Type check

- [x] `.venv/bin/basedpyright src/frontend src/shared --level error` — 0 errors, 0 warnings, 0 notes.
- [x] `./scripts/verify-all.sh` (full backend + frontend verification, confirms this change doesn't regress anything outside the touched files) — passed.

## 6. Manual verification

> Not performed by the implementing agent — requires launching the actual GUI app and a reachable Cloudflare dev Worker. Left for a human to verify before merge.

- [ ] Launch `python3 run_frontend_backend.py` with no `SPOTIBYE_*` env vars and no `~/.spotibye_cache/backend_selection.json`.
- [ ] In the `Choose Backend` popup, switch the spinner between `Localhost`, `Cloudflare Dev`, and `Cloudflare Prod` — confirm the URL field updates to a distinct value each time.
- [ ] Select `Cloudflare Dev`, click **Test Connection**, confirm `Connection successful` (requires the dev Worker to be reachable, or mock/stand up `wrangler dev` locally).
- [ ] Click **Continue** with `Cloudflare Dev` selected, close the app, relaunch — confirm the popup reopens with `Cloudflare Dev` pre-selected (not `Localhost`), validating the preset-restore fix.
- [ ] Relaunch with no saved selection and no env override — confirm it still defaults to `Localhost` / `http://localhost:8787` (FT-2's shipped-binary safety default is unchanged).

## 7. CHANGELOG.md

- [x] Add an entry under `[Unreleased] / Fixed` (per the project's Changelog Rule — any user-visible change needs one in the same PR):
  > Fixed the "Cloudflare Dev" preset in the startup backend selector being a no-op and silently losing the saved preset choice across relaunches — both were caused by `BACKEND_PRESETS["Cloudflare Dev"]` aliasing the same URL as `"Localhost"` after FT-2's shipped-binary safety default change. Added a dedicated `DEV_BACKEND_URL` constant (override via `SPOTIBYE_DEV_BACKEND_URL`) so the two concepts are decoupled.

---

## Out of scope (flagged, not fixed here)

- `PRODUCTION_BACKEND_URL` still defaults to the placeholder `https://spotibye-api.your-domain.com` (pre-existing, flagged as Q-4 in the original FT-2 plan). Not touched by this fix.
