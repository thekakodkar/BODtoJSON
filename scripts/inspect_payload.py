import sys
import os
import json

current_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.insert(0, os.path.join(root_dir, 'src'))
sys.path.insert(0, os.path.join(root_dir, 'tests'))

try:
    from BODtoJSON import to_json, to_ndjson, project, convert
    from config import Config
except ImportError as e:
    print(f"CRITICAL: Resource mapping failed. {e}")
    sys.exit(1)


def run_business_validation(mode: str = "ndjson"):
    """
    Executes a transformation check to validate OAGIS-to-JSON flattening profiles.
    Supported modes: 'ndjson', 'json', 'project', 'legacy'
    """
    print("=" * 60)
    print(f"BODtoJSON v2.3.0 | Payload Validation Profile: [{mode.upper()}]")
    print("=" * 60)

    try:
        if mode == "project":
            sample_schema = {
                "externalSystemId": "company[{Sync_AccountingEntityID}];PO;{PurchaseOrder_PurchaseOrderHeader_DisplayID}",
                "amount": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_#text",
                "currency": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID",
                "isActive": True
            }
            projected = project(Config.INPUT_VAR, "Sync", schema=sample_schema, include_header=True)
            formatted = json.dumps(projected, indent=4)
            with open("output_preview.json", "w", encoding="utf-8") as f:
                f.write(formatted)
            print("STATUS: SUCCESS (Projected Schema)")
            print(formatted)
            return

        if mode == "ndjson":
            raw_output = to_ndjson(Config.INPUT_VAR, "Sync")
        elif mode == "json":
            raw_output = to_json(Config.INPUT_VAR, "Sync")
        else:
            raw_output = convert(Config.INPUT_VAR, "Sync")

        if '"status":"error"' in raw_output.replace(" ", ""):
            raise ValueError(raw_output)

        print("STATUS: SUCCESS")
        print("-" * 60)

        first_line = raw_output.split("\n")[0]
        preview_data = json.loads(first_line)

        print(f"TOTAL FLATTENED KEYS IN RECORD: {len(preview_data)}")
        print("CRITICAL DATA PREVIEW:")
        sample_keys = [
            "PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text",
            "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_#text",
            "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID"
        ]

        for key in sample_keys:
            value = preview_data.get(key, "NOT FOUND")
            print(f"  > {key:50} : {value}")

        print("-" * 60)

        if mode == "ndjson":
            with open("output_preview.json", "w", encoding="utf-8") as f:
                f.write(raw_output)
        else:
            with open("output_preview.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(preview_data, indent=4))

        print("AUDIT LOG: 'output_preview.json' has been generated for review.")

    except Exception as e:
        print("STATUS: FAILURE")
        print(f"ERROR DETAIL: {str(e)}")


if __name__ == "__main__":
    # Options: "ndjson", "json", "project", "legacy"
    run_business_validation(mode="ndjson")