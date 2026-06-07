# Low-Frequency Security Rules

These security rules are rarely needed for the SpotiBye codebase and are moved here to reduce context bloat.

## Rules Moved to This Skill

The following codeguard rules are low-frequency for this codebase:

**Infrastructure/DevOps (not applicable):**
- codeguard-0-cloud-orchestration-kubernetes - Not using Kubernetes
- codeguard-0-devops-ci-cd-containers - CI/CD level, not code-level
- codeguard-0-iac-security - Not using Terraform/CloudFormation
- codeguard-0-supply-chain-security - Infrastructure level

**Platform-specific (not applicable):**
- codeguard-0-mobile-apps - Desktop app, not mobile
- codeguard-0-safe-c-functions - Not using C
- codeguard-0-client-side-web-security - Desktop app, not web

**Technologies not used:**
- codeguard-0-xml-and-serialization - Not using XML
- codeguard-1-digital-certificates - Not using certificates

**Rarely relevant:**
- codeguard-0-file-handling-and-uploads - Minimal file handling
- codeguard-0-session-management-and-cookies - Backend handles auth, not cookies directly
- codeguard-0-authorization-access-control - Backend handles this, rarely changed
- codeguard-0-data-storage - Simple KV storage, minimal complexity
- codeguard-0-privacy-data-protection - General, rarely specific changes
- codeguard-0-additional-cryptography - Limited crypto usage
- codeguard-0-authentication-mfa - No MFA implementation
- codeguard-1-crypto-algorithms - Limited crypto usage

## High-Frequency Rules (Stay in Main Context)

These rules remain in the main context as they're frequently relevant:
- codeguard-1-hardcoded-credentials - Always relevant
- codeguard-0-input-validation-injection - Relevant for API/backend work
- codeguard-0-framework-and-languages - General coding practices
- codeguard-0-logging - Relevant for backend code
- codeguard-0-api-web-services - Relevant for backend API work
