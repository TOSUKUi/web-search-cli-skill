# Critical Path

## Current Goal

Deliver a CLI and Codex skill combination that can replace the `hermes-web-search-plus` search tool functionality without requiring Hermes plugin hosting.

## Active Dependency Chain

1. Preserve the reference search engine behavior in a standalone CLI package.
2. Expose stable invocation paths: module command, installed console script, and direct repository runner.
3. Provide credential/config templates for all supported providers.
4. Provide a Codex skill that tells agents when and how to invoke the CLI.
5. Maintain a provider catalog that distinguishes recurring monthly quotas, daily quotas, one-time credits, and SERP-scraping products.
6. Support multiple provider API keys without breaking legacy credentials.
7. Support optional satellite clients backed by one central config/search server.
8. Run non-network validation, then defer live search validation until credentials or SearXNG are available.

## Known Blockers

- Live provider validation is blocked until at least one provider credential or `SEARXNG_INSTANCE_URL` is configured.
- Live satellite search also requires credentials on the central server; local server startup is available without them.
- Browser signup attempts can be blocked by CAPTCHA, existing OAuth-only accounts, email verification, or acceptance of provider terms; no credentials are committed to the repository.

## Recent Path Changes

- The project goal was clarified: complete search-tool replacement as CLI plus skill, not a lightweight wrapper and not a Hermes plugin port.
- Provider expansion remains compatible with the existing centralized dispatch/fallback model; the four new adapters are explicit/fallback providers and do not change intent routing.
- Docker Compose is an optional deployment path for the central server; local CLI behavior remains the default.
