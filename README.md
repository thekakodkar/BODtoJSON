# BODtoJSON v1.0.0

**BODtoJSON** is an enterprise-grade Python library designed to transform complex Infor OAGIS (XML) Business Object Documents into modern, AI-ready flattened JSON structures. 

v1.0.0 represents a significant leap from the 0.0.x series, moving from a utility script to a stable, commercialized data asset.

---

## 🚀 What’s New in v1.0.0 (vs. v0.0.7)

The transition from v0.0.7 to v1.0.0 is more than a version bump; it is a complete architectural refactor:

* **`src/` Layout Adoption:** Migrated from a flat directory to the professional `src/` layout. 
* **Strategic Verb Stripping:** Unlike v0.0.7, which often included administrative noise, v1.0.0 intelligently isolates the **Noun** (e.g., `PurchaseOrder`) and removes the **Verb** (e.g., `Sync`). This creates a cleaner dataset for LLM ingestion.
* **Defensive XML Engine:** * **Namespace Neutralization:** v1.0.0 uses dynamic regex to strip primary namespaces automatically.
    * **BOM Handling:** Added support for UTF-8 Byte Order Marks to prevent "Invalid Token" errors common in ERP exports.
* **Consolidated API:** The interface has been simplified. You no longer need to navigate deep submodules; simply use `from BODtoJSON import convert`.

---

## 📈 Why it is Better & Improved

| Feature | Legacy (v0.0.7) | **Production (v1.0.0)** |
| :--- | :--- | :--- |
| **Data Integrity** | Basic key-value mapping | **Preserves Attributes (`_@`) and Values (`_#text`)** |
| **AI Readiness** | Nested dictionaries (hard to index) | **Fully Flattened (Perfect for Vector DBs)** |
| **Stability** | Prone to XML namespace errors | **Resilient to OAGIS schema variations** |
| **Deployment** | Manual script copying | **Standardized Wheel/Source distribution** |

---

## 🛠️ Installation

```bash
pip install BODtoJSON
```

---

## 📂 Project Structure

```text
BODtoJSON/
├── src/
│   └── BODtoJSON/
│       ├── __init__.py      # Version & API exposure
│       └── mapper.py        # Core Transformation Engine
├── tests/
│   ├── config.py            # OAGIS XML Test Samples
│   └── test_mapper.py       # Automated Unit Tests (unittest)
├── scripts/
│   └── inspect_payload.py   # Manual Business Validation Utility
├── pyproject.toml           # Modern Build Configuration
└── README.md
```

---

## 🧪 Validation & Testing

### 1. Automated Testing (QA)
To run the standardized test suite and verify engine logic:
```powershell
python -m unittest discover tests
```

### 2. Manual Payload Inspection (UAT)
To verify the commercial value of the output and inspect the flattened JSON:
```powershell
python scripts/inspect_payload.py
```
This script generates an `inspection_result.json` in the root directory for side-by-side audit with the original XML.

---

## 💻 Code Example

```python
from BODtoJSON import convert

# Sample OAGIS XML
xml_input = """<SyncPurchaseOrder>...</SyncPurchaseOrder>"""

# High-fidelity conversion
# Strips 'Sync' verb, flattens 'PurchaseOrder' noun
flattened_json = convert(xml_input, verb="Sync")

print(flattened_json)
```

---

## 🤝 Commercial Value
By normalizing complex ERP structures into flat, labeled JSON, **BODtoJSON** reduces the engineering overhead of AI data preparation by up to 90%. It is built to be a stable foundation for forward-thinking AI strategies and automated business intelligence.

**Author:** Niraj Kakodkar  
**License:** MIT