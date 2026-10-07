"""Refresh spec/openapi.json from the API's published OpenAPI document.

tests/test_spec.py then says which types need to change.
"""

import json
import os
import urllib.request
from pathlib import Path

url = os.environ.get("MNML_OPENAPI_URL", "https://api.mnml.ai/v2/openapi.json")
with urllib.request.urlopen(url, timeout=30) as res:
    spec = json.load(res)
target = Path(__file__).resolve().parent.parent / "spec" / "openapi.json"
target.write_text(json.dumps(spec, indent=2) + "\n")
print(f"spec/openapi.json updated from {url} (version {spec.get('info', {}).get('version')})")
