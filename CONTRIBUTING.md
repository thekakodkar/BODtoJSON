# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[api,dev]"
```

## Tests

```bash
python -m pytest -v -p no:cacheprovider --cov=BODtoJSON --cov-report=term-missing
```

API tests are skipped automatically if FastAPI/httpx are not installed.

## Guidelines

- Keep public API backward compatible.
- Do not publish or tag without explicit owner approval.
- Prefer focused commits.
- Run the full test suite before opening a PR.
