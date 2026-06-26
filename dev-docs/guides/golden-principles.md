# Golden Principles

> Opinionated, mechanical rules that keep SpotiBye legible and consistent for humans and AI agents alike.
> When in doubt about a pattern, check here first. Violations should be caught by linters, structural tests, or a code review.

---

## 1. Parse at the Boundary

**Rule:** Validate and parse external data shapes at the layer boundary where they enter the system. Never pass raw, unvalidated responses inward.

**Backend:** Validate Spotify API responses in `services/spotify.ts` before returning typed objects to routes. Routes must not receive raw `Response` objects from the service layer.

**Frontend:** Validate backend API responses in `services/` before passing data to `screens/`.

**Why:** An unvalidated response that propagates inward silently breaks assumptions. A validation failure at the boundary is always easier to diagnose than a runtime TypeError three layers deep.

---

## 2. One Door to Spotify

**Rule:** All calls to `api.spotify.com` go through `services/spotify.ts`. No other file may `fetch` Spotify endpoints directly.

**Why:** This single-entry-point pattern makes it trivial to add rate limiting, logging, retry logic, or auth refresh in one place. It also makes the code legible: if you want to know how Spotify is called, you read one file.

---

## 3. Cursor Before Destruction

**Rule:** Export cursors (page offsets, job state) are always written to KV *before* any step that modifies or consumes data.

**Why:** Cloudflare Workers can be interrupted. If a cursor is written after the data has been consumed, a retry will skip records. Writing the cursor first means retries are idempotent.

---

## 4. Namespaced Cache Keys

**Rule:** Cache keys always follow the pattern `<user_id>:<resource_type>:<identifier>`.

**Examples:**
- `abc123:playlists:all`
- `abc123:tracks:playlist_456`
- `abc123:analysis:playlist_456`

**Why:** Flat key names collide across users. Namespacing allows safe, targeted invalidation of a single user's data without affecting others.

---

## 5. Structured Logging in the Backend

**Rule:** No `console.log` in non-test TypeScript code. Use structured log calls that emit context-rich JSON.

**Permitted:** `console.error`, `console.warn` in catch blocks where a proper logger is unavailable (e.g., top-level worker bootstrap). These must include a message and the error object.

**Why:** `console.log` produces unstructured noise that is useless for debugging in production. Structured logs can be queried with `wrangler tail --format json` and parsed by agents.

---

## 6. Named Exceptions in Python

**Rule:** Never use a bare `except:` clause. Always name the exception type.

```python
# Wrong
try:
    ...
except:
    pass

# Right
try:
    ...
except requests.HTTPError as e:
    logger.error("HTTP error: %s", e)
```

**Why:** Bare `except` catches `SystemExit`, `KeyboardInterrupt`, and other signals that should propagate. It also makes debugging impossible.

---

## 7. No Hand-Rolled Helpers

**Rule:** Before writing a new utility function, check `utils/` (frontend) and whether a service already provides it. If the same logic appears in two places, extract it.

**Why:** Duplicated helpers diverge. A fix to one copy doesn't fix the other. Centralized utilities are testable once and applied everywhere.

---

## 8. Layer Boundaries Are Not Suggestions

**Rule:** The dependency directions defined in [ARCHITECTURE.md](../ARCHITECTURE.md) are enforced mechanically. A PR that introduces a layer violation must fix the violation before merging, not defer it.

**Why:** At agent throughput, one violation becomes the template for the next ten. Mechanical enforcement stops drift before it compounds.

---

## 9. Types Over Raw Dicts

**Rule:**
- **TypeScript:** Define an `interface` or `type` for every API request/response shape. No `any` in production code (lint warning).
- **Python:** Use `TypedDict` or a dataclass for data that crosses layer boundaries. No bare `dict` returns from services.

**Why:** Typed shapes make the code legible to agents without requiring them to trace call chains to understand what a variable contains.

---

## 10. Docs Live in the Repo

**Rule:** Any architectural decision, API quirk, or engineering convention that is discussed elsewhere (Slack, GitHub comments, external docs) must be captured as a versioned file in this repo. If it isn't in the repo, the agent can't see it and it effectively doesn't exist.

**Where to put things:**
- Non-trivial design decisions → `dev-docs/architecture/design-decisions/`
- Third-party API notes → `dev-docs/references/`
- Active work plans → `dev-docs/exec-plans/active/`
- Developer guides → `dev-docs/guides/`
- User-facing guides → `docs/`
