import json
from pathlib import Path

import pytest

from BODtoJSON import (
    BODConverter,
    BODParseError,
    BODStructureError,
    __version__,
    convert,
    project,
    to_json,
    to_ndjson,
    to_records,
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
    assert data["PO_Line_0_ID"] == "A"
    assert data["PO_Line_1_ID"] == "B"
    assert data["PO_Line_2_@attr"] == "x"
    assert data["PO_Line_2_ID"] == "C"


def test_namespace_variations():
    cases = {
        "default_first": (
            '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><ID>A</ID></PO></DataArea></SyncPO>',
            "A",
        ),
        "xsi_first": (
            '<SyncPO xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://ex.com"><DataArea><Sync/><PO><ID>B</ID></PO></DataArea></SyncPO>',
            "B",
        ),
        "prefixed": (
            '<oa:SyncPO xmlns:oa="http://ex.com"><oa:DataArea><oa:Sync/><oa:PO><oa:ID>C</oa:ID></oa:PO></oa:DataArea></oa:SyncPO>',
            "C",
        ),
        "single_quotes": (
            "<SyncPO xmlns='http://ex.com'><DataArea><Sync/><PO><ID>D</ID></PO></DataArea></SyncPO>",
            "D",
        ),
        "child_xmlns": (
            '<SyncPO><DataArea xmlns="http://ex.com"><Sync/><PO><ID>E</ID></PO></DataArea></SyncPO>',
            "E",
        ),
        "two_xmlns": (
            '<SyncPO xmlns="http://root"><DataArea xmlns="http://ex.com"><Sync/><PO><ID>F</ID></PO></DataArea></SyncPO>',
            "F",
        ),
    }
    for name, (xml, expected) in cases.items():
        data = json.loads(to_json(xml, "Sync"))
        assert data.get("status") != "error", f"{name}: {data}"
        assert data.get("PO_ID") == expected, f"{name}: {data}"


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
    as_bytes = xml.encode("utf-8")
    data_b = json.loads(to_json(as_bytes, "Sync"))
    assert any("Käyttöohje" in str(v) for v in data_b.values())
    as_utf16 = xml.encode("utf-16")
    data_16 = json.loads(to_json(as_utf16, "Sync"))
    assert any("Käyttöohje" in str(v) for v in data_16.values())


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


def test_zero_runtime_requires():
    import importlib.metadata as metadata

    reqs = metadata.requires("BODtoJSON") or []
    # extras are allowed; core (no extra marker) must be empty
    core = [r for r in reqs if "extra ==" not in r]
    assert core == [], core


def test_source_has_no_unsafe_parser():
    src = Path(__file__).parent.parent / "src" / "BODtoJSON"
    tokens = (
        "import defusedxml",
        "from defusedxml",
        "ElementTree import fromstring",
        "ET.fromstring(",
        "ElementTree.fromstring(",
    )
    for path in src.glob("*.py"):
        text = path.read_text()
        for token in tokens:
            assert token not in text, f"{path.name} contains {token!r}"


def test_nested_verb_name_is_structure_error():
    """A Sync element only inside the noun must not raise a raw ValueError."""
    xml = """
    <SyncPO xmlns="http://ex.com">
      <DataArea>
        <Process/>
        <PO><Sync>inner</Sync><ID>Z</ID></PO>
      </DataArea>
    </SyncPO>
    """
    err = json.loads(to_json(xml, "Sync"))
    assert err["status"] == "error"
    with pytest.raises(BODStructureError):
        to_records(xml, "Sync")
    with pytest.raises(BODParseError):
        to_json("not-xml", "Sync", raise_on_error=True)


def test_max_depth():
    deep = "<L>leaf</L>"
    for _ in range(30):
        deep = f"<N>{deep}</N>"
    xml = f'<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO>{deep}</PO></DataArea></SyncPO>'
    conv = BODConverter(max_depth=10)
    with pytest.raises(BODParseError):
        conv.to_records(xml, "Sync")
    err = json.loads(conv.to_json(xml, "Sync"))
    assert err["status"] == "error"


def test_external_dtd_and_xxe_rejected_via_library():
    secret = Path("/tmp/bodtojson-2.4.0-lib-secret.txt")
    secret.write_text("SECRET_SHOULD_NOT_LEAK\n", encoding="utf-8")
    xxe = f"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO [ <!ENTITY xxe SYSTEM "file://{secret}"> ]>
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>&xxe;</Note></PO></DataArea></SyncPO>"""
    out = to_json(xxe, "Sync")
    assert "SECRET_SHOULD_NOT_LEAK" not in out
    assert json.loads(out)["status"] == "error"
    dtd = f"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO SYSTEM "file://{secret}">
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>ok</Note></PO></DataArea></SyncPO>"""
    out = to_json(dtd, "Sync")
    assert "SECRET_SHOULD_NOT_LEAK" not in out
    assert json.loads(out)["status"] == "error"


def test_output_parity_with_2_3_1():
    """Flattened output on samples and the namespace matrix must match published 2.3.1."""
    baseline_dir = Path(__file__).parent / "data" / "baselines_2_3_1"
    cases = {
        "sync_PO_PSU000049": (Path(__file__).parent / "data" / "sync_PO_PSU000049.xml").read_text(),
        "sync_PO_PSU000050": (Path(__file__).parent / "data" / "sync_PO_PSU000050.xml").read_text(),
        "ns_default_xmlns_first": '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><ID>A</ID></PO></DataArea></SyncPO>',
        "ns_xsi_first": '<SyncPO xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://ex.com"><DataArea><Sync/><PO><ID>B</ID></PO></DataArea></SyncPO>',
        "ns_prefixed": '<oa:SyncPO xmlns:oa="http://ex.com"><oa:DataArea><oa:Sync/><oa:PO><oa:ID>C</oa:ID></oa:PO></oa:DataArea></oa:SyncPO>',
        "ns_single_quotes": "<SyncPO xmlns='http://ex.com'><DataArea><Sync/><PO><ID>D</ID></PO></DataArea></SyncPO>",
        "ns_child_xmlns": '<SyncPO><DataArea xmlns="http://ex.com"><Sync/><PO><ID>E</ID></PO></DataArea></SyncPO>',
        "ns_two_xmlns": '<SyncPO xmlns="http://root"><DataArea xmlns="http://ex.com"><Sync/><PO><ID>F</ID></PO></DataArea></SyncPO>',
    }
    for name, xml in cases.items():
        expected = json.loads((baseline_dir / f"{name}.json").read_text())
        actual = {
            "to_json": json.loads(to_json(xml, "Sync")),
            "to_ndjson": [json.loads(line) for line in to_ndjson(xml, "Sync").splitlines() if line],
            "to_records_header": to_records(xml, "Sync", include_header=True),
        }
        assert actual == expected, name


def test_project_callable(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    schema = {"doubled": lambda rec: len(rec)}
    result = project(xml, "Sync", schema, include_header=False)
    assert isinstance(result[0]["doubled"], int)


def test_find_helpers_and_root_dataarea():
    conv = BODConverter()
    assert conv._find_direct_local(None, "DataArea") is None
    assert conv._find_local(None, "ApplicationArea") is None
    xml = '<DataArea xmlns="http://ex.com"><Sync/><PO><ID>R</ID></PO></DataArea>'
    recs = conv.to_records(xml, "Sync")
    assert recs[0]["PO_ID"] == "R"
    # ApplicationArea path: elem itself
    xml2 = """
    <SyncPO xmlns="http://ex.com">
      <ApplicationArea><BODID>X</BODID></ApplicationArea>
      <DataArea><Sync/><PO><ID>1</ID></PO></DataArea>
    </SyncPO>
    """
    recs = to_records(xml2, "Sync", include_header=True)
    assert recs[0]["ApplicationArea_BODID"] == "X"


def test_empty_noun_and_remove_guard():
    xml = '<SyncPO xmlns="http://ex.com"><DataArea><Sync/></DataArea></SyncPO>'
    with pytest.raises(BODStructureError, match="No Noun"):
        to_records(xml, "Sync")
    err = json.loads(to_json(xml, "Sync"))
    assert err["status"] == "error"
    conv = BODConverter()
    root = conv._parse('<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO/></DataArea></SyncPO>')
    data_area = conv._find_direct_local(root, "DataArea")
    stray = conv._parse("<Other/>")
    with pytest.raises(BODStructureError, match="not a direct child"):
        conv._remove_direct_child(data_area, stray, "Sync")


def test_mixed_content_and_indexed_nested():
    xml = """
    <SyncPO xmlns="http://ex.com">
      <DataArea>
        <Sync/>
        <PO>
          <P>hello <I>inner</I> tail</P>
          <Group>
            <Item><Sub a="1">A</Sub><Sub>B</Sub></Item>
            <Item>C</Item>
          </Group>
        </PO>
      </DataArea>
    </SyncPO>
    """
    data = json.loads(to_json(xml, "Sync"))
    assert data["PO_P_#text"] == "hello"
    assert data["PO_P_I"] == "inner"
    assert "A" in data.values() or any(v == "A" or v == "1" for v in data.values())


def test_project_coercion_and_ndjson_raise():
    xml = '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Flag>false</Flag></PO></DataArea></SyncPO>'
    out = project(xml, "Sync", {"flag": "PO_Flag", "const": "plain"}, coerce_booleans=False)
    assert out[0]["flag"] == "false"
    assert out[0]["const"] == "plain"
    with pytest.raises(BODParseError):
        to_ndjson("not-xml", "Sync", raise_on_error=True)
    conv = BODConverter()
    with pytest.deprecated_call():
        result = conv.convert(xml, "Sync")
    assert "PO_Flag" in result


def test_to_ndjson_error_json_default():
    out = to_ndjson("not-xml", "Sync")
    data = json.loads(out.strip())
    assert data["status"] == "error"
