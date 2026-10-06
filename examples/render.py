"""Render a massing image, wait for it, and save the result.

MNML_API_KEY=mk_live_... python examples/render.py
"""

from mnml_ai import Mnml, MnmlError

mnml = Mnml()

try:
    job = mnml.renders.create_and_wait(
        mode="exterior",
        engine="v4.6-ultra",
        image_url="https://developers.mnml.ai/sdk/input-model.webp",
        prompt="Timber facade, late afternoon light, olive trees",
    )[0]
    if job["status"] == "succeeded":
        # Output links are signed and expire in an hour or two: download what you keep.
        file = mnml.files.download(job["outputs"][0])
        ext = (file["content_type"] or "image/jpeg").split("/")[1]
        path = f"render-{job['id']}.{ext}"
        with open(path, "wb") as out:
            out.write(file["data"])
        print(f"Saved {path} ({job['credits_charged']} credits)")
    else:
        print(f"Job {job['status']}: {job['error']['message'] if job['error'] else ''}")
except MnmlError as err:
    print(f"{err.code} ({err.status}): {err} [request {err.request_id}]")
