# Changelog

All notable changes to this package are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## 0.1.0 — unreleased

First release.

- `Mnml` client for the mnml API v1: renders, edits, enhancements, videos, uploads, jobs
  (`get`, `wait`, `cancel`), account and engines.
- Retries for 429, 5xx and dropped connections, with `Retry-After` up to a minute.
- An `Idempotency-Key` on every spending call, kept across retries.
- `MnmlError` with the API's `code`, `status`, `request_id` and validation `issues`.
- `verify_webhook` and `sign_webhook` (Standard Webhooks).
- Typed answers in `mnml_ai.types`, and `py.typed`. No dependencies, Python 3.9+.
