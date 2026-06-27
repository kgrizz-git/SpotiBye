# Pyright Assessment — `src/frontend/screens/adapter_mixins/`

**NEEDS REVIEW**

## Verified Findings (2026-06-27)

- **Error count:** 147 ✓ — confirmed matches actual
- **Issues confirmed:** One dominant pattern — `reportAttributeAccessIssue` on mixin `self` attribute access (~147 errors). All attributes listed (`cache_manager`, `reccobeats_service`, `error_callback`, `backend_client`, `progress_callback`, `_emit_progress`, `_run_with_transient_retry`, `_format_backend_api_error`, `_generate_batch_export_resumable`, `clear_active_export_job`, `_persist_active_export_job`, `_load_or_create_resumable_job`, `network_monitor`, `playlists_loaded_callback`) are real cross-mixin dependencies.
- **Additional issue:** `core.py` line 114 — `callable()` used where a class is expected (`TypeIs` issue). Confirmed.
- **All suggestions are appropriate:** Protocol/ABC per mixin would be the most type-safe fix; suppressing `reportAttributeAccessIssue` for this folder is the pragmatic alternative.

**Command:** `basedpyright --level error src/frontend/screens/adapter_mixins/`
**Date:** 2026-06-27
**Errors found:** 147

---

## Overview

Almost all errors in this folder are **one pattern**: accessing attributes on mixin classes via `self.attribute_name`, where pyright doesn't know those attributes exist because they are provided by other mixins or the parent class at composition time.

These are `reportAttributeAccessIssue` errors with the pattern `Cannot access attribute "X" for class "SomeMixin*"`.

---

## `analysis.py` (7 errors)

Attributes accessed on `self` that pyright cannot resolve:
- `cache_manager` (lines 28, 30, 43)
- `reccobeats_service` (line 39)
- `error_callback` (lines 51–52)
- `backend_client` (line 66)

## `core.py` (3 errors)

- `get` on possibly-`None` (lines 94–95)
- `Expected class but received TypeIs[...]` (line 114) — `callable()` used in a context expecting a class.

## `exports.py` (34 errors)

Attributes on `self` not resolved:
- `progress_callback`, `_emit_progress`, `_run_with_transient_retry`, `backend_client`, `cache_manager`, `_format_backend_api_error`, `error_callback`, `_generate_batch_export_resumable`

## `exports_download.py` (19 errors)

Attributes on `self` not resolved:
- `progress_callback`, `_emit_progress`, `backend_client`, `_run_with_transient_retry`, `clear_active_export_job`, `_persist_active_export_job`, `_generate_batch_export_resumable`, `_format_backend_api_error`, `error_callback`

## `exports_resumable.py` (21 errors)

Attributes on `self` not resolved:
- `progress_callback`, `_emit_progress`, `_load_or_create_resumable_job`, `_persist_active_export_job`, `_run_with_transient_retry`, `backend_client`, `_format_backend_api_error`, `error_callback`

## `jobs.py` (10 errors)

Attributes on `self` not resolved:
- `cache_manager`, `_emit_progress`, `backend_client`, `_run_with_transient_retry`

## `playlists.py` (12 errors)

Attributes on `self` not resolved:
- `cache_manager`, `network_monitor`, `progress_callback`, `backend_client`, `_format_backend_api_error`, `playlists_loaded_callback`, `error_callback`

## `tracks.py` (19 errors)

Attributes on `self` not resolved:
- `progress_callback`, `backend_client`, `_format_backend_api_error`, `error_callback`, `cache_manager`

## `utilities.py` (13 errors)

Attributes on `self` not resolved:
- `network_monitor`, `cache_manager`, `backend_client`

---

## Suggested Fix

This entire class of errors stems from **mixin composition** where each mixin assumes certain attributes exist on the final composed class. Approaches:

1. **Protocol/ABC per mixin** — Define an abstract base that declares required attributes, and make the mixin depend on the protocol rather than `self`.
2. **`Self` type with type hints** — Annotate `self` as a Protocol that includes all expected attributes.
3. **Suppress `reportAttributeAccessIssue`** for this folder if mixin composition is the intended pattern.
4. **`# type: ignore`** on each access — tedious but keeps the checker green.
