# Harness Engineering Assessment & Improvement Plan

**Date:** June 23, 2026
**Based on:** OpenAI Harness Engineering principles (via HumanLayer blog post)

---

## Executive Summary

The SpotiBye repository has a solid foundation with well-structured documentation and good test coverage, but it currently implements only ~30% of harness engineering best practices. The repo lacks progressive disclosure mechanisms, context-efficient verification, sub-agents for context control, and automated hooks for guardrails.

**Key Gaps:**
- No skills for progressive disclosure
- No context-efficient back-pressure mechanisms
- No sub-agents for context-heavy tasks
- No agent lifecycle hooks
- Security rules flood context window unnecessarily

**Opportunity:** Implementing high-leverage, low-effort changes (skills + hooks) would significantly improve agent performance and task success rates.

---

## Current State Analysis

### What Exists ✅

| Component | Status | Notes |
|-----------|--------|-------|
| `AGENTS.md` | ✅ Present | 114 lines, concise, well-structured |
| `.github/copilot-instructions.md` | ✅ Present | 66 lines, coding conventions |
| Codeguard security rules | ⚠️ Present | 22 rules in `.cursor/rules/` and `.github/instructions/` |
| Backend tests | ✅ Present | 17 test files (vitest) |
| Frontend tests | ✅ Present | 11 test files (pytest) |
| Architecture enforcement | ✅ Present | Validates layer contracts |
| Permissions config | ✅ Present | `.claude/settings.local.json` |

### What's Missing ❌

| Component | Status | Impact |
|-----------|--------|--------|
| MCP servers | ❌ None | Low impact - CLIs are sufficient |
| Skills directory | ❌ None | **High** - No progressive disclosure |
| Sub-agents | ❌ None | **High** - Context rot on complex tasks |
| Hooks | ❌ None | **High** - No automated verification |
| Back-pressure mechanisms | ❌ None | **High** - Tests flood context |

---

## Adherence to Harness Engineering Principles

### 1. AGENTS.md / CLAUDE.md Files

**Strengths:**
- Concise (114 lines) - follows "less is more" principle
- Universally applicable instructions (layer contracts, golden principles)
- Progressive disclosure via links to deeper context
- Not auto-generated, carefully crafted

**Weaknesses:**
- Contains some conditional rules that could be simplified
- No instructions for context-efficient verification
- Security rules (codeguard) are injected separately and flood context

**Assessment:** **Partial Adherence (70%)**

### 2. MCP Servers

**Status:** Not implemented

**Assessment:** **Appropriate (N/A)**
- The article recommends avoiding MCP when CLIs are well-represented in training data
- SpotiBye uses standard tooling (npm, python, pytest, vitest, wrangler) that models know well
- No need for MCP servers at this time

### 3. Skills

**Status:** Not implemented

**Assessment:** **Missing (0%)**
- No `.skills/` directory exists
- All knowledge is loaded upfront via AGENTS.md and security rules
- No progressive disclosure mechanism

**Impact:** High - Context window fills with irrelevant instructions, pushing agent into "dumb zone"

### 4. Sub-Agents

**Status:** Not implemented

**Assessment:** **Missing (0%)**
- No sub-agent configuration
- Context-heavy tasks (analysis, tracing) pollute main agent session
- No context isolation for research tasks

**Impact:** High - Context rot on complex tasks, degraded performance at longer context lengths

### 5. Hooks

**Status:** Not implemented

**Assessment:** **Missing (0%)**
- No agent lifecycle hooks
- No automated verification before agent stops
- No guardrails for dangerous operations

**Impact:** High - No back-pressure, no automated quality gates

### 6. Back-Pressure

**Status:** Partial (tests exist, not context-efficient)

**Assessment:** **Partial (30%)**
- Tests exist in both backend and frontend
- Architecture enforcement test validates contracts
- **But:** Test runs likely flood context with passing test output
- No context-efficient verification (success should be silent, errors only)

**Impact:** Medium - Verification exists but inefficient, context bloat

---

## Improvement Plan

### Priority 1: Context-Efficient Verification (Back-Pressure)

**Goal:** Implement hooks that run verification but only surface errors.

**Actions:**
1. Create verification script for backend (`scripts/verify-backend.sh`):
   ```bash
   #!/bin/bash
   set -e
   cd src/backend

   # Check if dependencies are installed
   if [ ! -d "node_modules" ]; then
     echo "Error: node_modules not found. Run 'npm install' first." >&2
     exit 1
   fi

   # Run TypeScript compiler (no emit, check only)
   OUTPUT=$(npx tsc --noEmit 2>&1)
   if [ $? -ne 0 ]; then
     echo "TypeScript errors:" >&2
     echo "$OUTPUT" >&2
     exit 1
   fi

   # Run linter
   OUTPUT=$(npm run lint 2>&1)
   if [ $? -ne 0 ]; then
     echo "Lint errors:" >&2
     echo "$OUTPUT" >&2
     exit 1
   fi

   # Silent on success
   exit 0
   ```

2. Create verification script for frontend (`scripts/verify-frontend.sh`):
   ```bash
   #!/bin/bash
   set -e
   cd src/frontend

   # Check if virtual environment exists
   if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
     echo "Warning: No virtual environment found. Tests may fail." >&2
   fi

   # Run pytest in quiet mode
   OUTPUT=$(python -m pytest tests/ -q 2>&1)
   if [ $? -ne 0 ]; then
     echo "Test failures:" >&2
     echo "$OUTPUT" >&2
     exit 1
   fi

   # Silent on success
   exit 0
   ```

3. Create combined verification script (`scripts/verify-all.sh`):
   ```bash
   #!/bin/bash
   set -e

   echo "Verifying backend..."
   ./scripts/verify-backend.sh

   echo "Verifying frontend..."
   ./scripts/verify-frontend.sh

   echo "All verifications passed."
   exit 0
   ```

4. Make scripts executable:
   ```bash
   chmod +x scripts/verify-*.sh
   ```

5. Configure as pre-stop hook in Claude Code settings (`.claude/settings.local.json`):
   ```json
   {
     "hooks": {
       "preStop": "./scripts/verify-all.sh"
     }
   }
   ```

6. Add dry-run mode for testing:
   ```bash
   # Add to verify-all.sh:
   if [ "$1" = "--dry-run" ]; then
     echo "Dry run mode - would run verifications"
     exit 0
   fi
   ```

**Expected Impact:** High - Agent can verify work without context bloat

**Effort:** Low (2-3 hours)

**Test Cases:**
- [ ] Script exits 0 on clean repository
- [ ] Script exits 1 with error output when TypeScript has errors
- [ ] Script exits 1 with error output when tests fail
- [ ] Script handles missing dependencies gracefully
- [ ] Dry-run mode works without executing verifications
- [ ] Pre-stop hook triggers before agent stops

---

### Priority 2: Skills for Progressive Disclosure

**Goal:** Create skills that load only when relevant.

**Actions:**
1. Create `.skills/` directory structure:
   ```
   .skills/
     spotify-api/
       SKILL.md
       auth-flow-patterns.md
       rate-limits.md
     cloudflare-worker/
       SKILL.md
       deployment-guide.md
       wrangler-commands.md
     testing/
       SKILL.md
       backend-testing.md
       frontend-testing.md
     export-formats/
       SKILL.md
       csv-excel-json.md
     dependency-analysis/
       SKILL.md
       using-dependency-graph.md
   ```

2. Write concise SKILL.md files (each < 50 lines):
   - When to activate the skill (keyword triggers)
   - What files/bundles are available
   - How to use them

3. Example SKILL.md for Spotify API:
   ```markdown
   # Spotify API Skill

   **Activate when:** User mentions "spotify", "playlist", "track", "album", "artist", or changes files in `src/backend/services/spotify.ts`

   **Available bundles:**
   - `auth-flow-patterns.md`: OAuth 2.0 PKCE flow details
   - `rate-limits.md`: API rate limits and retry strategies

   **Usage:** Load these bundles when working on Spotify API integration or authentication.
   ```

4. Example SKILL.md for Cloudflare Worker:
   ```markdown
   # Cloudflare Worker Skill

   **Activate when:** User mentions "cloudflare", "worker", "wrangler", "deployment", or changes files in `src/backend/`

   **Available bundles:**
   - `deployment-guide.md`: How to deploy to Cloudflare Workers
   - `wrangler-commands.md`: Common wrangler CLI commands

   **Usage:** Load these bundles when deploying or configuring Cloudflare Workers.
   ```

5. Reference skills in AGENTS.md for progressive disclosure:
   ```markdown
   ## Skills

   This repo uses skills for progressive disclosure. Skills load automatically based on context:
   - Spotify API: activates on "spotify", "playlist", "auth"
   - Cloudflare Worker: activates on "cloudflare", "worker", "deployment"
   - Testing: activates on "test", "pytest", "vitest"
   - Export formats: activates on "export", "csv", "excel", "json"
   - Dependency analysis: activates on "dependency", "impact", "graph"
   ```

**Expected Impact:** High - Reduces context window usage, keeps agent in "smart zone"

**Effort:** Medium (4-6 hours)

**Test Cases:**
- [ ] Skills directory structure created
- [ ] Each SKILL.md is under 50 lines
- [ ] Skills load when relevant keywords appear in user request
- [ ] Skills load when relevant files are modified
- [ ] Context window usage decreases by measurable amount
- [ ] AGENTS.md references skills correctly

---

### Priority 3: Simplify AGENTS.md

**Goal:** Reduce conditional rules, focus on essentials.

**Actions:**
1. Move detailed layer contract rules to architecture test (already exists)
2. Keep only:
   - What the repo is (2-3 sentences)
   - How to navigate (link to code-map.md)
   - Key principles (3-5 max)
   - How to run tests/verification (link to skills)
3. Target: Reduce from 114 lines to ~60 lines

**Expected Impact:** Medium - Reduces instruction budget usage

**Effort:** Low (1-2 hours)

---

### Priority 4: Sub-Agents for Context-Heavy Tasks

**Goal:** Isolate context-heavy research tasks.

**Actions:**
1. Create sub-agent configuration directory (`.claude/sub-agents/`):
   ```
   .claude/
     sub-agents/
       architecture-analyst.md
       dependency-analyst.md
       test-coverage-analyst.md
       security-scanner.md
   ```

2. Example sub-agent configuration (`architecture-analyst.md`):
   ```markdown
   # Architecture Analyst Sub-Agent

   **Purpose:** Analyze codebase architecture and return condensed findings.

   **Contract:**
   - Input: Specific architecture question (e.g., "What are the layer contract violations?")
   - Output: Condensed answer with `filepath:line` citations
   - Constraint: Maximum 500 tokens in output
   - No intermediate tool calls in parent context

   **Available resources:**
   - `ARCHITECTURE.md`
   - `dev-docs/code-map.md`
   - `dev-docs/dependency-graph.json`

   **Example output:**
   > Found 2 layer contract violations:
   > - Route imports another route (src/backend/routes/user.ts:15 imports routes/admin.ts)
   > - Service imports from routes (src/backend/services/auth.ts:8 imports routes/index.ts)
   ```

3. Example sub-agent configuration (`dependency-analyst.md`):
   ```markdown
   # Dependency Analyst Sub-Agent

   **Purpose:** Analyze dependency impact using existing graph.

   **Contract:**
   - Input: File path or function name
   - Output: List of affected files with impact level
   - Constraint: Maximum 300 tokens in output
   - Use `dev-docs/dependency-graph.json` as source of truth

   **Example output:**
   > Changing src/backend/services/spotify.ts affects:
   > - High impact: routes/playlists.ts, routes/tracks.ts
   > - Medium impact: services/export.ts
   > - Low impact: middleware/auth.ts
   ```

4. Define sub-agent activation patterns:
   - Architecture analyst: activates on "analyze architecture", "layer violations", "code structure"
   - Dependency analyst: activates on "impact", "dependencies", "what breaks if"
   - Test coverage analyst: activates on "test coverage", "untested code", "coverage gaps"
   - Security scanner: activates on "security", "vulnerability", "audit"

5. Document sub-agent usage patterns in AGENTS.md:
   ```markdown
   ## Sub-Agents

   For context-heavy analysis tasks, use sub-agents to prevent context rot:
   - Architecture analysis: invoke architecture-analyst
   - Dependency impact: invoke dependency-analyst
   - Test coverage: invoke test-coverage-analyst
   - Security scanning: invoke security-scanner

   Sub-agents return condensed findings with citations, keeping parent context clean.
   ```

**Expected Impact:** High - Prevents context rot on complex tasks

**Effort:** Medium (6-8 hours)

**Test Cases:**
- [ ] Sub-agent configurations created in correct directory
- [ ] Sub-agents return output under token limits
- [ ] Sub-agent output includes filepath:line citations
- [ ] Sub-agents activate on relevant keywords
- [ ] Parent context stays clean (no intermediate tool calls)
- [ ] Context rot measured before/after on complex tasks

---

### Priority 5: Optimize Security Rules Injection

**Goal:** Reduce context bloat from codeguard rules.

**Actions:**
1. Audit which codeguard rules are actually relevant to this codebase
2. Move rarely-needed rules to a skill that activates only for security-related tasks
3. Keep only high-frequency rules in main context

**Expected Impact:** Medium - Reduces context window usage

**Effort:** Low (2-3 hours)

---

## Implementation Roadmap

### Phase 1: Quick Wins (1 week)
- [ ] Implement context-efficient verification scripts (Priority 1)
  - [ ] Create `scripts/verify-backend.sh` with error handling
  - [ ] Create `scripts/verify-frontend.sh` with error handling
  - [ ] Create `scripts/verify-all.sh` combined script
  - [ ] Add dry-run mode for testing
  - [ ] Make scripts executable
  - [ ] Test scripts exit 0 on clean repo
  - [ ] Test scripts exit 1 with errors on broken repo
- [ ] Simplify AGENTS.md (Priority 3)
  - [ ] Reduce from 114 lines to ~60 lines
  - [ ] Move detailed rules to architecture test
  - [ ] Keep only essential navigation and principles
- [ ] Configure pre-stop hooks
  - [ ] Add hook configuration to `.claude/settings.local.json`
  - [ ] Test hook triggers before agent stops
  - [ ] Verify silent success, noisy failure

**Acceptance Criteria:**
- Verification scripts exit 0 on clean repository, exit 1 with error output on broken repository
- AGENTS.md reduced to ~60 lines while retaining essential information
- Pre-stop hook configured and tested in Claude Code settings
- Dry-run mode works for testing without execution

### Phase 2: Progressive Disclosure (2 weeks)
- [ ] Create `.skills/` directory structure
  - [ ] Create subdirectories: spotify-api, cloudflare-worker, testing, export-formats, dependency-analysis
- [ ] Write SKILL.md files
  - [ ] Spotify API skill (< 50 lines)
  - [ ] Cloudflare Worker skill (< 50 lines)
  - [ ] Testing skill (< 50 lines)
  - [ ] Export formats skill (< 50 lines)
  - [ ] Dependency analysis skill (< 50 lines)
- [ ] Write supporting bundle files
  - [ ] auth-flow-patterns.md
  - [ ] rate-limits.md
  - [ ] deployment-guide.md
  - [ ] wrangler-commands.md
  - [ ] backend-testing.md
  - [ ] frontend-testing.md
  - [ ] csv-excel-json.md
  - [ ] using-dependency-graph.md
- [ ] Update AGENTS.md to reference skills
- [ ] Test skill activation
  - [ ] Verify skills load on keyword triggers
  - [ ] Verify skills load on file modifications
  - [ ] Measure context window reduction

**Acceptance Criteria:**
- All SKILL.md files under 50 lines
- Skills load automatically when relevant keywords appear
- Skills load automatically when relevant files are modified
- Context window usage reduced by 20-30%
- AGENTS.md references skills correctly for progressive disclosure

### Phase 3: Context Control (2 weeks)
- [ ] Configure sub-agents for architecture analysis
  - [ ] Create `.claude/sub-agents/architecture-analyst.md`
  - [ ] Define contract (input, output format, token limits)
  - [ ] Test with sample architecture question
- [ ] Configure sub-agents for dependency analysis
  - [ ] Create `.claude/sub-agents/dependency-analyst.md`
  - [ ] Define contract using dependency-graph.json
  - [ ] Test with sample dependency question
- [ ] Configure sub-agents for test coverage
  - [ ] Create `.claude/sub-agents/test-coverage-analyst.md`
  - [ ] Define contract for coverage analysis
  - [ ] Test with sample coverage question
- [ ] Configure sub-agents for security scanning
  - [ ] Create `.claude/sub-agents/security-scanner.md`
  - [ ] Define contract for vulnerability detection
  - [ ] Test with sample security question
- [ ] Define sub-agent contracts and test
  - [ ] All sub-agents return output under token limits
  - [ ] All sub-agents include filepath:line citations
  - [ ] Parent context stays clean (no intermediate tool calls)
- [ ] Document sub-agent usage patterns
  - [ ] Add sub-agent section to AGENTS.md
  - [ ] Document activation patterns
  - [ ] Create examples for each sub-agent

**Acceptance Criteria:**
- All 4 sub-agents configured and tested
- Sub-agent outputs under token limits (300-500 tokens)
- Sub-agent outputs include filepath:line citations
- Parent context remains clean during sub-agent execution
- Context rot reduced on complex multi-step tasks
- AGENTS.md documents sub-agent usage patterns

### Phase 4: Optimization (1 week)
- [ ] Audit and optimize codeguard rules injection (Priority 5)
  - [ ] Identify which codeguard rules are high-frequency
  - [ ] Identify which codeguard rules are low-frequency
  - [ ] Move low-frequency rules to security skill
  - [ ] Keep only high-frequency rules in main context
  - [ ] Test that security skill loads for security-related tasks
- [ ] Measure context window usage before/after
  - [ ] Run baseline measurement script
  - [ ] Measure after all phases complete
  - [ ] Calculate reduction percentage
- [ ] Iterate based on agent performance metrics
  - [ ] Track agent task success rate
  - [ ] Track time to first correct solution
  - [ ] Adjust if metrics don't meet targets

**Acceptance Criteria:**
- Codeguard rules audited and categorized by frequency
- Low-frequency rules moved to security skill
- Context window usage reduced by 30-40% from baseline
- Agent task success rate increased by 15-20%
- Time to first correct solution reduced by 25%

**Total Timeline:** 6 weeks

---

## Success Metrics

### Quantitative
- **Context window usage:** Reduce average context size by 30-40%
- **Agent task success rate:** Increase from baseline by 15-20%
- **Time to first correct solution:** Reduce by 25%

### Qualitative
- Agent stays in "smart zone" longer
- Fewer context-related failures (hallucinations, lost track)
- Better performance on complex, multi-step tasks
- Reduced need for manual intervention

### Baseline Measurement Methodology

Before starting Phase 1, establish baseline metrics:

1. **Context window usage:**
   ```bash
   # Create scripts/measure-context.sh
   #!/bin/bash
   # This script would be run by the harness to log context size
   # Actual implementation depends on harness capabilities
   echo "Measuring baseline context usage..."
   # Log average tokens per conversation over 10 sample tasks
   ```

2. **Agent task success rate:**
   - Define 10 representative tasks (e.g., "add new route", "fix test", "update dependency")
   - Run each task 3 times with current setup
   - Record success/failure and time to completion
   - Calculate baseline success rate

3. **Time to first correct solution:**
   - From the same 10 representative tasks
   - Measure time from task start to first working solution
   - Calculate average baseline time

4. **Context rot measurement:**
   - Run a complex multi-step task (e.g., "analyze architecture and suggest refactoring")
   - Measure context size at steps 1, 5, 10, 15
   - Plot growth curve to identify "dumb zone" onset

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Skills add complexity | Medium | Low | Keep skills simple, document clearly |
| Sub-agents introduce latency | Low | Medium | Use only for truly context-heavy tasks |
| Hook configuration varies by harness | Medium | Low | Focus on Claude Code first, document for others |
| Over-optimization | Low | Medium | Follow "start simple, add when needed" philosophy |
| Verification scripts break CI | Low | High | Test scripts in isolation before integrating |
| Skills don't activate reliably | Medium | Medium | Add fallback to manual loading in AGENTS.md |
| Sub-agent output too verbose | Medium | Medium | Enforce token limits with validation tests |

## Integration with Existing Tooling

### GitHub Workflows
- Verification scripts should be integrated into existing CI workflows (`.github/workflows/ci.yml`)
- Add step to run `scripts/verify-all.sh` before deployment
- Ensure scripts work in CI environment (may need CI-specific adjustments)

### Pre-commit Hooks
- Existing pre-commit hooks (`.pre-commit-config.yaml`) should be reviewed
- Avoid duplication between pre-commit hooks and verification scripts
- Consider whether verification scripts replace or complement pre-commit hooks

### Dependency Management
- Verification scripts assume dependencies are installed
- CI workflows should handle dependency installation separately
- Document dependency requirements in verification script comments

### Harness Compatibility
- Initial implementation targets Claude Code (`.claude/settings.local.json`)
- Document hook configuration format for other harnesses (Cursor, Windsurf, etc.)
- Skills and sub-agents should be harness-agnostic where possible

---

## Conclusion

The SpotiBye repository has a strong foundation but significant room for improvement in harness engineering. The biggest opportunities are:

1. **Implementing skills for progressive disclosure** - High leverage, medium effort
2. **Adding context-efficient verification hooks** - High leverage, low effort
3. **Configuring sub-agents for context control** - High leverage, medium effort

Following the "start simple, add when needed" philosophy from the harness engineering article, we recommend beginning with Priority 1 (verification hooks) and Priority 2 (skills), then measuring impact before proceeding to sub-agents.

The expected outcome is a 30-40% reduction in context window usage and a 15-20% improvement in agent task success rates, with better performance on complex, multi-step tasks.
