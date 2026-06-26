# Design: Cloudflare Workers + Hono Backend Choice

**Status:** Decided
**Date:** Early 2025 (during cloud migration)
**Relevant code:** `src/backend/`

---

## Decision

The SpotiBye backend is implemented as a **Cloudflare Worker** using the **Hono** HTTP framework.

---

## Context

SpotiBye originally had a local Python backend. As the app matured, a decision was made to migrate to a cloud-hosted backend to:
- Remove the requirement for users to run a local server
- Allow the frontend to be distributed as a standalone executable
- Keep Spotify API credentials server-side (out of the distributed binary)

---

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Cloudflare Workers + Hono | Zero cold start, global edge, generous free tier, TypeScript native, no infra to manage | CPU time limits, eventual-consistency KV, no filesystem |
| AWS Lambda | Mature ecosystem, flexible runtimes | Cold starts, more infra complexity, cost at scale |
| Fly.io / Railway (always-on container) | Full Node.js environment, no CPU limits | Cost, more moving parts |
| Local Python server (status quo) | Simple | Users must run it; breaks packaging goal |

---

## Why Cloudflare Workers + Hono

1. **Zero infrastructure overhead.** No servers to manage, patch, or monitor. Deployments are `wrangler deploy`.
2. **Hono is purpose-built for Workers.** Lightweight, TypeScript-first, well-documented, and widely used enough that agent training data covers it well.
3. **Edge latency.** Requests are handled close to the user.
4. **Free tier is sufficient** for SpotiBye's usage patterns (per-user, low sustained throughput).
5. **TypeScript alignment.** The entire backend is in one language with strong types — easier for agents to reason about than a mixed-language stack.

---

## Known Tradeoffs

- **CPU time limit:** 30 ms on free tier. Addressed by the resumable export cursor design.
- **No filesystem:** All state lives in KV. Acceptable for the current feature set.
- **KV eventual consistency:** Not suitable for counters or strict ordering. Acceptable for caching and export job state (both are idempotent).

---

## Agent Notes

- Do not add a Node.js-specific library that requires filesystem access or native modules — they will not work in Workers.
- When in doubt about what Workers supports, check [`../../references/cloudflare-workers-constraints.md`](../../references/cloudflare-workers-constraints.md).
- The `nodejs_compat` flag is enabled in `wrangler.toml` — a limited subset of Node.js APIs is available.
