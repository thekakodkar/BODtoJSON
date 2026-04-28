import os

class Config:
    """Enterprise OAGIS Test Data Provider."""
    
    # Raw XML string for quick testing
    INPUT_VAR = r"""<?xml version="1.0"?><SyncPurchaseOrder xmlns="http://schema.infor.com/InforOAGIS/2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schema.infor.com/InforOAGIS/2 http://schema.infor.com/2.14.x/InforOAGIS/BODs/SyncPurchaseOrder.xsd" xmlns:xsd="http://www.w3.org/2001/XMLSchema" releaseID="9.2" versionID="2.14.x"><ApplicationArea><Sender><LogicalID>lid://infor.ln.ln01/3555</LogicalID><ComponentID>erp</ComponentID><ConfirmationCode>OnError</ConfirmationCode></Sender><CreationDateTime>2020-06-18T09:41:56Z</CreationDateTime><BODID>infor-nid:TEST_TST:3555:S_350:PSU000049:?PurchaseOrder&amp;verb=Sync</BODID></ApplicationArea><DataArea><Sync><TenantID>TEST_TST</TenantID><AccountingEntityID>3555</AccountingEntityID><LocationID>S_350</LocationID><ActionCriteria><ActionExpression actionCode="Add"/></ActionCriteria></Sync><PurchaseOrder><PurchaseOrderHeader><DocumentID><ID accountingEntity="3555" location="S_350" lid="lid://infor.ln.ln01/3555" variationID="5">PSU000049</ID></DocumentID><DisplayID>PSU000049</DisplayID><Note type="Header">Subcontracting additions</Note><ExtendedAmount currencyID="EUR">2500</ExtendedAmount></PurchaseOrderHeader></PurchaseOrder></DataArea></SyncPurchaseOrder>""".strip()

    @staticmethod
    def get_xml_from_file(file_path: str) -> str:
        """Utility to read actual .xml files from disk."""
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return ""