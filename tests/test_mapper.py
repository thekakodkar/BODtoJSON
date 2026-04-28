import unittest
import json
import sys
import os

# Align pathing for local testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from BODtoJSON import convert
from config import Config

class TestBODtoJSON(unittest.TestCase):
    def test_sync_purchase_order(self):
        result_json = convert(Config.INPUT_VAR, "Sync")
        data = json.loads(result_json)
        
        # ALIGNED KEY: Engine includes the Noun name (PurchaseOrder)
        expected_key = "PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text"
        
        # Verification
        self.assertEqual(
            data.get(expected_key), 
            "PSU000049", 
            f"Key mismatch. Available keys: {list(data.keys())}"
        )

if __name__ == "__main__":
    unittest.main()