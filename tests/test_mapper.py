import json
import pytest
from BODtoJSON import to_json, to_ndjson, convert


@pytest.mark.parametrize(
    "file_name, expected_id",
    [
        ("sync_PO_PSU000049.xml", "PSU000049"),
        ("sync_PO_PSU000050.xml", "PSU000050"),
    ]
)
def test_to_json_flattening(xml_loader, file_name, expected_id):
    """Verifies standard structured JSON formatting maps correctly."""
    xml = xml_loader.load(file_name)

    result_json = to_json(xml, "Sync")
    data = json.loads(result_json)

    key = "PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text"
    assert data.get(key) == expected_id


@pytest.mark.parametrize(
    "file_name, expected_id",
    [
        ("sync_PO_PSU000049.xml", "PSU000049"),
    ]
)
def test_to_ndjson_linearization(xml_loader, file_name, expected_id):
    """Verifies strict compression and single-line execution constraints for NDJSON."""
    xml = xml_loader.load(file_name)

    result_ndjson = to_ndjson(xml, "Sync")
    
    # Operational Checks: No multi-line breaks allowed inside a single record
    assert result_ndjson.count("\n") == 1
    assert " " not in result_ndjson.split(":")[0]  # Verify dense spaces mapping

    data = json.loads(result_ndjson.strip())
    key = "PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text"
    assert data.get(key) == expected_id


def test_legacy_convert_deprecation_warning(xml_loader):
    """
    Regression Testing: Assures that calling the old 'convert' function
    still works but fires a deprecation alert to keep developers modern.
    """
    xml = xml_loader.load("sync_PO_PSU000049.xml")

    # This context manager passes only if a DeprecationWarning is successfully caught
    with pytest.deprecated_call():
        result = convert(xml, "Sync")
        
    data = json.loads(result)
    assert "PurchaseOrder_PurchaseOrderHeader_DisplayID" in data