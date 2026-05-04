# Cloudflare Workers Constraints

> Runtime limits and platform behaviors for the Cloudflare Worker that powers the SpotiBye backend. Agents: consult this before designing features that involve loops, large data, or timing.

---

## Runtime Limits

| Constraint | Limit | Notes |
|-----------|-------|-------|
| CPU time | 30 ms (free), 30 s (paid Bundled) | Clock time is unlimited; only CPU execution time counts |
| Memory | 128 MB | Per request |
| Request body size | 100 MB | Incoming request payload |
| Response body size | Unlimited (streamed) | Stream large responses |
| Subrequests per request | 1000 | `fetch()` calls within a single Worker invocation |
| KV reads per request | Unlimited (but billed) | |
| KV write per key size | 25 MB | Value size limit |
| KV key size | 512 bytes | |
| Script size | 1 MB (compressed) | Total compiled Worker bundle |
| Environment variables | 64 vars, 5 KB each | Secrets via `wrangler secret` |

---

## KV Namespace Bindings (this project)

Defined in `wrangler.toml`:

| Binding | Purpose |
|---------|---------|
| `CACHE_KV` | Response cache; namespaced by `<user_id>:<resource>:<id>` |
| `SESSIONS_KV` | OAuth session state during PKCE flow |

**KV consistency model:** Eventually consistent. Do not use KV for counters or anything requiring strict ordering. For export job state (cursors), KV is appropriate because retries are idempotent.

---

## Execution Model

- Each Worker invocation handles **one HTTP request**. There is no shared in-memory state between requests.
- `waitUntil()` can extend the lifetime of async operations (logging, non-critical writes) after a response is sent.
- Workers do not support long-polling or websockets in the standard runtime (Durable Objects required for that).
- Workers run in the **V8 isolate model** — no Node.js built-ins by default. The `nodejs_compat` compatibility flag (set in `wrangler.toml`) enables a subset of Node.js APIs.

---

## Local Development

```bash
cd src/backend
npm run dev        # Starts wrangler dev on http://localhost:8787
```

- `wrangler dev` uses a local KV simulation — data does not persist between `wrangler dev` restarts.
- To observe logs in production or staging: `wrangler tail --format json`

---

## Deployment Environments

Defined in `package.json` scripts:

| Command | Target |
|---------|--------|
| `npm run deploy` | Default (workers.dev) |
| `npm run deploy:dev` | Development environment |
| `npm run deploy:prod` | Production environment |

---

## Common Pitfalls

1. **CPU time exceeded:** Long synchronous loops over large track lists can hit the 30 ms free-tier CPU limit. Use async operations and yield between pages.
2. **KV write latency:** KV writes are async and eventually consistent. Don't read back a value immediately after writing and expect it to be present.
3. **No filesystem:** Workers have no access to the filesystem. Everything must be in memory, KV, or an R2 bucket.
4. **No `crypto.createHmac` without compat flag:** JWT signing uses `SubtleCrypto` (`crypto.subtle`) — this is the correct Web Crypto API and is always available.
5. **`fetch` to external APIs counts toward subrequest limit.** Batching Spotify API calls (e.g., `/audio-features?ids=...`) is important for large playlists.
