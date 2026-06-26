# Harness Engineering Assessment & Improvement Plan

**Date:** June 6, 2026
**Based on:** OpenAI harness engineering article (openai.com/index/harness-engineering/) and the gtcode.com framework (gtcode.com/articles/harness-engineering/)

> Previous assessment (dated June 23, 2026) was based on a secondary blog post summary. This version is based on reading the source articles directly.

---

## Maturity Level

The repo sits at **Level 3 (Mechanical)** on the 0–7 harness maturity scale:

| Level | Name | Status |
|-------|------|--------|
| 0 | Chat-assisted | ✅ Past |
| 1 | Instructions | ✅ Done — AGENTS.md, docs/ |
| 2 | Reproducible | ✅ Done — one-command setup, clean tests, sandboxed |
| 3 | Mechanical | ✅ Done — linters, formatters, layer rules, CI gates |
| 4 | Observable | ❌ Missing — runtime legibility, structured logs, browser automation |
| 5 | Graphs | ❌ Missing — ImplementationGraph, topology, API diffs |
| 6 | Normal form | ❌ Not started |
| 7 | Learning | ❌ Not started |

The framework is explicit: move through levels in order. The next gate is Level 4.

---

## Current State

### Implemented ✅

| Component | Notes |
|-----------|-------|
| `AGENTS.md` | 89 lines, navigation map with links — matches OpenAI's ~100-line target |
| `docs/` + `dev-docs/` | Structured, indexed, extensively linked |
| `ARCHITECTURE.md` | Layer contracts, data flow, dependency rules |
| `dev-docs/code-map.md` | Three Mermaid diagrams (module graph, sequence, backend layers) |
| Layered architecture + enforcement | ESLint rules + structural test enforce layer contracts |
| Pre-commit hooks | Formatting, secrets scanning (gitleaks), SAST (semgrep) |
| Verification scripts | `scripts/verify-all.sh` — silent on success, errors only on failure |
| Skills (progressive disclosure) | 6 skills: spotify-api, cloudflare-worker, testing, export-formats, dependency-analysis, security |
| Sub-agents | 4 configured: architecture-analyst, dependency-analyst, test-coverage-analyst, security-scanner |
| Permissions config | `.claude/settings.local.json` |

### Not Implemented ❌

| Gap | Impact | Priority |
|-----|--------|----------|
| Claude Code agent lifecycle hooks | Verify scripts exist but nothing triggers them — easiest win remaining | High |
| Runtime legibility | Agents can't observe the running app (logs, screenshots, browser) | High |
| Context anxiety mitigation | No mechanism to prevent premature task wrap-up as context fills | Medium |
| Planner/Generator/Evaluator structure | Current sub-agents are research analysts, not an adversarial quality loop | Medium |
| Scheduled drift detection | No background agent scanning for principle violations | Low |

---

## Gaps in Detail

### 1. Agent Lifecycle Hooks (Quick Win)

`settings.local.json` has a `permissions` block but no `hooks` block. `./scripts/verify-all.sh` is written and ready — it just needs to be wired.

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/verify-all.sh"
          }
        ]
      }
    ]
  }
}
```

---

### 2. Runtime Legibility (Level 4 Gate)

The OpenAI article calls this the second major problem they solved: agents couldn't verify their own output at runtime. Their fix was Chrome DevTools Protocol — screenshots, runtime events, log/metric queries, concrete thresholds (e.g., service startup under 800ms).

For SpotiBye this means:
- Structured, machine-readable log output (JSON logs queryable by agents)
- A way for agents to launch the frontend and observe UI state — even screenshot-based
- Backend: structured response logging so agents can diff behavior before/after a change

Without this, an agent editing UI or API behavior has no way to verify the result other than reading code.

---

### 3. Context Anxiety Mitigation

The OpenAI article specifically identifies **context anxiety**: agents prematurely wrap up tasks as the context window fills, cutting corners before running out of capacity. The fix is architectural — cap the apparent context budget so the model always believes it has runway.

The prior assessment framed this as "context bloat from test output," which is a symptom. The underlying issue is model behavior under perceived context pressure. Skills and sub-agents help but don't directly address it.

---

### 4. Sub-Agent Structure: Analysts vs. Adversarial Loop

The repo has 4 analyst sub-agents (architecture, dependency, test coverage, security). These isolate context for research tasks — that's valid.

What OpenAI actually validated was a **Planner / Generator / Evaluator** separation:
- **Planner**: expands intent into full specs, leaves implementation details open
- **Generator**: implements in bounded sprints, commits to a "done" contract
- **Evaluator**: tests behavior via browser automation like a real user, not just reads code

The Evaluator is the critical missing piece. It's adversarial by design — structurally separate from the Generator and testing against observable behavior, not code review. For SpotiBye, an Evaluator would: launch the app, attempt a Spotify login flow, trigger an export, verify the file lands on disk.

---

### 5. Scheduled Drift Detection

The OpenAI team ran background agents on a cron schedule to scan for principle violations and auto-submit refactoring PRs. The repo has no equivalent. Tech debt is caught only when a human or agent happens to look. Low priority until Level 4 is stable.

---

## Improvement Plan

### Priority 1: Wire the Hooks (1 hour)

Add the `hooks` block to `.claude/settings.local.json`. The scripts are already written and tested. This is the only true quick win left.

**Done when:** `./scripts/verify-all.sh` runs automatically before agent stops. Silent on clean repo, errors surface on broken repo.

---

### Priority 2: Runtime Legibility (Level 4) (1–2 weeks)

**Backend:**
- Structured JSON logging in the Cloudflare Worker — every request/response logged with enough context for an agent to diff behavior
- Add response shape assertions to existing vitest tests so agents get failing evidence, not just silent success

**Frontend:**
- Add a headless smoke-test mode: launch app, attempt auth flow, verify backend connection — producible by `pytest tests/smoke/`
- Even a screenshot-on-failure mechanism would be meaningful progress

**Done when:** An agent can make a change to the backend or frontend, run a command, and get observable evidence (log diff, test output with response shapes, or screenshot) confirming the change behaved as intended.

---

### Priority 3: Evaluator Sub-Agent (2–3 weeks)

Create `.claude/sub-agents/evaluator.md` defining an adversarial evaluator that:
- Receives a "done" contract from the Generator (which endpoints changed, what behavior is expected)
- Runs the smoke test suite and compares response shapes against the contract
- Returns pass/fail with specific evidence (log lines, response diffs) — not code review

This requires Priority 2 (runtime legibility) to be meaningful.

**Done when:** Generator sub-agent can hand off a contract to Evaluator and receive evidence-backed acceptance or rejection.

---

### Priority 4: Context Anxiety Mitigation (1 week)

Options in order of effort:
1. Add explicit "context budget" reminder to AGENTS.md — tell agents to plan for partial completion and leave clean stopping points
2. Break complex tasks into bounded sprints in sub-agent configs — each sprint has a defined completion artifact
3. Investigate whether Claude Code's context window settings can be capped at a lower limit

**Done when:** Agents on complex tasks leave clean stopping points rather than cutting corners as context fills.

---

### Priority 5: Scheduled Drift Detection (future)

Once Level 4 is stable, configure a scheduled agent (Claude Code cron or equivalent) to:
- Run `./scripts/verify-all.sh` and structural tests
- Scan for principle violations (bare `except:`, `console.log` in non-test code, cross-layer imports)
- Auto-submit a PR for mechanical fixes; escalate for judgment calls

Low priority until the evaluation infrastructure is solid enough for it to be reliable.

---

## What the Previous Assessment Got Wrong

The prior assessment (based on a secondary blog post) identified the right components but misdescribed two things:

1. **Sub-agents as the key gap** — framed as "context isolation for research tasks." The OpenAI article's actual finding was about adversarial evaluation (Planner/Generator/Evaluator), not research isolation. Research analyst sub-agents help but miss the point.

2. **Back-pressure as "test output flooding context"** — the real problem is context anxiety (premature task wrap-up), which is a model behavior issue, not just a tooling issue. Silent verification scripts help with output volume but don't address the underlying behavior.

The prior plan's Phase 1–3 work (skills, verify scripts, sub-agents) was worth doing and has been done. The remaining work is Level 4 (runtime legibility), which the prior plan didn't address.

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Maturity level | 3 (Mechanical) | 4 (Observable) |
| Agent lifecycle hooks | Not wired | `preStop` triggers verify-all.sh |
| Runtime evidence | None | Agents can observe behavior change after edit |
| Evaluator sub-agent | Not present | Evidence-backed accept/reject on behavior contracts |
| Context task completion | Unknown | Agents leave clean stopping points on complex tasks |
