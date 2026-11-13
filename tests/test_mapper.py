import json
import pytest
from BODtoJSON import to_json, to_ndjson, to_records, project, convert


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

    assert result_ndjson.count("\n") == 1
    assert " " not in result_ndjson.split(":")[0]

    data = json.loads(result_ndjson.strip())
    key = "PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text"
    assert data.get(key) == expected_id


def test_to_records_with_header(xml_loader):
    """Verifies native dict list extraction including Verb/ApplicationArea metadata."""
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    records = to_records(xml, "Sync", include_header=True)

    assert len(records) == 1
    assert records[0]["Sync_AccountingEntityID"] == "3555"
    assert records[0]["PurchaseOrder_PurchaseOrderHeader_DisplayID"] == "PSU000049"


def test_project_schema_mapping(xml_loader):
    """Verifies declarative schema projection with header placeholder interpolation."""
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    schema = {
        "externalSystemId": "company[{Sync_AccountingEntityID}];PO;{PurchaseOrder_PurchaseOrderHeader_DisplayID}",
        "currency": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID",
        "isActive": "true"
    }

    projected = project(xml, "Sync", schema=schema, include_header=True)
    assert len(projected) == 1
    assert projected[0] == {
        "externalSystemId": "company[3555];PO;PSU000049",
        "currency": "EUR",
        "isActive": True
    }


def test_legacy_convert_deprecation_warning(xml_loader):
    """Assures calling 'convert' still works and emits a DeprecationWarning."""
    xml = xml_loader.load("sync_PO_PSU000049.xml")

    with pytest.deprecated_call():
        result = convert(xml, "Sync")

    data = json.loads(result)
    assert "PurchaseOrder_PurchaseOrderHeader_DisplayID" in data