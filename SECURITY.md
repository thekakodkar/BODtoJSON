# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.3.x   | :white_check_mark: |
| < 2.3.0 | :x:                |

## Reporting a Vulnerability

Please report security issues privately via GitHub Security Advisories or by contacting the maintainer.

**Do not** attach untrusted BOD/XML files to public issues.

## XML Parsing

All XML is parsed with [defusedxml](https://pypi.org/project/defusedxml/), which disables DTD processing, entity expansion, and external entity resolution. Billion-laughs and XXE payloads are rejected.

A maximum document size (default 10 MiB) is enforced before parsing.

The optional FastAPI layer is unauthenticated. Treat it as a trusted-network service or place it behind your own authentication.
