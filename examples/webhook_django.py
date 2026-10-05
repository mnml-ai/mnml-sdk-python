"""A Django view for job events. Map it in urls.py and exempt it from CSRF."""

import os

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from mnml_ai import WebhookVerificationError, verify_webhook


@csrf_exempt
@require_POST
def mnml_webhook(request: HttpRequest) -> HttpResponse:
    try:
        event = verify_webhook(request.body, request.headers, os.environ["MNML_WEBHOOK_SECRET"])
    except WebhookVerificationError:
        return HttpResponse(status=400)
    if event["type"] == "job.succeeded":
        job = event["data"]  # noqa: F841 — the job, as jobs.get returns it
    return HttpResponse(status=204)
