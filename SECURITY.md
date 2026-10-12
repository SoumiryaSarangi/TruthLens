# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 1.0.x | yes |
| earlier | no |

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private vulnerability reporting for this
repository (the "Security" tab, then "Report a vulnerability"), or contact the maintainer through the address on their
GitHub profile. Include what you found, how to reproduce it, and what you think the impact is. This is a student project
maintained by one person: expect an acknowledgement within a few days, and please allow reasonable time before disclosing.

## Scope and threat model

TruthLens is built to run **on one machine, for one reader**, bound to `127.0.0.1:8000`. It has **no authentication** and
no rate limiting, and is not hardened for exposure to an untrusted network. If you put it behind a reverse proxy on a
network, add authentication, TLS and rate limiting there; the live look-up spends a third-party API quota and the models
are expensive to run.

What the project does take care over:

- **The Google Fact Check API key** lives only in a git-ignored `.env`. It is redacted from cache paths and logs, and the
  tests check that it never reaches the cache directory. **Never commit it, paste it into an issue, or put it in a URL.**
  If a key is exposed, revoke it in the Google Cloud console and issue a new one; rewriting git history alone is not
  enough.
- **Raw dataset text** and the owner-written claim files in `data/private/` are git-ignored and must stay out of the
  repository.
- **Input handling:** messages are length-limited (4000 characters) and Unicode-normalised, and the web client renders
  them as text. Source passages come from third parties and are HTML-escaped before display.
- **The page makes no request except to its own server.** Server-side, only the live look-up reaches Wikipedia and Google,
  and only when requested.

Out of scope: denial of service by a local user, and attacks that need an attacker who already controls the machine or
its `.env`.
