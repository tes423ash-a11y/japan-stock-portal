# Security

## Secrets

- Never commit `.env`, API keys, brokerage credentials, cookies, private keys or webhook tokens.
- Store future J-Quants or AI credentials only in GitHub Actions secrets.
- The published site reads local JSON and does not require credentials in the browser.

## Supply chain

- GitHub Actions are pinned to full commit SHAs.
- Report generation runs with `contents: read`; only the isolated publish job receives `contents: write`.
- The vendored Lightweight Charts file is version-pinned and SHA-256 checked by `scripts/security_audit.py`.
- Dependabot checks Python and GitHub Actions dependencies weekly.

## Reporting a vulnerability

Do not open a public issue containing credentials or exploitable details. Contact the repository owner privately through GitHub account contact information and rotate any exposed secret immediately.
