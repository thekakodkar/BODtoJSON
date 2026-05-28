import json
from fastapi.testclient import TestClient
from BODtoJSON.api import app

client = TestClient(app)


def test_api_convert_to_json(xml_loader):
    """Validates the modern structured JSON streaming path."""
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")

    # Pass the XML string directly as the raw request content
    response = client.post(
        "/convert/json?verb=Sync",
        content=xml_data,
        headers={"Content-Type": "text/plain"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    
    # Verify the flattened content was returned cleanly
    data = response.json()
    assert "PurchaseOrder_PurchaseOrderHeader_DisplayID" in data
    assert data["PurchaseOrder_PurchaseOrderHeader_DisplayID"] == "PSU000049"


def test_api_convert_to_ndjson(xml_loader):
    """Validates the modern linearized NDJSON streaming path."""
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")

    response = client.post(
        "/convert/ndjson?verb=Sync",
        content=xml_data,
        headers={"Content-Type": "text/plain"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"
    
    # NDJSON response returns raw text rows. Parse the first row to validate.
    raw_text = response.text
    assert raw_text.endswith("\n")  # Ensure strict NDJSON spacing compliance
    
    first_record = json.loads(raw_text.split("\n")[0])
    assert first_record["PurchaseOrder_PurchaseOrderHeader_DisplayID"] == "PSU000049"


def test_legacy_api_convert_fallback(xml_loader):
    """Validates that old integrations hitting /convert still work flawlessly."""
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")

    response = client.post(
        "/convert?verb=Sync",
        content=xml_data,
        headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 200