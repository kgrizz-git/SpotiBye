# Test Coverage Analyst Sub-Agent

**Purpose:** Analyze test coverage and identify gaps.

**Contract:**
- Input: File path, directory, or "overall"
- Output: Coverage percentage and uncovered files/lines
- Constraint: Maximum 300 tokens in output
- Use test coverage reports from pytest/vitest

**Example output:**
> Backend coverage: 78%
> Uncovered files:
> - src/backend/services/new-feature.ts (0%)
> - src/backend/routes/legacy.ts (45%)
>
> Frontend coverage: 82%
> Uncovered files:
> - src/frontend/screens/new-screen.py (0%)

**Activation patterns:**
- "test coverage"
- "untested code"
- "coverage gaps"
- "coverage report"
