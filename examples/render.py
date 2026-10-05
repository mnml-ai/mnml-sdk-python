"""Render a massing image, wait for it, and print the output link.

MNML_API_KEY=mk_live_... python examples/render.py
"""

from mnml_ai import Mnml, MnmlError

mnml = Mnml()

try:
    started = mnml.renders.create(
        mode="exterior",
        image_url="https://developers.mnml.ai/sdk/input-model.webp",
        prompt="Timber facade, late afternoon light, olive trees",
    )
    print(f"Started job {started['id']}, {started['credits_charged']} credits")

    job = mnml.jobs.wait(started["id"])
    if job["status"] == "succeeded":
        # Output links are signed and expire in an hour or two: download what you keep.
        print(job["outputs"][0]["url"])
    else:
        print(f"Job {job['status']}: {(job['error'] or {}).get('message', '')}")
except MnmlError as err:
    print(f"{err.code} ({err.status}): {err} [request {err.request_id}]")
