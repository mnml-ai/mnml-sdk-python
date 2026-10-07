# mnml Python SDK

The official Python client for the [mnml API](https://developers.mnml.ai): architecture
renders, edits, enhancements and video, from your own product.

- Every endpoint of API v1: renders, edits, enhancements, video, uploads, jobs, account, engines
- Images sent in the call itself: a link, bytes, a `Path` or an open file, no upload step
- Retries, timeouts and idempotency keys handled for you
- `create_and_wait()` and `jobs.wait()` to poll a job until it settles, `files.download()` to keep
  its output
- Webhook signature verification, with typed events
- Typed keyword arguments and answers (`TypedDict`), checked against the API's OpenAPI document
- No dependencies. Python 3.9+

```bash
pip install mnml-ai
```

## Quick start

Create an API key in the [console](https://developers.mnml.ai/console/keys), then:

```python
from pathlib import Path

from mnml_ai import Mnml

mnml = Mnml()  # reads MNML_API_KEY

job = mnml.renders.create_and_wait(
    mode="exterior",
    image=Path("massing.png"),  # or a link: "https://example.com/massing.png"
    prompt="Timber facade, late afternoon light, olive trees",
)[0]
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

| Method                            | Endpoint                    | What it does                                        |
| --------------------------------- | --------------------------- | --------------------------------------------------- |
| `renders.create(...)`             | `POST /v1/renders`          | Render from an image, or from a prompt alone        |
| `edits.create(...)`               | `POST /v1/edits`            | Edit or erase, over the whole image or a region     |
| `enhancements.create(...)`        | `POST /v1/enhancements`     | Upscale, enhance, remove the background, outpaint   |
| `videos.create(...)`              | `POST /v1/videos`           | Video from a still                                  |
| `uploads.create(file, ...)`       | `POST /v1/uploads`          | Upload an image to reuse across calls               |
| `jobs.get(id)`                    | `GET /v1/jobs/{id}`         | Read a job                                          |
| `jobs.cancel(id)`                 | `POST /v1/jobs/{id}/cancel` | Cancel a job (refunded if it had not produced yet)  |
| `account.get()`                   | `GET /v1/account`           | Balance, tier and limits for this key               |
| `engines.list()`                  | `GET /v1/engines`           | Engines, video models, prices and capabilities      |
| `files.download(output, to=None)` | `GET /v1/files/{id}`        | A job output's bytes, from its signed link          |
| `jobs.wait(id, ...)`              | `GET /v1/jobs/{id}`         | Read a job until it succeeds, fails or is cancelled |
| `jobs.wait_all(ids, ...)`         | `GET /v1/jobs/{id}`         | `wait` for several jobs at once                     |
| `<resource>.create_and_wait(...)` | the create, then the job    | Start a job and wait for it (a render: every job)   |

Create calls take the API's fields as keyword arguments, exactly as the
[reference](https://developers.mnml.ai/docs/renders) names them, typed so your editor completes
them, and every call returns the answer's `data` as a `dict`. A field the API does not take is a
`TypeError` before anything is sent. `create_and_wait` is on `renders`, `edits`, `enhancements` and
`videos`; a render returns a list with one job per `count`, the others one job.

### Engines, modes and settings

`engine`, `mode`, `aspect_ratio`, `camera_movement`, `motion` and the video `model` are typed with
the values the API takes. `engines.list()` is the live list, with each engine's price and what it
can do:

```python
for engine in mnml.engines.list()["engines"]:
    print(engine["id"], engine["prices"]["render"], engine["capabilities"]["max_references"])
```

### Images

Send the image in the call, as `image`:

```python
from pathlib import Path

mnml.renders.create(image="https://example.com/plan.png", prompt="Brick and glass, dusk")
mnml.renders.create(image=Path("plan.png"), prompt="Brick and glass, dusk")
mnml.renders.create(image=png_bytes, prompt="Brick and glass, dusk")
```

A `str` is sent as it is: a public `https://` link, a `data:image/...;base64,` URI or bare base64.
Bytes, a `Path` or an open binary file is read and sent as a data URI, up to 15 MB per image. A
`str` is never read as a file, so pass `Path("plan.png")`, not `"plan.png"`. `image_url` is the
old name of `image` and still works.

Every place an image goes takes the same: `image`, each of `references`, an edit's `mask` and a
video's `end_frame`. A reference can also be a dict with a `mode`:

```python
mnml.renders.create(
    image=Path("massing.png"),
    references=[Path("timber.jpg"), {"image": "https://example.com/brick.png", "mode": "material"}],
    prompt="Timber and brick, overcast",
)
```

To work on a finished job's output without downloading it, pass its `job_id`:

```python
mnml.edits.create(job_id=job["id"], prompt="Dark brick instead of render")
```

### Uploads (optional)

You do not need an upload to send an image. Upload one when you use the same image in many calls,
and pass its `upload_id`:

```python
upload = mnml.uploads.create("massing.png")  # a path, bytes, or an open binary file
for prompt in ("Concrete and glass, overcast", "Timber, dusk", "White render, noon"):
    mnml.renders.create(upload_id=upload["id"], prompt=prompt)

# Or have the API fetch a public image:
mnml.uploads.create(url="https://example.com/massing.png")
```

### Edits, enhancements and video

```python
# Change one thing, inside a box (fractions of the image from its top-left)
mnml.edits.create(
    job_id=job_id, prompt="A red front door", region={"box": {"x": 0.4, "y": 0.5, "width": 0.2, "height": 0.4}}
)

# Or paint a mask: a PNG, white to change and black to keep
mnml.edits.create(image=Path("house.jpg"), mask=Path("door-mask.png"), prompt="A red front door")

# Remove what a region covers
mnml.edits.create(job_id=job_id, kind="erase", region={"box": {"x": 0.1, "y": 0.6, "width": 0.2, "height": 0.3}})

# Upscale, enhance, cut out, or extend to a new frame
mnml.enhancements.create(job_id=job_id, kind="outpaint", aspect_ratio="16:9")

# A ten-second camera move
mnml.videos.create(job_id=job_id, model="v2.0-flash", duration_seconds=10, camera_movement="orbit-right")
```

### Waiting for a job

```python
job = mnml.jobs.wait(job_id, interval=3.0, timeout=600.0)
```

`jobs.wait` raises `MnmlTimeoutError` when its own time runs out. The job keeps running, so
read it again later. `videos.create_and_wait` reads every 10 seconds for up to 20 minutes unless
you say otherwise. For long jobs such as video, a [webhook](#webhooks) beats polling.

### Downloading outputs

Output links are signed and expire after an hour or two. Download what you want to keep:

```python
file = mnml.files.download(job["outputs"][0], to="render.jpg")
print(file["content_type"], len(file["data"]))
```

The link's signature is its credential, so your key is not sent with it. An expired link raises
`MnmlError` with `NOT_FOUND`; read the job again for fresh links.

## Errors

A refusal raises `MnmlError`, carrying the API's `code`, the HTTP `status` and the
`request_id` to quote to support:

```python
from mnml_ai import MnmlError

try:
    mnml.renders.create(image=url, prompt=prompt)
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
mnml.renders.create(prompt=prompt, image=url, idempotency_key=f"order-{order_id}")
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
    elif event["type"] == "credits.low":
        balance = event["data"]["balance"]  # and event["data"]["threshold"]
    return "", 204
```

`verify_webhook` raises `WebhookVerificationError` on a bad signature or a stale timestamp
(over five minutes). Events: `job.succeeded`, `job.failed`, `job.canceled`, `credits.low` and
`webhook.test`; checking `event["type"]` narrows `event["data"]` for a type checker. The scheme is
[Standard Webhooks](https://www.standardwebhooks.com). See
[`examples/`](./examples) for FastAPI and Django.

## Typing

The answers are typed as `TypedDict`s in `mnml_ai.types` (`Job`, `RenderStarted`, `Upload`,
`Account`, `Engines`, `WebhookEvent` and more), the values the API takes as `Literal`s (`Mode`,
`EngineId`, `CameraMove` …), and the package ships `py.typed`. A test in this repository checks
every keyword argument, field and listed value against the API's OpenAPI document
([`spec/openapi.json`](./spec/openapi.json)).

## Moving from the v3 API

The v3 routes (`/v1/archDiffusion-v46`, `/v1/upscale`, `/v1/status/{id}` …) still answer on
`api.mnml.ai`, deprecated, so nothing breaks while you move. The SDK speaks API v1 only. Each old
route has a v1 call that does the same job:

| v3 route                                                      | SDK call                                                      |
| ------------------------------------------------------------- | ------------------------------------------------------------- |
| `archDiffusion-v46`                                           | `renders.create(engine="v4.6-ultra", ...)`                    |
| `archDiffusion-v45`, `-v45-lite`                              | `renders.create(engine="v4.5-ultra")`, `"v4.5-fast"`          |
| `archDiffusion-v44`, `-v44-lite`                              | `renders.create(engine="v4.4-ultra")`, `"v4.4-fast"`          |
| `archDiffusion-v43`, `-v43-lite`, `-v42`, `-v42-lite`, `-v41` | `renders.create(engine="v4.3")`, `"v4.3-fast"`                |
| `mixture-of-experts`                                          | `renders.create(mode=..., ...)` (`expert_name` is the `mode`) |
| `exterior`, `interior`, `sketch-to-img`                       | `renders.create(engine="v3.1", mode=..., ...)`                |
| `style/transfer`                                              | `renders.create(references=[{..., "mode": "style"}], ...)`    |
| `imagine-ai`                                                  | `renders.create(mode="text-to-render", prompt=...)`           |
| `virtual-staging-ai` (v1 and v2)                              | `renders.create(mode="interior", ...)`                        |
| `inpaint`                                                     | `edits.create(prompt=..., mask=...)` or `region`              |
| `ai-eraser`                                                   | `edits.create(kind="erase", region=...)`                      |
| `upscale`, `render/enhancer`                                  | `enhancements.create(kind="upscale")`, `kind="enhance"`       |
| `video-v20-flash`, `video-v20-cinematic`, `video-ai`          | `videos.create(model="v2.0-flash")`, `"v2.0"`, `"v1.1"`       |
| `status/{id}` (v1 and v2)                                     | `jobs.get(id)` or `jobs.wait(id)`                             |
| `credits`                                                     | `account.get()`                                               |

v1 takes the image in the request, like v3 did: pass it as `image` (a link, bytes or a `Path`).
An `upload_id` (from `uploads.create`) is optional, for one image you reuse across calls, and a
`job_id` works on a finished job's output. The full guide is at
[developers.mnml.ai/docs/migrate](https://developers.mnml.ai/docs/migrate).

## Links

- [Documentation](https://developers.mnml.ai/docs)
- [API reference](https://developers.mnml.ai/docs/renders)
- [TypeScript SDK](https://github.com/mnml-ai/mnml-sdk-typescript)
- [Changelog](./CHANGELOG.md)

## License

[MIT](./LICENSE)
