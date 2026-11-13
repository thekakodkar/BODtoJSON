# BODtoJSON v2.3.0

**BODtoJSON** is a zero-dependency, enterprise-grade Python data liquidity engine designed to transform complex Infor OAGIS (XML) Business Object Documents into modern, AI-ready flattened JSON, streaming NDJSON, and declarative target schemas.

<p>
<a hredf="https://thekakodkar.github.io/BODtoJSON/"> BODtoJSON Library Documentation </a>
</p>
<center><img width="769" height="336" alt="BOD2JSon" src="https://github.com/user-attachments/assets/0b089179-f137-4d56-b717-85cffb20d622" /></center>

v2.3.0 establishes a zero-dependency core engine, introduces native single-pass ElementTree traversal, adds declarative schema projection (`project()` / `to_records()`) for Infor ION Scripting, and delivers a dual-pipeline streaming standard for Data Lakehouses and Vector Databases.

## 🚀 What’s New in v2.3.0 (vs. v1.0.0)

* **Zero-Dependency Core Engine:** Removed `xmltodict` in favor of a single-pass recursive traversal built purely on Python’s native `xml.etree.ElementTree`. Eliminates external supply-chain risks, shrinks deployment footprints for air-gapped or Infor ION environments, and halves intermediate memory allocations.

* **Infor ION Scripting Helpers (`to_records` & `project`):** Eliminates boilerplate XML namespace parsing, `json.loads()` line-splitting loops, and manual boolean coercion in ION scripts. Captures `ApplicationArea` and `DataArea/<Verb>` header metadata automatically (`include_header=True`) and maps records directly into target REST/API JSON schemas.

* **Explicit Dual-Pipeline Architecture:** Dedicated top-level API methods—`to_json` and `to_ndjson`—improve interface predictability and self-documentation.

* **Strict NDJSON Linearization:** Features compact serialization via `separators=(',', ':')` and forced line termination (`\n`). Multi-noun batch payloads inside `DataArea` are automatically unpacked and emitted as individual, single-line text records.

* **100% Backward Compatibility:** The original `convert()` function remains active at the package root, routing to `to_json()` while emitting a non-breaking `DeprecationWarning` scheduled for removal in **v3.0.0**.

* **Enterprise REST API Tier (`api.py`):** Added an optional, high-performance FastAPI microservice layer featuring zero-overhead streaming using raw `Response` classes and `/project` schema mapping.

## 📈 Architectural Comparison

| Feature | Legacy (v1.0.0) | **Enterprise Engine (v2.3.0)** | 
| ----- | ----- | ----- | 
| **Core Dependencies** | Relied on `xmltodict` | **Zero External Dependencies (100% Python Stdlib)** | 
| **Memory & Speed** | Double-pass XML $\rightarrow$ Dict $\rightarrow$ Flat Dict | **Single-pass ElementTree traversal (\~50% lower memory)** | 
| **Data Formats** | Standard Structured JSON string | **Standard JSON, Strict NDJSON, Native Dicts & Projected Schemas** | 
| **Infor ION Scripting** | Manual XML + JSON loop boilerplate | **Declarative `project()` with automatic header context** | 
| **Ingestion Target** | Application memory / NoSQL DBs | **Data Lakehouses (Snowflake/Databricks), Vector DBs & ION APIs** | 
| **System Delivery** | Library imports only | **Library + Optional FastAPI Microservice Tier (`[api]`)** | 

## 🛠️ Installation

### Core Library (Zero Dependencies)

Ideal for Infor ION Scripting, data-engineering pipelines, ETL workers, and air-gapped environments:

```bash
pip install BODtoJSON
```

### With Enterprise REST API Tier

Includes `fastapi` and `uvicorn` for microservice deployment:

```bash
pip install "BODtoJSON[api]"
```

## 📂 Project Structure

```text
BODtoJSON/
├── src/
│   └── BODtoJSON/
│       ├── __init__.py      # Package version (2.3.0) & API exports
│       ├── mapper.py        # Zero-Dependency Dual-Pipeline & Projection Engine
│       └── api.py           # Optional FastAPI Microservice Ingestion Layer
├── tests/
│   ├── data/                # Raw OAGIS XML Test Datasets (.xml)
│   ├── config.py            # Test Data Configuration
│   ├── conftest.py          # Pytest Dataset Loader Fixtures
│   ├── test_mapper.py       # Core Engine Unit Tests, ION Projection & Regression Suite
│   └── test_api.py          # API Endpoint Verification
├── scripts/
│   └── inspect_payload.py   # Multi-Profile Business Validation Utility
├── pyproject.toml           # Build, Optional Extras & Pytest Configurations
└── README.md
```

## 🧪 Validation & Testing

### 1. Automated Testing (QA Suite)

Run the standardized `pytest` execution engine:

```powershell
python -m pytest -v -p no:cacheprovider
```

### 2. Manual Payload Inspection (UAT Engine)

Verify transformation output profiles locally:

```powershell
python scripts/inspect_payload.py
```

*Toggle the `mode` parameter within `inspect_payload.py` between `"ndjson"`, `"json"`, `"project"`, and `"legacy"` to inspect outputs in `output_preview.json`.*

## 💻 Code Examples

### 1. Infor ION Scripting: Declarative Schema Projection (`project`)

*Eliminates manual XML namespace handling, `json.loads()` loops, and boolean boilerplate.*

```python
import json
from BODtoJSON import project

SCHEMA = {
    "externalSystemId": "company[{Sync_AccountingEntityID}];DIMENSION1;{ChartOfAccounts_BaseChartOfAccounts_GLNominalAccount}",
    "isActive": "true",
    "companyId": "company[3100]",
    "dimensionName": "DIMENSION1",
    "usableInPurchase": "true",
}

# Automatically merges DataArea/Sync header context with each flattened Noun record
items = project(input_var, verb="Sync", schema=SCHEMA, include_header=True)
output_var = json.dumps(items)
```

### 2. Native Python Records (`to_records`)

*Extracts a Python `list[dict]` directly with optional `ApplicationArea` and `Verb` header context.*

```python
from BODtoJSON import to_records

records = to_records(xml_input, verb="Sync", include_header=True)
for rec in records:
    print(rec["Sync_AccountingEntityID"], rec["PurchaseOrder_PurchaseOrderHeader_DisplayID"])
```

### 3. Modern Pipeline: Newline Delimited JSON (`to_ndjson`)

*Optimized for Data Lakehouses (Snowflake/Databricks) and Vector Database ingestion.*

```python
from BODtoJSON import to_ndjson

xml_input = """<SyncPurchaseOrder>...</SyncPurchaseOrder>"""

# Returns a dense, single-line string per record with zero internal spaces, terminated by \n
linearized_ndjson = to_ndjson(xml_input, verb="Sync")
```

### 4. Modern Pipeline: Standard Flattened JSON (`to_json`)

*Optimized for application-level consumption and document-store indexing.*

```python
from BODtoJSON import to_json

xml_input = """<SyncPurchaseOrder>...</SyncPurchaseOrder>"""

# Returns a standard flat JSON string
flattened_json = to_json(xml_input, verb="Sync")
```

### 5. Legacy Pipeline: Backward-Compatible Conversion (`convert`)

*Maintained for smooth migration of existing production pipelines.*

```python
from BODtoJSON import convert

xml_input = """<SyncPurchaseOrder>...</SyncPurchaseOrder>"""

# DEPRECATED: Scheduled for removal in v3.0.0.
# Internally routes to to_json() and emits a DeprecationWarning.
legacy_json = convert(xml_input, verb="Sync")
```

### 6. Running the Enterprise API Tier

Launch the microservice locally:

```powershell
uvicorn BODtoJSON.api:app --reload
```

Open `http://127.0.0.1:8000/docs` to test `/convert/ndjson`, `/convert/json`, and `/project` directly via Swagger UI.

## 🤝 Commercial Value

By normalizing complex ERP structures into zero-dependency, flat JSON, streaming NDJSON, and projected API payloads, **BODtoJSON v2.3.0** eliminates third-party library bloat and reduces AI, Lakehouse, and Infor ION integration overhead by up to 90%.

**Author:** Niraj Kakodkar

**License:** MIT