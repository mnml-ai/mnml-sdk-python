# Changelog

All notable changes to this package are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## 0.2.0 — unreleased

Amounts in US dollars. API v2 now answers every amount in dollars beside the credits; the SDK
names the dollar keys and steers you to them. Nothing is removed, so 0.1.0 code still runs.

- New keys, each a number of US dollars to four decimals: `charged_usd` on every create call
  (`RenderStarted`, `JobStarted`); `charged_usd` and `refunded_usd` on `Job`; `refunded_usd` on
  `JobCanceled`; `balance_usd`, `key.daily_limit_usd` and `limits.daily_usd` on `Account`;
  `render_usd` and `edit_usd` on `EnginePrices`; `usd` on `VideoPrice`; `balance_usd` and
  `threshold_usd` on the `credits.low` webhook's `CreditsLow`.
- Deprecated (documented in `mnml_ai.types`, removed in a later release): `credits_charged`,
  `credits_refunded`, `Account["credits"]` (`AccountCredits.spendable`), `daily_credit_limit`,
  `daily_credits`, `EnginePrices` `render` and `edit`, `VideoPrice` `credits`, and `CreditsLow`
  `balance` and `threshold`. Each names the dollar key to read instead. Answers are plain dicts,
  so reading a deprecated key raises no warning.
- `spec/openapi.json` refreshed (Nov 9 2026). `tests/test_spec.py` now also checks that the SDK
  deprecates exactly the keys the spec does.
- README and examples read the dollar keys.

## 0.1.0

First release.

- Speaks API v2: every call is under `/v2` (`/v1` is now the mnmlai.dev API, which the SDK
  does not call). `uploads.create`, `upload_id` and `mask_upload_id` are gone, as the API no
  longer has uploads: send the image in the call, or a finished `job_id`.
- A create call's `status` is typed `JobStatus`, as the API now promises (it once answered
  the raw stored status on an idempotent replay). `spec/openapi.json` refreshed (Oct 18 2026).
- `jobs.stream(job_id)`: follow a job over one connection (Server-Sent Events), as a generator of
  `JobStreamEvent`s: `job` as it changes, then `done`, `timeout` or `error`. `Mnml` takes a
  `stream_transport` for it, as it takes `transport`.

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
