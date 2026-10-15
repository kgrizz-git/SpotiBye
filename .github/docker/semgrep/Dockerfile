# Pin for the Semgrep SAST step in .github/workflows/security.yml.
# Never built: the workflow reads the image reference from the FROM line
# and runs it directly. It lives in a Dockerfile only so Dependabot's
# docker ecosystem can see it and open bump PRs (an image named inside a
# workflow `run:` script is invisible to Dependabot).
FROM semgrep/semgrep:1.180.0@sha256:529ee8a277ec8adc5b534d7c74eea0a47e9de21d62852b6ba7ac6ba9566845c3
