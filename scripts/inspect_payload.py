import sys
import os
import json

# 1. Get the absolute path of the root directory (BODtoJSON)
current_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(current_dir, '..'))

# 2. Add 'src' and 'tests' to the search path
sys.path.insert(0, os.path.join(root_dir, 'src'))
sys.path.insert(0, os.path.join(root_dir, 'tests'))

# 3. Import directly from the folders we just added
try:
    from BODtoJSON import to_json, to_ndjson, convert
    from config import Config  
except ImportError as e:
    print(f"CRITICAL: Resource mapping failed. {e}")
    sys.exit(1)


def run_business_validation(mode: str = "ndjson"):
    """
    Executes a high-fidelity transformation check to validate 
    OAGIS-to-JSON flattening profiles.
    
    Supported modes: 'json', 'ndjson', 'legacy'
    """
    print("="*60)
    print(f"BODtoJSON v1.1.0 | Payload Validation Profile: [{mode.upper()}]")
    print("="*60)
    
    # 1. Execute transformation based on the target business profile
    if mode == "ndjson":
        raw_output = to_ndjson(Config.INPUT_VAR, "Sync")
    elif mode == "json":
        raw_output = to_json(Config.INPUT_VAR, "Sync")
    else:
        # Validates that your legacy production calls still execute gracefully
        raw_output = convert(Config.INPUT_VAR, "Sync")
    
    try:
        # Check for inline engine errors
        if '"status":"error"' in raw_output.replace(" ", ""):
            raise ValueError(raw_output)

        print(f"STATUS: SUCCESS")
        print("-" * 60)
        
        # Parse the first record line for terminal visualization/metrics
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
        
        # 2. Audit Log Generation
        # Write the raw output directly. to_ndjson is already flat and newline terminated.
        if mode == "ndjson":
            with open("output_preview.json", "w", encoding="utf-8") as f:
                f.write(raw_output)
        else:
            # If standard JSON, we can format it with an indent for human readability
            formatted_json = json.dumps(preview_data, indent=4)
            with open("output_preview.json", "w", encoding="utf-8") as f:
                f.write(formatted_json)
                
        print("AUDIT LOG: 'output_preview.json' has been generated for review.")
        
    except Exception as e:
        print(f"STATUS: FAILURE")
        print(f"ERROR DETAIL: {str(e)}")

if __name__ == "__main__":
    # Options: "ndjson" (strict single-line), "json" (standard), "legacy" (backward compatibility check)
    run_business_validation(mode="ndjson")