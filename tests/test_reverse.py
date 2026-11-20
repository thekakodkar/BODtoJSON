"""JSON -> BOD XML reverse conversion."""

import json
import re
from pathlib import Path

import pytest

from BODtoJSON import (
    INFOR_OAGIS_NS,
    BODConverter,
    BODParseError,
    BODStructureError,
    BODTransformError,
    json_to_bod,
    to_json,
    to_records,
)

DATA = Path(__file__).parent / "data"
EXAMPLES = Path(__file__).parent.parent / "examples"

MULTI = """<SyncPurchaseOrder xmlns="http://schema.infor.com/InforOAGIS/2">
<ApplicationArea><CreationDateTime>2026-01-01T00:00:00Z</CreationDateTime></ApplicationArea>
<DataArea><Sync><ActionCriteria><ActionExpression actionCode="Replace"/></ActionCriteria></Sync>
<PurchaseOrder>
  <PurchaseOrderHeader><DocumentID><ID variationID="1">A1</ID></DocumentID><Empty/></PurchaseOrderHeader>
  <PurchaseOrderLine><LineNumber>1</LineNumber><Item><ID>X</ID><ID>Y</ID></Item></PurchaseOrderLine>
  <PurchaseOrderLine><LineNumber>2</LineNumber></PurchaseOrderLine>
  <PurchaseOrderLine><LineNumber>3</LineNumber><Note type="t">mix<Sub>s</Sub></Note></PurchaseOrderLine>
</PurchaseOrder>
<PurchaseOrder><PurchaseOrderHeader><DocumentID><ID>A2</ID></DocumentID></PurchaseOrderHeader></PurchaseOrder>
</DataArea></SyncPurchaseOrder>"""


@pytest.mark.parametrize("name", ["sync_PO_PSU000049.xml", "sync_PO_PSU000050.xml"])
def test_round_trip_sample_files(name):
    xml = (DATA / name).read_text(encoding="utf-8")
    records = to_records(xml, "Sync", include_header=True)
    rebuilt = json_to_bod(records, "Sync", version_id="2.14.x")
    assert rebuilt.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<SyncPurchaseOrder ')
    assert f'xmlns="{INFOR_OAGIS_NS}"' in rebuilt
    assert 'releaseID="9.2" versionID="2.14.x"' in rebuilt
    assert to_records(rebuilt, "Sync", include_header=True) == records


def test_round_trip_multi_noun_repeats_attributes_mixed_content():
    records = to_records(MULTI, "Sync", include_header=True)
    rebuilt = json_to_bod(records, "Sync")
    assert to_records(rebuilt, "Sync", include_header=True) == records
    assert rebuilt.count("<PurchaseOrder>") == 2
    assert "<Empty/>" in rebuilt
    assert '<Note type="t">mix' in rebuilt


def test_ndjson_and_json_text_input():
    nd = BODConverter().to_ndjson(MULTI, "Sync")
    xml = json_to_bod(nd, "Sync", include_application_area=False)
    assert "<ApplicationArea>" not in xml
    assert to_records(xml, "Sync") == to_records(MULTI, "Sync")
    single = to_json(MULTI, "Sync")
    assert json_to_bod(single.encode(), "Sync").count("<PurchaseOrder>") == 1
    assert "<ApplicationArea>" in json_to_bod(single, "Sync")


def test_nested_input_with_attributes_text_and_lists():
    data = {
        "PurchaseOrder": {
            "@type": "std",
            "PurchaseOrderHeader": {
                "DocumentID": {"ID": {"@variationID": 2, "#text": "N1"}},
                "Flag": True,
                "Nothing": None,
                "Under_Score": "keeps name",
            },
            "PurchaseOrderLine": [
                {"LineNumber": 1, "Quantity": {"@unitCode": "EA", "#text": 2.5}},
                {"LineNumber": 2},
            ],
            "Tags": [],
        }
    }
    xml = json_to_bod(data, "Process", namespace=None, release_id=None,
                      include_application_area=False, pretty=False, xml_declaration=False)
    assert xml.startswith('<ProcessPurchaseOrder><DataArea><Process/><PurchaseOrder type="std">')
    assert '<ID variationID="2">N1</ID>' in xml
    assert "<Flag>true</Flag><Nothing/><Under_Score>keeps name</Under_Score>" in xml
    assert '<Quantity unitCode="EA">2.5</Quantity>' in xml
    assert xml.count("<PurchaseOrderLine>") == 2
    assert "<Tags/>" in xml


def test_noun_relative_keys_flat_and_nested():
    flat = {"PurchaseOrderHeader_DisplayID": "P1", "@lang": "en", "Sync_TenantID": "T"}
    xml = json_to_bod(flat, "Sync", "PurchaseOrder", include_application_area=False)
    rec = to_records(xml, "Sync", include_header=True)[0]
    assert rec["PurchaseOrder_PurchaseOrderHeader_DisplayID"] == "P1"
    assert rec["PurchaseOrder_@lang"] == "en"
    assert rec["Sync_TenantID"] == "T"

    nested = {"PurchaseOrderHeader": {"DisplayID": "P2"}, "Sync": {"TenantID": "T"}}
    xml2 = json_to_bod(nested, "Sync", "PurchaseOrder", include_application_area=False)
    assert "<Sync>\n      <TenantID>T</TenantID>" in xml2
    assert "<PurchaseOrder>\n      <PurchaseOrderHeader>" in xml2


def test_mixed_flat_key_with_nested_value():
    rec = {"PurchaseOrder_PurchaseOrderHeader": {"DisplayID": "M1"}, "PurchaseOrder_X": "1"}
    xml = json_to_bod(rec, "Sync", flat=True, include_application_area=False)
    assert "<DisplayID>M1</DisplayID>" in xml and "<X>1</X>" in xml


def test_application_area_option_and_action_code():
    rec = {"PurchaseOrder_ID": "1"}
    xml = json_to_bod(
        rec, "Sync",
        application_area={"Sender_LogicalID": "lid://x", "ApplicationArea_BODID": "b1"},
        action_code="Replace",
    )
    assert "<LogicalID>lid://x</LogicalID>" in xml and "<BODID>b1</BODID>" in xml
    assert "CreationDateTime" not in xml
    assert '<ActionExpression actionCode="Replace"/>' in xml

    xml2 = json_to_bod(rec, "Sync", application_area={"ApplicationArea": {"BODID": "n"}})
    assert "<BODID>n</BODID>" in xml2
    xml3 = json_to_bod(rec, "Sync", application_area={"Sender": {"ComponentID": "erp"}})
    assert "<ComponentID>erp</ComponentID>" in xml3

    auto = json_to_bod(rec, "Sync")
    assert re.search(r"<CreationDateTime>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ</CreationDateTime>", auto)

    keep = {"Sync_ActionCriteria_ActionExpression_@actionCode": "Add", "PurchaseOrder_ID": "1"}
    assert 'actionCode="Add"' in json_to_bod(keep, "Sync", action_code="Replace")


def test_custom_root_separator_and_escaping():
    rec = {"Item.Note": 'a & b < c > "d"\r', "Item.Note.@q": 'x"y\n\tz'}
    xml = json_to_bod(rec, "Sync", root="SyncItemMaster", separator=".",
                      include_application_area=False)
    assert "<SyncItemMaster " in xml
    assert "a &amp; b &lt; c &gt; \"d\"&#13;" in xml
    assert 'q="x&quot;y&#10;&#9;z"' in xml
    assert to_records(xml, "Sync")[0]["Item_Note_@q"] == 'x"y\n\tz'


def test_from_json_method_uses_converter_settings():
    conv = BODConverter(separator="__")
    xml = conv.from_json({"PO__Header__ID": "1"}, "Sync", include_application_area=False)
    assert "<Header>\n        <ID>1</ID>" in xml


def test_reverse_rules_map_foreign_json_to_bod():
    rules = json.loads((EXAMPLES / "rules_json_to_bod.json").read_text())
    order = json.loads((EXAMPLES / "order.json").read_text())
    xml = json_to_bod(order, "Sync", "PurchaseOrder", rules=rules, action_code="Replace",
                      include_application_area=False)
    rec = to_records(xml, "Sync", include_header=True)[0]
    assert rec["PurchaseOrder_PurchaseOrderHeader_DocumentID_ID"] == "PO-1001"
    assert rec["PurchaseOrder_PurchaseOrderHeader_Status_Code"] == "Open"
    assert rec["PurchaseOrder_PurchaseOrderHeader_CustomerParty_Name"] == "Ada Lovelace"
    assert rec["PurchaseOrder_PurchaseOrderLine_0_Quantity_@unitCode"] == "EA"
    assert rec["PurchaseOrder_PurchaseOrderLine_1_Quantity_#text"] == "3"
    assert rec["PurchaseOrder_PurchaseOrderLine_1_Item_ID"] == "SKU-2"
    assert "order_id" not in xml  # mode "only" by default for reverse rules


def test_reverse_rules_merge_mode_and_errors():
    rec = {"PurchaseOrder_ID": "1", "first": "A"}
    xml = json_to_bod(rec, "Sync", rules={"rules": {"PurchaseOrder_Name": "$first"},
                                          "mode": "merge", "drop": ["first"]},
                      include_application_area=False)
    assert "<Name>A</Name>" in xml and "<ID>1</ID>" in xml
    with pytest.raises(BODTransformError):
        json_to_bod(rec, "Sync", rules={"x": {"nope": 1}})


@pytest.mark.parametrize(
    "data, kwargs, exc, message",
    [
        ("", {}, BODParseError, "empty"),
        ("{bad", {}, BODParseError, "neither JSON"),
        (b"\xff\xfe", {}, BODParseError, "UTF-8"),
        ("x" * 50, {"max_size": 10}, BODParseError, "maximum"),
        (b"x" * 50, {"max_size": 10}, BODParseError, "maximum"),
        ("[" * 100000 + "]" * 100000, {"max_size": 10**7}, BODParseError, "deeply"),
        ("5", {}, BODStructureError, "JSON object"),
        ("[]", {}, BODStructureError, "no records"),
        ("[1]", {}, BODStructureError, "JSON object"),
        ({"status": "error", "message": "boom"}, {}, BODStructureError, "boom"),
        ({"Sync_TenantID": "x"}, {}, BODStructureError, "No noun"),
        ({"PurchaseOrder_bad name": "x"}, {}, BODStructureError, "Invalid XML element"),
        ({"PurchaseOrder_1x": "x"}, {}, BODStructureError, "Invalid XML element"),
        ({"PurchaseOrder_@a:b": "x"}, {}, BODStructureError, "attribute"),
        ({"@a": "x"}, {}, BODStructureError, "without an element"),
        ({"#text": "x"}, {}, BODStructureError, "misplaced"),
        ({"PurchaseOrder_#text_X": "x"}, {}, BODStructureError, "misplaced"),
        ({"0_x": "x"}, {}, BODStructureError, "no element name"),
        ({"": "x"}, {}, BODStructureError, "non-empty"),
        ({"PurchaseOrder_A": "\x01"}, {}, BODStructureError, "not allowed"),
        ({"PurchaseOrder_A": {"@b": [1]}}, {}, BODStructureError, "scalars"),
        ({"PurchaseOrder": {"A": [[1]]}}, {}, BODStructureError, "nested list"),
        ({"PurchaseOrder": {"": 1}}, {}, BODStructureError, "non-empty"),
        ({"PurchaseOrder": {"A": object()}}, {}, BODStructureError, "Unsupported value"),
        ({"PurchaseOrder_A": "1"}, {"separator": ""}, BODStructureError, "Separator"),
        ({"PurchaseOrder_A": "1"}, {"verb": "bad verb"}, BODStructureError, "verb"),
        ({"PurchaseOrder_A": "1"}, {"noun": "1x"}, BODStructureError, "noun"),
        ({"PurchaseOrder_A": "1"}, {"root": "<x>"}, BODStructureError, "root"),
        ({"A_B_C_D": "1"}, {"max_depth": 2}, BODStructureError, "deeper"),
        ({"A": {"B": {"C": {"D": 1}}}}, {"max_depth": 2}, BODStructureError, "exceeds"),
        ({"A": {"B": [[1]]}}, {"rules": {"x": "$A_B_0"}}, BODStructureError, "nested lists"),
        ({"A": {"B": {"C": {"D": 1}}}}, {"rules": {"x": 1}, "max_depth": 1}, BODStructureError,
         "exceeds"),
    ],
)
def test_reverse_errors(data, kwargs, exc, message):
    kwargs = dict(kwargs)
    verb = kwargs.pop("verb", "Sync")
    with pytest.raises(exc, match=message):
        json_to_bod(data, verb, **kwargs)


def test_rebuilt_xml_is_accepted_by_hardened_parser():
    xml = json_to_bod({"PurchaseOrder_Note": "<!DOCTYPE x>"}, "Sync")
    assert "&lt;!DOCTYPE x&gt;" in xml
    # Literal '<!DOCTYPE' never appears in output, so the safe parser accepts it.
    assert to_records(xml, "Sync")[0]["PurchaseOrder_Note"] == "<!DOCTYPE x>"
