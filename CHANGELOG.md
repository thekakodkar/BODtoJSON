# Changelog

## [2.4.0] - 2026-11-15

### Security
- Restored a **zero-runtime-dependency** core. XML is parsed with a stdlib-only hardened loader (`xml.parsers.expat` + `ElementTree.TreeBuilder`); `defusedxml` is no longer required.
- Any `DOCTYPE` or `ENTITY` declaration is rejected before parse (UTF-8/16/32 byte scan plus decoded-text scan), including external DTDs, UTF-16/32 encodings, and declarations hidden after comments.
- Expat handlers forbid DTD, entity declarations, and external entity references. Parameter-entity parsing is disabled. Reparse deferral is enabled when available.
- Added a configurable maximum element depth (default 256) on `BODConverter`.
- Removed the unsafe `xml.etree.ElementTree.fromstring` fallback that ran when `defusedxml` was missing in 2.3.1.

### Fixed
- Verb and `DataArea` lookups now match **direct children** only, so a nested element with the same local name as the verb can no longer raise a raw `ValueError`.
- FastAPI body-size limit (HTTP 413) now applies to every POST route, including `/project` and `/convert/json/wrapper`.
- Accept `bytes` as well as `str` in `to_json` / `to_ndjson` / `to_records` / `project` (including UTF-16/32 and BOM-encoded payloads).

### Changed
- Package version 2.4.0. `pip install BODtoJSON` installs no third-party runtime dependencies.
- Documentation updated for ION / air-gapped use and for the conservative DTD policy (literal `<!DOCTYPE` / `<!ENTITY` tokens in CDATA or comments are rejected).


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
