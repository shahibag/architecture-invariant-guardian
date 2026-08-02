# Security Policy

## Supported release line

Invariant Guardian follows a single supported release line.

- **Current release:** `v0.2.0`
- **Default branch:** `main`
- Security fixes are applied to `main` and released as a new immutable tag; previous tags are never rewritten.

## Reporting a vulnerability

If you discover a security issue in Invariant Guardian, please report it privately.

- Open a **private vulnerability report** through GitHub at <https://github.com/shahibag/architecture-invariant-guardian/security/advisories/new>.
- Email the maintainer at the address listed on the GitHub profile if GitHub Advisories is unavailable.
- Allow up to five business days for an initial response.

Please do **not** open public issues, pull requests, or discussions for undisclosed security vulnerabilities, and do **not** post secrets, tokens, or private repository data in any public channel.

## Secrets and credentials

- Never commit API keys, tokens, or passwords to this repository.
- Use GitHub Actions secrets (`Settings > Secrets and variables > Actions`) for provider keys such as `DEEPSEEK_API_KEY`.
- For local development, store secrets in `.env.local` (ignored by Git) with file mode `600`.
- Do not pass secrets through workflow `env`, Docker build arguments, `echo`, or log output.
- Report accidental secret exposure immediately so the credential can be revoked and rotated.

## Action security boundary

Invariant Guardian is a GitHub Action that reads pull-request metadata and changed files and may call a configured LLM provider.

- It requests only `contents: read` and `pull-requests: write` permissions.
- It reads target Java source and patches from GitHub's API; it does **not** compile, import, or execute contributor code.
- It sends a bounded evidence package to the configured provider; full source trees, PR descriptions, and comments are not included.
- Fork pull requests do not invoke the provider and do not publish comments.
- Provider responses are validated against a strict schema before any comment is rendered.

## What is in scope

- Disclosure of secrets through logs, comments, or Action outputs.
- Execution or compilation of target-repository code by the Action.
- Path traversal or unsafe local file writes.
- Unauthorized modification of contributor comments.
- Prompt injection that alters the judge contract or invents findings.
- Elevation of workflow permissions beyond the documented minimum.

## What is out of scope

- Security of the target repository's own code, dependencies, build scripts, or runtime environment.
- Availability or security of the configured LLM provider's API.
- Social engineering, credential phishing, or compromise of a maintainer's GitHub account.
- General code-quality or architecture findings that are not security vulnerabilities.

## Security-related configuration

- Pin the Action to an immutable release tag, e.g. `shahibag/architecture-invariant-guardian@v0.2.0`.
- Pin third-party actions to full commit SHAs in production workflows.
- Restrict `pull-requests: write` to jobs that need it, and never grant it to jobs that run untrusted build steps.
- Review the [known limitations](docs/known-limitations-v0.2.md) before enabling the Action on private repositories.

## Acknowledgments

We credit reporters who responsibly disclose valid vulnerabilities in release notes unless they request anonymity.
