# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
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

The optional FastAPI layer (`BODtoJSON[api]`) is unauthenticated. Treat it as a trusted-network service or place it behind your own authentication, and cap request size at the reverse proxy.
