# BODtoJSON v2.0.0

**BODtoJSON** is a zero-dependency, enterprise-grade Python data liquidity engine designed to transform complex Infor OAGIS (XML) Business Object Documents into modern, AI-ready flattened JSON and NDJSON structures.

<center><img width="769" height="336" alt="BOD2JSon" src="https://github.com/user-attachments/assets/0b089179-f137-4d56-b717-85cffb20d622" /></center>

v2.0.0 marks a major architectural milestone: eliminating all external core dependencies, introducing native single-pass ElementTree traversal, and establishing a dual-pipeline streaming standard for Data Lakehouses and Vector Databases.

---

## 🚀 What’s New in v2.0.0 (vs. v1.0.0)

* **Zero-Dependency Core Engine:** Removed `xmltodict` in favor of a single-pass recursive traversal built purely on Python’s native `xml.etree.ElementTree`. This eliminates external supply-chain risks, shrinks deployment footprints for air-gapped or serverless environments, and halves intermediate memory allocations.
* **Explicit Dual-Pipeline Architecture:** Replaced parameter-driven routing with dedicated top-level API methods—`to_json` and `to_ndjson`—improving interface predictability and self-documentation.
* **Strict NDJSON Linearization:** Features compact serialization via `separators=(',', ':')` and forced line termination (`\n`). Multi-noun batch payloads inside `DataArea` are automatically unpacked and emitted as individual, single-line text records.
* **Enterprise REST API Tier (`api.py`):** Added an optional, high-performance FastAPI microservice layer featuring zero-overhead streaming using raw `Response` classes, eliminating middleware double-serialization bottlenecks.
* **Pytest Suite:** Standardized automated quality assurance on **`pytest`**, including regression assertions for deprecation warnings.

---

## 📈 Why it is Better & Improved

| Feature | Production (v1.0.0) | **Streaming Engine (v1.5.0)** |
| :--- | :--- | :--- |
| **Data Formats** | Standard Structured JSON string | **Dual-Engine: Standard JSON & Strict Single-Line NDJSON** |
| **API Interface** | Single `convert()` entry point | **Explicit `to_json()` and `to_ndjson()` methods** |
| **Ingestion Target** | Application memory / NoSQL DBs | **Data Lakehouses (Snowflake/Databricks) & Vector DBs (RAG)** |
| **System Delivery** | Library imports only | **Library + High-Performance FastAPI Ingestion Tier** |
| **Regression Safety**| Basic structural testing | **Deprecation warning validation via Pytest** |

---

## 🛠️ Installation

```bash
pip install BODtoJSON
```

## 📂 Project Structure

```text
BODtoJSON/
├── src/
│   └── BODtoJSON/
│       ├── __init__.py      # Universal API exposure & versioning
│       ├── mapper.py        # Dual-Pipeline Transformation Engine
│       └── api.py           # FastAPI Microservice Ingestion Layer
├── tests/
│   ├── data/                # Raw OAGIS XML Test Datasets (.xml)
│   ├── config.py            # Global Test Environments Data Configuration
│   ├── conftest.py          # Pytest Dataset Loader Fixtures
│   ├── test_mapper.py       # Core Engine Unit Tests & Deprecation Validation
│   └── test_api.py          # API Performance Endpoint Verification
├── scripts/
│   └── inspect_payload.py   # Multi-Profile Business Validation Utility
├── pyproject.toml           # Modern Build and Pytest Configurations
└── README.md
```

---

## 🧪 Validation & Testing

### 1. Automated Testing (QA)
To run the standardized test suite and verify engine logic:
```powershell
python -m pytest -v -p no:cacheprovider
```
### 2. Manual Payload Inspection (UAT)
To verify the commercial value of the output and inspect the flattened JSON:
```powershell
python scripts/inspect_payload.py
```

This script generates an `output_preview.json` in the root directory for side-by-side audit with the original XML.
Note: Toggle the mode parameter within inspect_payload.py between "ndjson", "json", and "legacy" to evaluate various system outputs directly in output_preview.json.

---
## 💻 Code Example
1. Modern Pipeline: Newline Delimited JSON (NDJSON)
Optimized for Data Lakehouses (Snowflake/Databricks) and Vector Database ingestion.

```python
from BODtoJSON import to_ndjson

xml_input = """<SyncPurchaseOrder>...</SyncPurchaseOrder>"""

# Returns a dense, single-line string with zero internal spaces, terminated by a clean \n
linearized_ndjson = to_ndjson(xml_input, verb="Sync")

```
2. Modern Pipeline: Standard Flattened JSON
Optimized for application-level consumption and quick document-store indexing.
```python
from BODtoJSON import to_json

xml_input = """<SyncPurchaseOrder>...</SyncPurchaseOrder>"""

# Returns standard, single flat JSON string
flattened_json = to_json(xml_input, verb="Sync")
```

3. Legacy Pipeline: Backward-Compatible Conversion
Maintained to ensure active production systems do not break during upgrades.
```python
from BODtoJSON import convert

xml_input = """<SyncPurchaseOrder>...</SyncPurchaseOrder>"""

# WARNING: This method is deprecated and will be removed in v2.0.0.
# It internally routes to to_json() but fires a DeprecationWarning log.
legacy_json = convert(xml_input, verb="Sync")
```
4. Running the Enterprise API Tier
Launch your processing microservice engine locally:
```bash
uvicorn BODtoJSON.api:app --reload

```
Navigate your browser to http://127.0.0.1:8000/docs to interact with the visual Swagger UI. Use /convert/json or /convert/ndjson to execute on-demand pipeline testing.

---

## 🤝 Commercial Value
By providing native, low-latency transformations for both document-level applications and streaming data pipelines, **BODtoJSON** v1.5.0 reduces cloud compute and token serialization costs by up to 90%. It acts as an optimized, zero-friction interface between legacy ERP architectures (Infor LN/M3) and modern enterprise data lakes or generative AI strategies.
**Author:** Niraj Kakodkar  
**License:** MIT
