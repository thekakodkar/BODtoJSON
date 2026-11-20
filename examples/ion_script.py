"""Infor ION Scripting: map a SyncPurchaseOrder BOD to a target REST payload.

ION supplies ``input_var`` (the BOD XML) and reads ``output_var``.
RULES is the output template from examples/ion_purchase_order_template.json,
pasted inline because ION scripts usually cannot read files.
"""

from BODtoJSON import bod_to_json

RULES = {
    "externalSystemId": {"template": "{Sync_AccountingEntityID}_{PurchaseOrder_PurchaseOrderHeader_DisplayID}"},
    "isActive": True,
    "companyId": {"template": "company[{Sync_AccountingEntityID}]"},
    "amount": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount",
    "currencyCode": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID",
    "orderIdentifier": "PurchaseOrder_PurchaseOrderHeader_DisplayID",
    "registerDate": "PurchaseOrder_PurchaseOrderHeader_OrderDateTime",
    "supplier": "PurchaseOrder_PurchaseOrderHeader_SupplierParty_PartyIDs_ID",
    "externalSystemMetadata": [{}],
    "purchaseOrderLines": {
        "repeat": "PurchaseOrder_PurchaseOrderLine_*",
        "item": {
            "externalSystemId": {"template": "{Sync_AccountingEntityID}_{PurchaseOrder_PurchaseOrderHeader_DisplayID}_{PurchaseOrder_PurchaseOrderLine_*_LineNumber}"},
            "isActive": True,
            "amount": "PurchaseOrder_PurchaseOrderLine_*_ExtendedAmount",
            "lineNumber": "PurchaseOrder_PurchaseOrderLine_*_LineNumber",
            "quantity": "PurchaseOrder_PurchaseOrderLine_*_Quantity",
            "unit": "PurchaseOrder_PurchaseOrderLine_*_Quantity_@unitCode",
            "unitPrice": "PurchaseOrder_PurchaseOrderLine_*_UnitPrice_Amount",
            "codingLines": {"repeat": "CodingLine_*", "item": {}},
            "deliveryLines": [{"isActive": True, "externalSystemMetadata": [{}]}],
            "externalSystemMetadata": [{}],
        },
    },
    "purchaseOrderComments": [{}],
}

output_var = bod_to_json(input_var, rules=RULES)  # noqa: F821 - input_var is provided by ION
