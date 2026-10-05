# mnml Python SDK

The official Python client for the [mnml API](https://developers.mnml.ai): architecture
renders, edits, enhancements and video, from your own product.

- Retries, timeouts and idempotency keys handled for you
- `jobs.wait()` to poll a job until it settles
- Webhook signature verification
- Typed answers (`TypedDict`), checked against the API's OpenAPI document
- No dependencies. Python 3.9+

```bash
pip install mnml-ai
```

## Quick start

Create an API key in the [console](https://developers.mnml.ai/console/keys), then:

```python
from mnml_ai import Mnml

mnml = Mnml()  # reads MNML_API_KEY

started = mnml.renders.create(
    mode="exterior",
    image_url="https://example.com/massing.png",
    prompt="Timber facade, late afternoon light, olive trees",
)

job = mnml.jobs.wait(started["id"])
print(job["status"], job["outputs"][0]["url"] if job["outputs"] else None)
```

Every call spends credits from your prepaid API balance. Top it up in dollars on
[Billing](https://developers.mnml.ai/console/billing).

## Configuration

```python
mnml = Mnml(
    api_key=None,  # defaults to the MNML_API_KEY environment variable
    max_retries=2,  # retries for a 429, a 5xx or a dropped connection
    timeout=60.0,  # seconds, per request
)
```

## Methods

| Method                          | Endpoint                    | What it does                                        |
| ------------------------------- | --------------------------- | --------------------------------------------------- |
| `renders.create(**body)`        | `POST /v1/renders`          | Render from an image, or from a prompt alone        |
| `edits.create(**body)`          | `POST /v1/edits`            | Edit or erase, over the whole image or a region     |
| `enhancements.create(**body)`   | `POST /v1/enhancements`     | Upscale, enhance, remove the background, outpaint   |
| `videos.create(**body)`         | `POST /v1/videos`           | Video from a still                                  |
| `uploads.create(file, ...)`     | `POST /v1/uploads`          | Upload an image to use as a source or mask          |
| `jobs.get(id)`                  | `GET /v1/jobs/{id}`         | Read a job                                          |
| `jobs.wait(id, ...)`            | `GET /v1/jobs/{id}`         | Read a job until it succeeds, fails or is cancelled |
| `jobs.cancel(id)`               | `POST /v1/jobs/{id}/cancel` | Cancel a job (refunded if it had not produced yet)  |
| `account.get()`                 | `GET /v1/account`           | Balance, tier and limits for this key               |
| `engines.list()`                | `GET /v1/engines`           | Engines, video models, prices and capabilities      |

Create calls take the API's fields as keyword arguments, exactly as the
[reference](https://developers.mnml.ai/docs/renders) names them, and every call returns the
answer's `data` as a `dict`.

### Sources

A source image is one of your uploads, a public URL, or a finished job:

```python
mnml.renders.create(upload_id=upload["id"], prompt="Brick and glass, dusk")
mnml.renders.create(image_url="https://example.com/plan.png", prompt="Brick and glass, dusk")
mnml.edits.create(job_id=job["id"], prompt="Dark brick instead of render")
```

### Uploads

```python
upload = mnml.uploads.create("massing.png")  # a path, bytes, or an open binary file
mnml.renders.create(upload_id=upload["id"], prompt="Concrete and glass, overcast")

# Or have the API fetch a public image:
mnml.uploads.create(url="https://example.com/massing.png")
```

### Waiting for a job

```python
job = mnml.jobs.wait(job_id, interval=3.0, timeout=600.0)
```

`jobs.wait` raises `MnmlTimeoutError` when its own time runs out. The job keeps running, so
read it again later. Output links are signed and expire after an hour or two; download what
you want to keep. For long jobs such as video, prefer a [webhook](#webhooks) to polling.

## Errors

A refusal raises `MnmlError`, carrying the API's `code`, the HTTP `status` and the
`request_id` to quote to support:

```python
from mnml_ai import MnmlError

try:
    mnml.renders.create(image_url=url, prompt=prompt)
except MnmlError as err:
    if err.code == "INSUFFICIENT_CREDITS":
        ...  # top up, then send it again
    raise
```

On `VALIDATION_FAILED`, `err.issues` lists each refused field. Every code is described at
[developers.mnml.ai/docs/errors](https://developers.mnml.ai/docs/errors).

## Retries and idempotency

The client retries a `429`, a `5xx` or a dropped connection, twice by default. It waits out
`Retry-After` when that is a minute or less, and otherwise raises the error to you. That
covers a daily limit, which resets at midnight UTC.

Every call that can spend credits carries an `Idempotency-Key`, and the client reuses the same
key across its own retries, so a retry never charges twice. To make your own retries safe as
well, pass a key you choose:

```python
mnml.renders.create(prompt=prompt, image_url=url, idempotency_key=f"order-{order_id}")
```

## Webhooks

Add an endpoint and copy its signing secret on the
[Webhooks](https://developers.mnml.ai/console/webhooks) page. Then verify each delivery with
the raw request body, before parsing it:

```python
import os
from flask import Flask, request
from mnml_ai import WebhookVerificationError, verify_webhook

app = Flask(__name__)


@app.post("/webhooks/mnml")
def mnml_webhook():
    try:
        event = verify_webhook(request.get_data(), request.headers, os.environ["MNML_WEBHOOK_SECRET"])
    except WebhookVerificationError:
        return "", 400
    if event["type"] == "job.succeeded":
        job = event["data"]  # the job, as jobs.get returns it
    return "", 204
```

`verify_webhook` raises `WebhookVerificationError` on a bad signature or a stale timestamp
(over five minutes). Events: `job.succeeded`, `job.failed`, `job.canceled`, `credits.low` and
`webhook.test`. The scheme is [Standard Webhooks](https://www.standardwebhooks.com). See
[`examples/`](./examples) for FastAPI and Django.

## Typing

The answers are typed as `TypedDict`s in `mnml_ai.types` (`Job`, `RenderStarted`, `Upload`,
`Account` and more), and the package ships `py.typed`. A test in this repository checks every
field against the API's OpenAPI document ([`spec/openapi.json`](./spec/openapi.json)).

## Links

- [Documentation](https://developers.mnml.ai/docs)
- [API reference](https://developers.mnml.ai/docs/renders)
- [TypeScript SDK](https://github.com/mnml-ai/mnml-sdk-typescript)
- [Changelog](./CHANGELOG.md)

## License

[MIT](./LICENSE)
