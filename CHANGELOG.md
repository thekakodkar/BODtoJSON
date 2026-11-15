# Changelog

## [2.3.1] - 2026-11-15

### Security
- Switched XML parsing to `defusedxml` to reject entity expansion (billion-laughs) and XXE.
- Added configurable maximum document size (default 10 MiB) enforced before parsing.

### Fixed
- Namespace handling: now matches elements by local name (supports default xmlns, prefixed elements, single-quoted xmlns, xmlns order variations, child-level xmlns).
- Wrong or missing verb now fails clearly (BODStructureError / error JSON) instead of silently flattening the verb or dropping the noun.
- FastAPI endpoints return HTTP 400 (not 200) for parse/structure errors.
- Version strings aligned across pyproject.toml, package, API, README, and docs.
- sdist now includes tests/, tests/data/, docs/, and scripts/.

### Added
- Public exceptions: `BODParseError`, `BODStructureError`.
- Optional `raise_on_error` on `to_json` / `to_ndjson` (default remains return error JSON).
- CHANGELOG, SECURITY.md, CONTRIBUTING.md, CI workflow, Dependabot config.
- Test coverage for namespaces, repeating siblings, error paths, size limits, and API status codes.

### Changed
- Core dependency: `defusedxml`. No longer claims zero-dependency / pure stdlib.
- Documented that `to_json` returns only the first noun; `to_records` / `to_ndjson` return all.

## [2.3.0] - prior

- Version string alignment and README typo fix. Engine identical to 2.2.0.

## Earlier

- 2.1.1 / 2.1.2 / 2.2.0 shipped with mismatched `__version__` strings. Do not repeat.
