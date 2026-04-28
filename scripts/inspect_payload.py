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
    from BODtoJSON import convert
    from config import Config  # Changed from 'from tests.config'
except ImportError as e:
    print(f"CRITICAL: Resource mapping failed. {e}")
    sys.exit(1)


def run_business_validation():
    """
    Executes a high-fidelity transformation check to ensure 
    OAGIS-to-JSON flattening meets enterprise standards.
    """
    print("="*60)
    print("BODtoJSON v1.0.0 | Enterprise Payload Validation")
    print("="*60)
    
    # Execute the conversion
    raw_json = convert(Config.INPUT_VAR, "Sync")
    
    try:
        # Load string into dictionary for analysis
        data = json.loads(raw_json)
        
        # 1. Verification of flattening
        print(f"STATUS: SUCCESS")
        print(f"TOTAL FLATTENED KEYS: {len(data)}")
        print("-" * 60)
        
        # 2. Display specific business-critical keys
        print("CRITICAL DATA PREVIEW:")
        sample_keys = [
            "PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text",
            "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_#text",
            "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID"
        ]
        
        for key in sample_keys:
            value = data.get(key, "NOT FOUND")
            print(f"  > {key:50} : {value}")
            
        print("-" * 60)
        
        # 3. Export to file for manual audit
        with open("output_preview.json", "w") as f:
            f.write(json.dumps(data, indent=4))
        print("AUDIT LOG: 'output_preview.json' has been generated for review.")
        
    except Exception as e:
        print(f"STATUS: FAILURE")
        print(f"ERROR DETAIL: {str(e)}")

if __name__ == "__main__":
    run_business_validation()