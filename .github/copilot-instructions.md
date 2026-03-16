# Repository Copilot Instructions

## Changelog Maintenance Rule

When a change affects user-visible behavior, update CHANGELOG.md in the same pull request.

User-visible changes include:
- New features or removed features
- Bug fixes that alter behavior
- UI and UX changes users can notice
- Build and distribution changes that affect delivered artifacts

Changelog updates should:
- Add concise bullet points under the correct unreleased or release version section
- Use sections such as Added, Changed, Fixed, and Known Issues as appropriate
- Keep entries focused on outcomes and user impact

Changelog updates are not required for internal-only changes, such as:
- Refactors with no user-visible behavior changes
- Test-only changes
- Documentation-only updates that do not change product behavior
- CI/internal tooling changes with no user-facing impact
