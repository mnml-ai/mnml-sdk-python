# Changelog

All notable changes to this package are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## 0.1.0 — unreleased

First release.

- Speaks API v2: every call is under `/v2` (`/v1` is now the mnmlai.dev API, which the SDK
  does not call). `uploads.create`, `upload_id` and `mask_upload_id` are gone, as the API no
  longer has uploads: send the image in the call, or a finished `job_id`.

- `image` on `renders`, `edits`, `enhancements` and `videos`: send the image in the call, with no
  upload step. A `str` (a link, a data URI or base64) is sent as it is; bytes, a `Path` or an open
  binary file is sent as a base64 data URI, as JSON.
- `references` items and `end_frame` take an image the same way, or a dict with `image`.
- `mask` on `edits`: a PNG mask in the call, white to change and black to keep.
- `image_url` still works and is deprecated: it is the old name of `image`.
- `wait` (1-90 seconds) on `renders.create` and `jobs.get`: the API holds the answer until the job
  settles. `create_and_wait` and `jobs.wait` use it, so a render is one or two calls, not a polling
  loop.
- `Mnml` client for the mnml API v2: renders, edits, enhancements, videos, jobs
  (`get`, `wait`, `wait_all`, `cancel`), account and engines.
- Every request field as a typed keyword argument; a field the API does not take is a `TypeError`.
- `create_and_wait` on renders, edits, enhancements and videos: start a job and wait for it.
- `files.download(output, to=None)`: a job output's bytes and content type, from its signed link,
  without sending the key.
- `TypedDict`s for every answer, the nested ones included (engine prices and capabilities, video
  prices, account limits), and `Literal`s for the values the API takes: engine and video model ids,
  camera moves, motion, modes, aspect ratios.
- `WebhookEvent` as a union that narrows `data` on `type` (`job.*`, `credits.low`, `webhook.test`).
- A migration table from the mnmlai.dev routes to SDK calls.
- Retries for 429, 5xx and dropped connections, with `Retry-After` up to a minute.
- An `Idempotency-Key` on every spending call, kept across retries.
- `MnmlError` with the API's `code`, `status`, `request_id` and validation `issues`.
- `verify_webhook` and `sign_webhook` (Standard Webhooks).
- Typed answers in `mnml_ai.types`, and `py.typed`. No dependencies, Python 3.9+.
