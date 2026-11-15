import json
import pytest
from pathlib import Path

from BODtoJSON import (
    to_json,
    to_ndjson,
    to_records,
    project,
    convert,
    BODConverter,
    BODParseError,
    BODStructureError,
    __version__,
)


@pytest.mark.parametrize(
    "file_name, expected_id",
    [
        ("sync_PO_PSU000049.xml", "PSU000049"),
        ("sync_PO_PSU000050.xml", "PSU000050"),
    ],
)
def test_to_json_flattening(xml_loader, file_name, expected_id):
    xml = xml_loader.load(file_name)
    result_json = to_json(xml, "Sync")
    data = json.loads(result_json)
    key = "PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text"
    assert data.get(key) == expected_id


def test_to_ndjson_linearization(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    result_ndjson = to_ndjson(xml, "Sync")
    assert result_ndjson.count("\n") == 1
    data = json.loads(result_ndjson.strip())
    assert data.get("PurchaseOrder_PurchaseOrderHeader_DocumentID_ID_#text") == "PSU000049"


def test_to_records_with_header(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    records = to_records(xml, "Sync", include_header=True)
    assert len(records) == 1
    assert records[0]["Sync_AccountingEntityID"] == "3555"
    assert records[0]["PurchaseOrder_PurchaseOrderHeader_DisplayID"] == "PSU000049"


def test_project_schema_mapping(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    schema = {
        "externalSystemId": "company[{Sync_AccountingEntityID}];PO;{PurchaseOrder_PurchaseOrderHeader_DisplayID}",
        "currency": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID",
        "isActive": "true",
    }
    projected = project(xml, "Sync", schema=schema, include_header=True)
    assert projected[0]["externalSystemId"] == "company[3555];PO;PSU000049"
    assert projected[0]["currency"] == "EUR"
    assert projected[0]["isActive"] is True


def test_legacy_convert_deprecation_warning(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    with pytest.deprecated_call():
        result = convert(xml, "Sync")
    data = json.loads(result)
    assert "PurchaseOrder_PurchaseOrderHeader_DisplayID" in data


def test_repeating_siblings():
    xml = """
    <SyncPO xmlns="http://example.com">
      <DataArea>
        <Sync><AccountingEntityID>1</AccountingEntityID></Sync>
        <PO>
          <Line><ID>A</ID></Line>
          <Line><ID>B</ID></Line>
          <Line attr="x"><ID>C</ID></Line>
        </PO>
      </DataArea>
    </SyncPO>
    """
    data = json.loads(to_json(xml, "Sync"))
    assert "PO_Line_0_ID" in data or "PO_Line_0" in data or any("Line_0" in k for k in data)
    # Exact key shape may vary; at least the values appear
    assert any("A" in str(v) for v in data.values())
    assert any("B" in str(v) for v in data.values())


def test_namespace_variations():
    cases = [
        # default xmlns first
        '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><ID>B</ID></PO></DataArea></SyncPO>',
        # xsi before default
        '<SyncPO xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://ex.com"><DataArea><Sync/><PO><ID>B</ID></PO></DataArea></SyncPO>',
        # prefixed only
        '<oa:SyncPO xmlns:oa="http://ex.com"><oa:DataArea><oa:Sync/><oa:PO><oa:ID>B</oa:ID></oa:PO></oa:DataArea></oa:SyncPO>',
        # single quotes
        "<SyncPO xmlns='http://ex.com'><DataArea><Sync/><PO><ID>B</ID></PO></DataArea></SyncPO>",
    ]
    for xml in cases:
        data = json.loads(to_json(xml, "Sync"))
        assert any("B" in str(v) for v in data.values()), f"Failed for: {xml[:60]}"


def test_missing_dataarea():
    xml = "<root><other/></root>"
    with pytest.raises(BODStructureError):
        to_records(xml, "Sync")
    err = json.loads(to_json(xml, "Sync"))
    assert err["status"] == "error"


def test_wrong_verb():
    xml = """
    <SyncPO xmlns="http://ex.com">
      <DataArea>
        <Sync><AccountingEntityID>3555</AccountingEntityID></Sync>
        <PurchaseOrder><ID>PO1</ID></PurchaseOrder>
      </DataArea>
    </SyncPO>
    """
    err = json.loads(to_json(xml, "Process"))
    assert err["status"] == "error"
    with pytest.raises(BODStructureError):
        to_records(xml, "Process")


def test_multi_noun():
    xml = """
    <SyncPO xmlns="http://ex.com">
      <DataArea>
        <Sync/>
        <PO><ID>1</ID></PO>
        <PO><ID>2</ID></PO>
      </DataArea>
    </SyncPO>
    """
    records = to_records(xml, "Sync")
    assert len(records) == 2
    ndjson = to_ndjson(xml, "Sync")
    assert ndjson.count("\n") == 2
    first = json.loads(to_json(xml, "Sync"))
    assert any("1" in str(v) for v in first.values())


def test_unicode_and_bom():
    xml = '<?xml version="1.0"?><SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>Käyttöohje 测试 🚀</Note></PO></DataArea></SyncPO>'
    bom = "\ufeff" + xml
    data = json.loads(to_json(bom, "Sync"))
    assert any("Käyttöohje" in str(v) for v in data.values())


def test_empty_element():
    xml = '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Empty/></PO></DataArea></SyncPO>'
    data = json.loads(to_json(xml, "Sync"))
    # Empty element becomes null
    assert any(v is None for v in data.values()) or "Empty" in str(data)


def test_entity_expansion_rejected():
    # Billion-laughs style (small)
    xml = """<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
    ]>
    <lolz>&lol2;</lolz>
    """
    with pytest.raises(BODParseError):
        to_records(xml, "Sync")
    err = json.loads(to_json(xml, "Sync"))
    assert err["status"] == "error"
    # Must not expand into huge text; error should indicate entity rejection
    assert "EntitiesForbidden" in err.get("message", "") or "entity" in err.get("message", "").lower()


def test_oversize():
    conv = BODConverter(max_size=100)
    big = "x" * 200
    with pytest.raises(BODParseError):
        conv.to_records(big, "Sync")


def test_version_consistency():
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    text = pyproject.read_text()
    assert f'version = "{__version__}"' in text
    assert __version__ == "2.3.1"


def test_project_callable(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    schema = {"doubled": lambda rec: len(rec)}
    result = project(xml, "Sync", schema, include_header=False)
    assert isinstance(result[0]["doubled"], int)
