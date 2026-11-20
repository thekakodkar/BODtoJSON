# Changelog

## [Unreleased]

### Changed
- **License**: MIT with an attribution requirement (`LicenseRef-MIT-Attribution` in the package metadata). Any use, copy, or derivative, including generated Infor ION scripts, must keep the credit "Powered by BODtoJSON by Niraj Kakodkar (Bizzteq) – https://thekakodkar.github.io/BODtoJSON/". In an ION script, the header comment that names BODtoJSON and links to that page counts as the credit. Published versions up to and including 2.6.0 stay under plain MIT.
- The ION examples (`examples/ion_script.py`, README, docs) start with that header comment.

## [2.6.0] - 2026-11-20

### Added
- **One-call mapping to your own JSON shape**: `bod_to_json(xml, rules)` (JSON string), `bod_to_data(xml, rules)` (Python objects), and `Mapper(rules)` / `Mapper.from_file(path)` (compile once, then `.to_json` / `.to_data` / `.apply(record)`).
  - The rules are an **output template**:
    - plain strings are field paths, with a `_#text` fallback;
    - `"{A}_{B}"` / `{"template": ...}` strings;
    - literals and `{}` / `[{}]` pass through;
    - nested objects and lists;
    - `repeat` with `*` bound to the current line, relative paths, nested repeats relative to the line, single unindexed lines, and `where` filters;
    - `if` (including else-if lists), `case` (branch list or value map), `concat`, `coalesce`, `upper`/`lower`/`trim`, `number`, `replace`, `substr`, `literal`, and `path`/`default`.
  - One output object per noun (`single=True` returns the first). `missing=` sets the value for absent fields. Rules may be a dict, JSON text, or a file path.
  - Compact conditions `{"eq": ["Path", "value"]}` (and every other operator), alongside the `{"path", "op", "value"}` form.
  - Errors name the template location, for example `Rule at '$.purchaseOrderLines.repeat': ...`.
  - 2.5 flat rules are auto-detected and keep their behaviour. `kind=` forces either mode.
- Verb auto-detection: `bod_to_json(..., verb=None)`, `to_records(xml, None)`, `BODConverter.detect_verb()`, and an optional `--verb` in the CLI.
- CLI: `bodtojson to-json in.xml --rules template.json [--single] [--missing-empty]`.
- API: `POST /map`.
- `examples/ion_purchase_order_template.json`, `examples/ion_script.py`, and `tests/data/sync_PO_lines.xml` (a three-line order with coding lines).
- `tests/test_mapping.py`, which runs the user's ION template unchanged (330 tests in total).

### Changed
- The comparison logic in `transforms.py` is factored into `compare()` / `normalize_op()` and shared by both engines. There is no behaviour change.
- Version 2.6.0, still with zero runtime dependencies.

## [2.5.0] - 2026-11-20

### Added
- **Transformation rules** (`BODtoJSON.transforms`, `rules=` on `to_json`, `to_ndjson`, `to_records`, `project` and `BODConverter` methods). Rules are declarative JSON and are interpreted with no `eval`/`exec`:
  - values: `"$Path"` lookups (with an automatic `_#text` fallback), literals, `path`/`default`, `concat` (with `sep` and `skip_empty`), `template`, `coalesce`, `upper`/`lower`/`trim`, `replace`, `substr`, `number`;
  - conditionals: `if`/`then`/`else`, else-if chains, and `case`/`when`/`default` (map or `match` list, optional `ignore_case`);
  - conditions: `eq ne gt ge lt le in not_in contains not_contains starts_with ends_with exists missing empty not_empty`, combined with `all`/`any`/`not`;
  - `*` path segments run a rule once per repeated element (for example per `PurchaseOrderLine`);
  - `mode` (`merge` / `only`) and `drop` glob patterns;
  - validation when the rules are compiled, raising the new `BODTransformError`.
- Public helpers: `TransformRules`, `compile_rules`, `apply_rules`, `BODTransformError`.
- **JSON → BOD reverse conversion**: `json_to_bod()` and `BODConverter.from_json()`.
  - Accepts flattened records (the forward output), NDJSON, nested JSON, or a mix.
  - Rebuilds the root `<Verb><Noun>`, the Infor OAGIS namespace, `releaseID`/`versionID`, `ApplicationArea` (generated with `CreationDateTime` when absent), `DataArea/<Verb>` (optional `action_code`), and one noun per record.
  - Honours the `@attr`, `#text` and repeated-index key conventions, so `to_records(include_header=True)` round-trips.
  - Optional reverse rules (default mode `only`) map foreign JSON onto BOD paths.
  - Output is written by a stdlib serializer with explicit escaping. Names and XML 1.0 characters are validated, and size and depth caps apply.
- `to_ndjson(..., include_header=True)`.
- **CLI**: the `bodtojson` console script and `python -m BODtoJSON`, with `to-json` (`--format json|ndjson|records`, `--rules`, `--include-header`) and `to-bod` (`--noun`, `--rules`, `--action-code`, `--namespace`, `--root`, ...).
- **API**: `POST /transform`, `POST /convert/bod`, and optional `rules` on `POST /project`.
- `examples/` folder: forward rules, reverse rules, and a sample order JSON.
- Tests for rules, reverse conversion and round trips, the CLI, and the new API endpoints (224 tests in total). The core-only CI job now runs the rules, reverse and CLI suites without extras.

### Changed
- Version 2.5.0. There are still no runtime dependencies.
- `bod_xml` parameters are now annotated `Union[str, bytes]`. Bytes were already accepted.
- README, `docs/index.html`, and `scripts/inspect_payload.py` (new `transform` and `bod` modes) are updated. The Known Limitations section now describes reverse-conversion fidelity in place of "one-way only".

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
