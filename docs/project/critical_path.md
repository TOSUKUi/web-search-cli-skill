# Critical Path

## Current Goal

Deliver a CLI and Codex skill combination that can replace the `hermes-web-search-plus` search tool functionality without requiring Hermes plugin hosting.

## Active Dependency Chain

1. Preserve the reference search engine behavior in a standalone CLI package.
2. Expose stable invocation paths: module command, installed console script, and direct repository runner.
3. Provide credential/config templates for all supported providers.
4. Provide a Codex skill that tells agents when and how to invoke the CLI.
5. Run non-network validation, then defer live search validation until credentials or SearXNG are available.

## Known Blockers

- Live provider validation is blocked until at least one provider credential or `SEARXNG_INSTANCE_URL` is configured.

## Recent Path Changes

- The project goal was clarified: complete search-tool replacement as CLI plus skill, not a lightweight wrapper and not a Hermes plugin port.
