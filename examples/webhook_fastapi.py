"""Receive job events with FastAPI. Read the raw body for the signature check.

MNML_WEBHOOK_SECRET=whsec_... uvicorn examples.webhook_fastapi:app
"""

import os

from fastapi import FastAPI, HTTPException, Request, Response

from mnml_ai import WebhookVerificationError, verify_webhook

app = FastAPI()


@app.post("/webhooks/mnml")
async def mnml_webhook(request: Request) -> Response:
    try:
        event = verify_webhook(await request.body(), request.headers, os.environ["MNML_WEBHOOK_SECRET"])
    except WebhookVerificationError as err:
        raise HTTPException(status_code=400) from err
    if event["type"] == "credits.low":
        pass  # time to top up: https://developers.mnml.ai/console/billing
    return Response(status_code=204)
