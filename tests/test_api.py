import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from BODtoJSON import __version__
from BODtoJSON.api import app

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


def test_api_root_version():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == __version__
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_api_ndjson_malformed_returns_400():
    response = client.post(
        "/convert/ndjson",
        content="not-xml",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_api_oversize_returns_413(monkeypatch):
    import BODtoJSON.api as api_mod

    monkeypatch.setattr(api_mod, "MAX_BODY_SIZE", 64)
    over = "Z" * 200
    r = client.post(
        "/convert/json?verb=Sync",
        content=over,
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 413

    r = client.post(
        "/project",
        json={"xml": over, "verb": "Sync", "schema_map": {"a": "b"}},
    )
    assert r.status_code == 413

    r = client.post(
        "/convert/json/wrapper",
        json={"xml": over, "verb": "Sync"},
    )
    assert r.status_code == 413


def test_api_unexpected_errors_return_500(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("BODtoJSON.api.to_json", boom)
    monkeypatch.setattr("BODtoJSON.api.to_ndjson", boom)
    monkeypatch.setattr("BODtoJSON.api.project", boom)
    monkeypatch.setattr("BODtoJSON.api.convert", boom)

    xml = "<SyncPO><DataArea><Sync/><PO/></DataArea></SyncPO>"
    assert client.post("/convert/json", content=xml, headers={"Content-Type": "text/plain"}).status_code == 500
    assert client.post("/convert/ndjson", content=xml, headers={"Content-Type": "text/plain"}).status_code == 500
    assert client.post("/project", json={"xml": xml, "verb": "Sync", "schema_map": {"a": "b"}}).status_code == 500
    assert client.post("/convert", content=xml, headers={"Content-Type": "text/plain"}).status_code == 500
    assert client.post("/convert/json/wrapper", json={"xml": xml, "verb": "Sync"}).status_code == 500


def test_legacy_convert_error_json_is_400(xml_loader):
    response = client.post(
        "/convert",
        content="not-xml",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"


# ---------------------------------------------------------------- 2.5.0
TRANSFORM_RULES = {
    "rules": {
        "orderRef": {"concat": ["PO-", "$PurchaseOrder_PurchaseOrderHeader_DisplayID"]},
        "currency": {
            "case": "$PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID",
            "when": {"EUR": "Euro"},
            "default": "Other",
        },
    },
    "mode": "only",
}


def test_api_transform(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    r = client.post("/transform", json={"xml": xml, "verb": "Sync", "rules": TRANSFORM_RULES})
    assert r.status_code == 200
    assert r.json() == [{"orderRef": "PO-PSU000049", "currency": "Euro"}]


def test_api_transform_bad_rules_400(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    r = client.post("/transform", json={"xml": xml, "rules": {"a": {"nope": 1}}})
    assert r.status_code == 400
    assert r.json()["status"] == "error"


def test_api_project_with_rules(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    r = client.post(
        "/project",
        json={"xml": xml, "schema_map": {"ref": "orderRef"}, "rules": TRANSFORM_RULES},
    )
    assert r.status_code == 200
    assert r.json() == [{"ref": "PO-PSU000049"}]


def test_api_convert_bod_round_trip(xml_loader):
    from BODtoJSON import to_records

    xml = xml_loader.load("sync_PO_PSU000049.xml")
    recs = to_records(xml, "Sync", include_header=True)
    r = client.post("/convert/bod", json={"data": recs, "verb": "Sync", "version_id": "2.14.x"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert to_records(r.text, "Sync", include_header=True) == recs


def test_api_convert_bod_options_and_errors():
    r = client.post(
        "/convert/bod",
        json={
            "data": {"PurchaseOrderHeader": {"DisplayID": "N1"}},
            "noun": "PurchaseOrder",
            "action_code": "Replace",
            "namespace": "",
            "release_id": "",
            "include_application_area": False,
            "pretty": False,
        },
    )
    assert r.status_code == 200
    assert r.text.startswith('<?xml version="1.0" encoding="UTF-8"?><SyncPurchaseOrder>')
    bad = client.post("/convert/bod", json={"data": {"Sync_TenantID": "x"}})
    assert bad.status_code == 400


def test_api_new_endpoints_500(monkeypatch, xml_loader):
    import BODtoJSON.api as api_mod

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(api_mod, "to_records", boom)
    monkeypatch.setattr(api_mod, "json_to_bod", boom)
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    assert client.post("/transform", json={"xml": xml, "rules": {}}).status_code == 500
    assert client.post("/convert/bod", json={"data": {}}).status_code == 500
