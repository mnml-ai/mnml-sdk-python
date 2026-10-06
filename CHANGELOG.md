# Changelog

All notable changes to this package are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## 0.1.0 — unreleased

First release.

- `Mnml` client for the mnml API v1: renders, edits, enhancements, videos, uploads, jobs
  (`get`, `wait`, `wait_all`, `cancel`), account and engines.
- Every request field as a typed keyword argument; a field the API does not take is a `TypeError`.
- `create_and_wait` on renders, edits, enhancements and videos: start a job and wait for it.
- `files.download(output, to=None)`: a job output's bytes and content type, from its signed link,
  without sending the key.
- `TypedDict`s for every answer, the nested ones included (engine prices and capabilities, video
  prices, account limits), and `Literal`s for the values the API takes: engine and video model ids,
  camera moves, motion, modes, aspect ratios.
- `WebhookEvent` as a union that narrows `data` on `type` (`job.*`, `credits.low`, `webhook.test`).
- A migration table from the v3 routes to SDK calls.
- Retries for 429, 5xx and dropped connections, with `Retry-After` up to a minute.
- An `Idempotency-Key` on every spending call, kept across retries.
- `MnmlError` with the API's `code`, `status`, `request_id` and validation `issues`.
- `verify_webhook` and `sign_webhook` (Standard Webhooks).
- Typed answers in `mnml_ai.types`, and `py.typed`. No dependencies, Python 3.9+.
