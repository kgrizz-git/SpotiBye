# Security Scanner Sub-Agent

**Purpose:** Scan for security vulnerabilities and policy violations.

**Contract:**
- Input: File path, directory, or "full scan"
- Output: List of security issues with severity and remediation
- Constraint: Maximum 400 tokens in output
- Use codeguard rules and SECURITY.md as reference

**Example output:**
> Found 3 security issues:
> - High: Hardcoded API key in src/backend/config.ts:12
> - Medium: Missing input validation in src/backend/routes/user.ts:45
> - Low: Outdated dependency lodash@4.17.21

**Activation patterns:**
- "security"
- "vulnerability"
- "audit"
- "security scan"
