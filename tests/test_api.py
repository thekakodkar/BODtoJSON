import json
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from BODtoJSON.api import app
from BODtoJSON import __version__

client = TestClient(app)


def test_api_convert_to_json(xml_loader):
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")
    response = client.post(
        "/convert/json?verb=Sync",
        content=xml_data,
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["PurchaseOrder_PurchaseOrderHeader_DisplayID"] == "PSU000049"


def test_api_convert_to_ndjson(xml_loader):
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")
    response = client.post(
        "/convert/ndjson?verb=Sync",
        content=xml_data,
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 200


def test_api_malformed_xml_returns_400():
    response = client.post(
        "/convert/json",
        content="not-xml",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"


def test_api_project_bad_xml_returns_400():
    response = client.post(
        "/project",
        json={"xml": "not-xml", "verb": "Sync", "schema_map": {"a": "b"}},
    )
    assert response.status_code == 400


def test_api_legacy_convert(xml_loader):
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")
    response = client.post(
        "/convert?verb=Sync",
        content=xml_data,
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 200


def test_api_legacy_wrapper(xml_loader):
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")
    response = client.post(
        "/convert/json/wrapper",
        json={"xml": xml_data, "verb": "Sync"},
    )
    assert response.status_code == 200


def test_api_project_happy(xml_loader):
    xml_data = xml_loader.load("sync_PO_PSU000049.xml")
    response = client.post(
        "/project",
        json={
            "xml": xml_data,
            "verb": "Sync",
            "schema_map": {"id": "PurchaseOrder_PurchaseOrderHeader_DisplayID"},
        },
    )
    assert response.status_code == 200
