# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.5.x   | :white_check_mark: |
| 2.4.x   | :white_check_mark: |
| 2.3.x   | :white_check_mark: |
| < 2.3.0 | :x:                |

## Reporting a Vulnerability

Please report security issues privately via GitHub Security Advisories or by contacting the maintainer.

**Do not** attach untrusted BOD/XML files to public issues.

## XML Parsing

The core library has **no third-party runtime dependencies**. XML is parsed with a stdlib-only hardened loader (`xml.parsers.expat` + `xml.etree.ElementTree.TreeBuilder`):

- Any `DOCTYPE` or `ENTITY` declaration is rejected before parse (byte scan in UTF-8/16/32 plus a decoded-text scan). This is the portable guarantee on older expat builds (< 2.4.1) that lack built-in billion-laughs protection.
- Expat handlers also forbid DTD, entity declarations, and external entity references. Parameter-entity parsing is disabled. Reparse deferral is enabled when the interpreter exposes it.
- A maximum document size (default 10 MiB) and a maximum element depth (default 256) are enforced.

Billion-laughs, quadratic entity blowup, XXE, and external DTD payloads are rejected. Documents whose text, comments, or CDATA contain the literal tokens `<!DOCTYPE` or `<!ENTITY` are also rejected — Infor OAGIS BODs do not need DTDs.

Version 2.3.1 used [defusedxml](https://pypi.org/project/defusedxml/) as a core dependency. From 2.4.0 that dependency is no longer required.

## Transformation Rules (2.5.0+)

Rules are declarative JSON, validated when they are compiled and run by a small interpreter in `transforms.py`. There is no `eval`, `exec`, `compile`, attribute access, import, or regular expression built from rule text, so a rules file cannot run code. Validation rejects unknown keys and operators and caps nesting at 64 levels and the rule count at 10,000. Invalid rules raise `BODTransformError`.

## JSON → BOD (2.5.0+)

`json_to_bod` writes XML with its own serializer and explicit escaping (`&`, `<`, `>`, quotes, CR/LF/TAB in attributes). Element and attribute names are checked against XML name rules, and characters that XML 1.0 does not allow are rejected. JSON input is subject to the same default 10 MiB size cap and 256-level depth cap. No XML parser is used, and DTDs or entities are never emitted.

The optional FastAPI layer (`BODtoJSON[api]`) is unauthenticated. Treat it as a trusted-network service or place it behind your own authentication, and cap request size at the reverse proxy.
