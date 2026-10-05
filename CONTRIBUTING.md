# Contributing

Issues and pull requests are welcome.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
mypy
```

CI runs the same checks on Python 3.9 to 3.13.

## The API's shape

`spec/openapi.json` is the API's published OpenAPI document. `tests/test_spec.py` checks that
the client has a method for every operation and that `mnml_ai/types.py` names every answer
field. When the API changes:

```bash
python scripts/update_spec.py   # refresh spec/openapi.json
pytest                          # test_spec.py names what to add to mnml_ai/types.py
```

## Releasing

Maintainers only. Releases are published by hand from a clean `main`:

1. Bump `VERSION` in `src/mnml_ai/_client.py` (the package version is read from it) and add
   the entry to `CHANGELOG.md`.
2. Commit, then tag: `git tag v0.1.0 && git push --tags`.
3. `python -m build && python -m twine upload dist/*`.
4. Create a GitHub release from the tag with the changelog entry.

Never commit credentials. Tests run against a fake transport and need no API key.
