# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in ViT-CORE-FORENSICS (authentication
bypass, injection, path traversal, etc.), please report it privately rather
than opening a public GitHub issue.

- Use GitHub's [private vulnerability reporting](../../security/advisories/new)
  feature for this repository, or
- Contact the maintainer directly via the email listed on the GitHub profile.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any suggested remediation, if known

## Known Security Considerations

This project documents several deliberate trade-offs in `README.md` under
**Security & Deployment Notes** — notably that the frontend `X-API-KEY` is
compiled into the public JS bundle and is not a true secret. This is a known,
documented design constraint, not a vulnerability requiring private disclosure.
Reports about this specific behaviour will be referred to that section.

## Supported Versions

Only the latest version on `main` is supported with security fixes.
