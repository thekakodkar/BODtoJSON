# BODtoJSON 2.6.0 — local test report

Date: 20 November 2026 (Europe/Helsinki, EET, UTC+2)

Scope: `mapping.py` (`bod_to_json`, `bod_to_data`, `Mapper`), verb auto-detection, the CLI `to-json --rules <template>`, and `POST /map`.

| Check | Result |
| ----- | ----- |
| `ruff check src tests scripts` / `mypy src` | Clean |
| `pytest`, Python 3.13 `[api,dev]` | **330 passed**, coverage 99.1% |
| User's ION template, unchanged, against a three-line PO with coding lines | Exact expected output (`tests/test_mapping.py::test_users_rules_one_call`) |
| 2.5 flat rules via `bod_to_json` and `to_records(rules=)` | Unchanged behaviour |

---

# BODtoJSON 2.5.0 — local test report

Date: 20 November 2026 (Europe/Helsinki, EET, UTC+2)

Scope: transformation rules (`transforms.py`), JSON → BOD (`reverse.py`), CLI (`cli.py`, `__main__.py`), and the API endpoints `/transform` and `/convert/bod`.

| Check | Result |
| ----- | ----- |
| `ruff check src tests scripts` | All checks passed |
| `mypy src` | No issues (8 source files) |
| `pytest`, Python 3.13.5, `[api,dev]` | **224 passed**, coverage **98.8%** (gate 90%) |
| `pytest`, Python 3.10.22, `[api,dev]` | **224 passed**, coverage 98.8% |
| Core-only venv (no extras), mapper + safe_xml + transforms + reverse + CLI suites | **206 passed**, coverage 98.9% (`api.py` omitted) |
| Round trip `to_records(include_header=True)` → `json_to_bod` → `to_records` | Identical for both sample BODs and a multi-noun, repeated-line, mixed-content case |
| Runtime requirements | Still none (`dependencies = []`) |

---

# BODtoJSON 2.4.0 — local test report

Date: 15 November 2026, 14:23 Europe/Helsinki (EET, UTC+2)

This report covers the local-only 2.4.0 zero-dependency core work in `/workspace/bodtojson-2.4.0`. Nothing was pushed, tagged, committed to a remote, or uploaded to PyPI.

## What was already in place

Source, tests, `pyproject.toml`, README, CHANGELOG, SECURITY, and CONTRIBUTING were already updated to 2.4.0 from the earlier session. `docs/index.html` was also already updated (title, badge, hero text, install pins, footer, “Secure Parsing (stdlib)” tag). This session finished coverage, a bytes-input fix, packaging, the test matrix, and the deliverable archives.

## Scope completed in this session

- Raised unit-test coverage from 82% to **97.37%** (target >= 90%).
- Fixed a regression where `to_json` / `_check_size` / `_parse` crashed on `bytes` input (`AttributeError: 'bytes' object has no attribute 'encode'`). The public API now accepts `str` or `bytes`, including UTF-16/32 and BOM payloads. CHANGELOG notes this.
- Tightened `.github/workflows/ci.yml` so the core-only job asserts that *unconditional* runtime requires are empty (extras may still appear as marked `Requires-Dist`).
- Set `[tool.mypy] python_version = "3.10"` so current mypy runs cleanly. Runtime `requires-python` remains `>=3.8`.
- Built sdist + wheel, ran `twine check`, installed the wheel in a clean venv, ran tests from the extracted sdist, executed attack probes, and confirmed 2.3.1 output parity.

## Commands and results

### Static checks (Python 3.13.5 venv with `[api,dev]`)

```
ruff check src tests scripts
# All checks passed!

mypy src
# Success: no issues found in 4 source files
```

Source grep for `import defusedxml`, `from defusedxml`, and `ElementTree.fromstring` / `ET.fromstring(`: clean.

### Pytest — Python 3.13.5

```
python -m pytest -v -p no:cacheprovider --cov=BODtoJSON --cov-report=term-missing
```

**59 passed**, 4 warnings (Starlette TestClient deprecation + expected `convert()` DeprecationWarning).

Coverage (fail_under=90):

| Module        | Stmts | Miss | Cover | Missing |
|---------------|------:|-----:|------:|---------|
| `__init__.py` |     3 |    0 |  100% |         |
| `api.py`      |    78 |    2 |   97% | 79-80 (malformed error-JSON fallback in `_handle_library_result`) |
| `mapper.py`   |   217 |    6 |   97% | 85, 91, 184, 261, 280, 287 |
| `safe_xml.py` |   120 |    3 |   98% | 218, 221, 224 (expat entity / ext-ref / skipped-entity handlers; pre-scan usually rejects first) |
| **TOTAL**     |   418 |   11 | **97.37%** | |

### Pytest — Python 3.10.22

Same suite, same flags: **59 passed**, coverage **97.10–97.37%** (after the bytes-input test). Required 90% reached.

### Core-only venv (no extras)

```
python3.13 -m venv /tmp/bod240-core
pip install /workspace/bodtojson-2.4.0   # no [api] / [dev]
pip install pytest pytest-cov
pytest tests/test_mapper.py tests/test_safe_xml.py
```

- Import of `to_json`, `to_records`, `project`, `convert`, `BODConverter`, `BODParseError`, `BODStructureError` succeeded.
- `fastapi` was **not** installed.
- **47 passed** (all core tests).
- `pip show BODtoJSON` → `Requires:` empty.
- `importlib.metadata.requires("BODtoJSON")` lists only extra-marked entries (`extra == "api"` / `"dev"`).

### README examples and `scripts/inspect_payload.py`

- `to_json`, `to_ndjson`, `to_records(include_header=True)`, `project`, and deprecated `convert` ran successfully against `tests/data/sync_PO_PSU000049.xml`.
- Bytes input (`Path.read_bytes()`) returns the same document id `PSU000049`.
- `inspect_payload.py` reports `BODtoJSON v2.4.0` and `STATUS: SUCCESS`.

### Build and twine

```
python -m build
twine check dist/*
```

Artifacts (SHA-256):

- `bodtojson-2.4.0-py3-none-any.whl` (15127 bytes)  
  `50f5ebc8fc92adc520a70d5f0faa22dbcf237d995d5a497325585a9685e01735`
- `bodtojson-2.4.0.tar.gz` (39770 bytes)  
  `3d37f6821453f78aaadaba8cff68ca00b2a0e0d960b9f68ff03e7884a49d02ee`

`twine check`: **PASSED** for both.

Note: setuptools 84 still injects `src/BODtoJSON.egg-info/SOURCES.txt` into a raw `python -m build` sdist even with `prune src/BODtoJSON.egg-info` in `MANIFEST.in`. The delivered tarball had that directory stripped and contains no `*.egg-info`. The wheel already used `dist-info` only.

### Clean-venv wheel install

```
python3.13 -m venv /tmp/bod240-wheel
pip install dist/bodtojson-2.4.0-py3-none-any.whl
```

`pip install` output: `Installing collected packages: bodtojson` — no other packages pulled.

`pip list` after install: only `BODtoJSON 2.4.0` and `pip 26.3`.

`pip show BODtoJSON`:

```
Name: BODtoJSON
Version: 2.4.0
Requires:
```

(`Requires` is empty.) Import of `to_json` / `__version__` succeeded (`2.4.0`).

### Tests from the extracted sdist

```
tar -xzf dist/bodtojson-2.4.0.tar.gz
pip install './bodtojson-2.4.0[api,dev]'
cd bodtojson-2.4.0 && pytest
```

**59 passed**, coverage **97.37%**.

### Attack probes (all rejected)

Standalone probes via the clean wheel venv, plus the unit tests in `tests/test_safe_xml.py` and `tests/test_mapper.py`. No secret file contents leaked.

| Probe | Result |
|-------|--------|
| XXE file entity (`SYSTEM` file URI) | REJECTED (pre-parse DOCTYPE/ENTITY scan) |
| External DTD (`<!DOCTYPE ... SYSTEM ...>`) | REJECTED |
| Billion-laughs entity expansion | REJECTED |
| Quadratic blowup | REJECTED |
| Parameter entity | REJECTED |
| `<!DOCTYPE` after a comment | REJECTED |
| UTF-16 LE / UTF-16 BE / UTF-32 LE DOCTYPE | REJECTED (raw-byte scan) |
| UTF-8 BOM DOCTYPE | REJECTED (raw-byte scan) |
| Oversized document (`max_size=16`) | REJECTED (`BODParseError`) |
| Over-deep document (`max_depth=5`) | REJECTED (`BODParseError`) |

### Output parity vs 2.3.1

Compared `to_json`, `to_ndjson`, and `to_records(..., include_header=True)` against frozen baselines in `tests/data/baselines_2_3_1/`:

- `sync_PO_PSU000049.xml` — MATCH (10 flattened keys)
- `sync_PO_PSU000050.xml` — MATCH (10 flattened keys)
- Namespace matrix (default `xmlns`, `xmlns:xsi` first, prefixed-only, single-quoted `xmlns`, two `xmlns`, child-level `xmlns`) — all MATCH

`SAMPLE_DIFFS: 0`. Unit test `test_output_parity_with_2_3_1` passed.

### API status codes (with `[api]`)

Covered by `tests/test_api.py`: 200 happy path, 400 malformed / structure errors (including `/convert/ndjson` and legacy `/convert`), 413 oversize on raw and JSON-wrapper / `/project` routes (middleware), 500 unexpected errors, `/` reports version `2.4.0`.

## Remote status (unchanged)

```
git ls-remote https://github.com/thekakodkar/BODtoJSON.git refs/heads/master
# 5a53b939ac64755b22f634f9986c9bd83883a9c4    refs/heads/master
```

The work tree `/workspace/bodtojson-2.4.0` has no `.git` directory. No push, tag, PR, issue, comment, or PyPI upload was performed.

## Deliverables

- Source zip: `/workspace/bodtojson-2.4.0.zip`  
  Excludes `.git`, `.coverage`, `.ruff_cache`, `.mypy_cache`, `__pycache__`, venvs, `build/`, `dist/`, `*.egg-info`, and gitignored `output_preview.json`.
- Distribution artifacts: `/workspace/bodtojson-2.4.0-dist/`  
  (`bodtojson-2.4.0.tar.gz`, `bodtojson-2.4.0-py3-none-any.whl`)
