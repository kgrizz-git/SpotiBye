# Backend Deployment Tracking Suggestions

This document outlines several suggestions for keeping track of when the backend was last deployed, and communicating to AI agents when a deployment is necessary and what changes have been made since the last deployment.

## 1. Local State File (`.deployed-commit.json`)
Create a local un-tracked state file (e.g., `src/backend/.deployed-commit.json`) that records the last deployed commit hash and the deployment timestamp.
- **Implementation:** Modify the `deploy` scripts in `src/backend/package.json` to run a post-deploy step:
  `"deploy:prod": "wrangler deploy --env production && git rev-parse HEAD > .deployed-commit && date -u > .deployed-timestamp"`
- **Agent Usage:** Add a rule in `AGENTS.md` or `.cursor/rules/` that instructs agents to read this file and compare it against `HEAD`. An agent can then run `git diff $(cat src/backend/.deployed-commit)..HEAD src/backend` to instantly see pending changes.

## 2. Git Tags
Tag deployments in Git with a specific prefix (e.g., `backend-prod-<date>`).
- **Implementation:** Create a helper script (e.g., `scripts/deploy-backend.sh`) that runs `wrangler deploy` and then automatically creates and pushes a tag like `backend-prod-2026-06-22`.
- **Agent Usage:** Agents can run `git describe --match "backend-prod-*" --abbrev=0` to find the last deployment tag, and use `git log <tag>..HEAD -- src/backend/` to list all commits made since then.

## 3. Dedicated Status Script
Provide a script like `scripts/backend-deploy-status.sh` that aggregates this information in an easily readable format.
- **Implementation:** The script would fetch the last deployed commit (from a tag or local file), run a diff against the current workspace, and output:
  - Last deployment date and commit hash
  - List of files changed in `src/backend/` since then
  - A clear boolean recommendation: `Needs Deployment: YES/NO`
- **Agent Usage:** Instruct agents in `AGENTS.md` to execute this script whenever asked about the backend status or before finalizing a feature that touches the backend.

## 4. Documentation & Agent Rules (`AGENTS.md`)
Whatever technical solution is chosen, you must document it explicitly so agents know how to interact with it.
- **Implementation:** Add a new section to `AGENTS.md` (e.g., `## Backend Deployments`) detailing how to check the deployment status. 
- **Example Rule:** 
  > **Backend Deployments:** To check what changes are pending deployment, run `./scripts/backend-deploy-status.sh` or compare HEAD to the commit hash in `src/backend/.deployed-commit`. If there are un-deployed changes in `src/backend/`, ask the user if they would like you to deploy them.

## Recommended Approach
A combination of **Option 1 (Local State File)** and **Option 4 (Agent Rules)** is often the most straightforward for AI agents, as they can quickly cat the file and use standard git commands to see the diffs without needing external API calls to Cloudflare. If you work across multiple machines, **Option 2 (Git Tags)** is better since it syncs via the remote repository.
