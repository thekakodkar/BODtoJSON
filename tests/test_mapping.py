"""One-call mapping to a nested output template: bod_to_json / bod_to_data / Mapper."""

import json
from pathlib import Path

import pytest

from BODtoJSON import (
    BODStructureError,
    BODTransformError,
    Mapper,
    bod_to_data,
    bod_to_json,
    to_records,
)
from BODtoJSON.mapping import is_template_rules, load_rules

DATA = Path(__file__).parent / "data"
EXAMPLES = Path(__file__).parent.parent / "examples"
LINES_XML = (DATA / "sync_PO_lines.xml").read_text(encoding="utf-8")
PO49_XML = (DATA / "sync_PO_PSU000049.xml").read_text(encoding="utf-8")

# The user's RULES, exactly as written in their ION script (JSON true -> Python True).
RULES = {
    "externalSystemId": {
        "template": "{Sync_AccountingEntityID}_{PurchaseOrder_PurchaseOrderHeader_DisplayID}"
    },
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
            "externalSystemId": {
                "template": "{Sync_AccountingEntityID}_{PurchaseOrder_PurchaseOrderHeader_DisplayID}_{PurchaseOrder_PurchaseOrderLine_*_LineNumber}"
            },
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


def _line(ext, amount, num, qty, unit, price, coding):
    return {
        "externalSystemId": ext,
        "isActive": True,
        "amount": amount,
        "lineNumber": num,
        "quantity": qty,
        "unit": unit,
        "unitPrice": price,
        "codingLines": coding,
        "deliveryLines": [{"isActive": True, "externalSystemMetadata": [{}]}],
        "externalSystemMetadata": [{}],
    }


EXPECTED = {
    "externalSystemId": "3555_PSU000051",
    "isActive": True,
    "companyId": "company[3555]",
    "amount": "1350.50",
    "currencyCode": "EUR",
    "orderIdentifier": "PSU000051",
    "registerDate": "2026-11-19T10:15:00Z",
    "supplier": "SUP0042",
    "externalSystemMetadata": [{}],
    "purchaseOrderLines": [
        _line("3555_PSU000051_10", "500", "10", "5", "EA", "100", [{}, {}]),
        _line("3555_PSU000051_20", "750.50", "20", "2.5", "KG", "300.20", [{}]),
        _line("3555_PSU000051_30", "100", "30", "1", "EA", "100", []),
    ],
    "purchaseOrderComments": [{}],
}


# ------------------------------------------------------------ user's script
def test_users_rules_one_call():
    input_var = LINES_XML
    output_var = bod_to_json(input_var, rules=RULES)
    assert json.loads(output_var) == [EXPECTED]


def test_users_rules_as_json_text_file_and_single(tmp_path):
    text = json.dumps(RULES)
    assert bod_to_data(LINES_XML, text, single=True) == EXPECTED
    path = tmp_path / "rules.json"
    path.write_text(text)
    assert bod_to_data(LINES_XML, str(path)) == [EXPECTED]
    assert bod_to_data(LINES_XML, path) == [EXPECTED]
    assert bod_to_data(LINES_XML.encode(), text.encode(), single=True) == EXPECTED
    assert Mapper.from_file(EXAMPLES / "ion_purchase_order_template.json").to_data(
        LINES_XML, single=True
    ) == EXPECTED


def test_example_ion_script_runs():
    script = (EXAMPLES / "ion_script.py").read_text()
    ns = {"input_var": LINES_XML}
    exec(compile(script, "ion_script.py", "exec"), ns)  # noqa: S102 - running the example
    assert json.loads(ns["output_var"]) == [EXPECTED]


def test_no_lines_and_missing_fields():
    out = bod_to_data(PO49_XML, RULES, single=True)
    assert out["purchaseOrderLines"] == []
    assert out["registerDate"] is None and out["supplier"] is None
    assert out["amount"] == "2500"  # _#text fallback
    empty = bod_to_data(PO49_XML, RULES, single=True, missing="")
    assert empty["supplier"] == ""


def test_single_unindexed_line_and_single_coding_line():
    xml = LINES_XML.split("<PurchaseOrderLine>")[0] + "<PurchaseOrderLine>" + (
        LINES_XML.split("<PurchaseOrderLine>")[2].split("</PurchaseOrderLine>")[0]
    ) + "</PurchaseOrderLine></PurchaseOrder></DataArea></SyncPurchaseOrder>"
    out = bod_to_data(xml, RULES, single=True)
    assert len(out["purchaseOrderLines"]) == 1
    line = out["purchaseOrderLines"][0]
    assert line["lineNumber"] == "20" and line["externalSystemId"] == "3555_PSU000051_20"
    assert line["codingLines"] == [{}]


def test_multi_noun_gives_one_item_per_noun():
    second = "<PurchaseOrder><PurchaseOrderHeader><DisplayID>PSU9</DisplayID></PurchaseOrderHeader></PurchaseOrder>"
    xml = LINES_XML.replace("</DataArea>", second + "</DataArea>")
    out = bod_to_data(xml, {"id": "PurchaseOrder_PurchaseOrderHeader_DisplayID"})
    assert out == [{"id": "PSU000051"}, {"id": "PSU9"}]


# ------------------------------------------------------- template features
def test_relative_paths_nested_repeat_items_and_where():
    tpl = {
        "lines": {
            "repeat": "PurchaseOrder_PurchaseOrderLine_*",
            "where": {"gt": ["ExtendedAmount", 200]},
            "item": {
                "no": "LineNumber",
                "item": "Item_ID",
                "entity": "Sync_AccountingEntityID",
                "coding": {
                    "repeat": "CodingLine_*",
                    "item": {
                        "account": "Account",
                        "pct": {"number": "Percentage"},
                        "abs": "PurchaseOrder_PurchaseOrderLine_*_CodingLine_*_Account",
                        "rel": "CodingLine_*_Account",
                        "line": "LineNumber",
                        "key": "{LineNumber}-{Account}",
                    },
                },
            },
        }
    }
    out = bod_to_data(LINES_XML, tpl, single=True)
    assert [ln["no"] for ln in out["lines"]] == ["10", "20"]
    first = out["lines"][0]
    assert first["item"] == "ITEM-A" and first["entity"] == "3555"
    assert first["coding"] == [
        {"account": "4000", "pct": 60, "abs": "4000", "rel": "4000", "line": "10", "key": "10-4000"},
        {"account": "4010", "pct": 40, "abs": "4010", "rel": "4010", "line": "10", "key": "10-4010"},
    ]
    assert out["lines"][1]["coding"][0]["account"] == "4100"


def test_top_level_star_takes_first_match_and_absolute_repeat_inside_row():
    tpl = {
        "firstLine": "PurchaseOrder_PurchaseOrderLine_*_LineNumber",
        "missing": "PurchaseOrder_Nope_*_X",
        "lines": {
            "repeat": "PurchaseOrder_PurchaseOrderLine_*",
            "item": {"codes": {"repeat": "PurchaseOrder_PurchaseOrderLine_*_CodingLine_*",
                               "item": "Account"}},
        },
        "none": {"repeat": "PurchaseOrder_Nope_*", "item": {}},
        "unbound": {"repeat": "PurchaseOrder_*_Line_*", "item": {}},
    }
    out = bod_to_data(LINES_XML, tpl, single=True)
    assert out["firstLine"] == "10" and out["missing"] is None
    assert out["lines"][0]["codes"] == ["4000", "4010"]
    assert out["none"] == [] and out["unbound"] == []


def test_if_case_concat_and_helpers():
    tpl = {
        "band": {
            "if": [
                {"when": {"ge": ["PurchaseOrder_PurchaseOrderHeader_ExtendedAmount", 10000]}, "then": "high"},
                {"when": {"path": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount", "op": "ge", "value": 1000}, "then": "medium"},
            ],
            "else": "low",
        },
        "simpleIf": {"if": {"eq": ["PurchaseOrder_PurchaseOrderHeader_Status_Code", "Open"]},
                     "then": True, "else": False},
        "noElse": {"if": False, "then": 1},
        "statusList": {
            "case": [
                {"when": {"eq": ["PurchaseOrder_PurchaseOrderHeader_Status_Code", "Closed"]}, "then": "C"},
                {"when": {"in": ["PurchaseOrder_PurchaseOrderHeader_Status_Code", ["Open", "New"]]}, "then": "O"},
            ],
            "default": "?",
        },
        "caseDefault": {"case": [{"when": False, "then": 1}], "default": "none"},
        "currency": {"case": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID",
                     "when": {"eur": "Euro"}, "default": "Other", "ignore_case": True},
        "currencyMiss": {"case": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount_@currencyID",
                         "when": {"USD": "Dollar"}, "default": "Other"},
        "label": {"concat": ["PO-", "PurchaseOrder_PurchaseOrderHeader_DisplayID", "PurchaseOrder_Nope"],
                  "sep": "/"},
        "name": {"coalesce": ["PurchaseOrder_Nope", "PurchaseOrder_PurchaseOrderHeader_SupplierParty_Name"]},
        "nothing": {"coalesce": ["PurchaseOrder_Nope", ""]},
        "up": {"upper": "PurchaseOrder_PurchaseOrderHeader_SupplierParty_Name"},
        "low": {"lower": "PurchaseOrder_PurchaseOrderHeader_SupplierParty_Name"},
        "trim": {"trim": {"literal": "  x  "}},
        "upNone": {"upper": "PurchaseOrder_Nope"},
        "num": {"number": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount"},
        "numInt": {"number": "Sync_AccountingEntityID"},
        "numBad": {"number": "PurchaseOrder_PurchaseOrderHeader_DisplayID", "default": 0},
        "rep": {"replace": "PurchaseOrder_PurchaseOrderHeader_DisplayID", "old": "PSU", "new": "PO"},
        "sub": {"substr": "PurchaseOrder_PurchaseOrderHeader_DisplayID", "start": 3},
        "lit": {"literal": "PurchaseOrder_PurchaseOrderHeader_DisplayID"},
        "constText": {"template": "DIMENSION1"},
        "braces": "{{x}} {Sync_TenantID} {Nope_Field}",
        "dollar": "$PurchaseOrder_PurchaseOrderHeader_DisplayID",
        "wrapped": "{PurchaseOrder_PurchaseOrderHeader_DisplayID}",
        "pathDefault": {"path": "PurchaseOrder_Nope", "default": "n/a"},
        "pathHit": {"path": "$Sync_TenantID", "default": "n/a"},
        "pathMiss": {"path": "PurchaseOrder_Nope"},
        "thenPath": {"if": True, "then": "Sync_TenantID"},
        "thenMissingPath": {"if": True, "then": "Some_Missing"},
        "thenTemplate": {"if": True, "then": "T-{Sync_TenantID}"},
        "blank": "",
        "nested": {"a": [1, "Sync_TenantID", {"b": None}]},
    }
    out = bod_to_data(LINES_XML, tpl, single=True)
    assert out == {
        "band": "medium",
        "simpleIf": True,
        "noElse": None,
        "statusList": "O",
        "caseDefault": "none",
        "currency": "Euro",
        "currencyMiss": "Other",
        "label": "PO-/PSU000051",
        "name": "Nordic Parts Oy",
        "nothing": None,
        "up": "NORDIC PARTS OY",
        "low": "nordic parts oy",
        "trim": "x",
        "upNone": None,
        "num": 1350.5,
        "numInt": 3555,
        "numBad": 0,
        "rep": "PO000051",
        "sub": "000051",
        "lit": "PurchaseOrder_PurchaseOrderHeader_DisplayID",
        "constText": "DIMENSION1",
        "braces": "{x} TEST_TST ",
        "dollar": "PSU000051",
        "wrapped": "PSU000051",
        "pathDefault": "n/a",
        "pathHit": "TEST_TST",
        "pathMiss": None,
        "thenPath": "TEST_TST",
        "thenMissingPath": None,
        "thenTemplate": "T-TEST_TST",
        "blank": "",
        "nested": {"a": [1, "TEST_TST", {"b": None}]},
    }


H = "PurchaseOrder_PurchaseOrderHeader_"


@pytest.mark.parametrize(
    "cond, expected",
    [
        ({"eq": [H + "Status_Code", "Open"]}, True),
        ({"ne": [H + "Status_Code", "Open"]}, False),
        ({"==": [H + "ExtendedAmount", 1350.5]}, True),
        ({"gt": [H + "ExtendedAmount", "1000"]}, True),
        ({"ge": [H + "ExtendedAmount", 1350.5]}, True),
        ({"lt": [H + "ExtendedAmount", 100]}, False),
        ({"le": [H + "ExtendedAmount", 1350.5]}, True),
        ({"in": [H + "Status_Code", ["Open"]]}, True),
        ({"in": [H + "Status_Code", "Open"]}, True),
        ({"not_in": [H + "Status_Code", ["Open"]]}, False),
        ({"contains": [H + "SupplierParty_Name", "Parts"]}, True),
        ({"not_contains": [H + "SupplierParty_Name", "Parts"]}, False),
        ({"starts_with": [H + "DisplayID", "psu"], "ignore_case": True}, True),
        ({"ends_with": [H + "DisplayID", "51"]}, True),
        ({"exists": [H + "DisplayID"]}, True),
        ({"exists": H + "Nope"}, False),
        ({"missing": H + "Nope"}, True),
        ({"empty": H + "Nope"}, True),
        ({"not_empty": H + "DisplayID"}, True),
        ({"eq": ["{" + H + "DisplayID}", "PSU000051"]}, True),
        ({"eq": [H + "DisplayID", "$" + H + "DocumentID_ID"]}, True),
        ({"eq": [H + "DisplayID", "$$x"]}, False),
        ({"eq": [{"concat": ["Sync_TenantID", H + "DisplayID"], "sep": "-"}, "TEST_TST-PSU000051"]}, True),
        ({"eq": [{"upper": H + "Nope"}, "x"]}, False),
        ({"eq": [H + "DisplayID", {"template": "PSU{Sync_AccountingEntityID}"}]}, False),
        ({"all": [{"exists": H + "DisplayID"}, {"eq": [H + "Status_Code", "Open"]}]}, True),
        ({"and": [{"exists": H + "DisplayID"}, {"exists": H + "Nope"}]}, False),
        ({"any": [{"exists": H + "Nope"}, {"exists": H + "DisplayID"}]}, True),
        ({"or": [{"exists": H + "Nope"}]}, False),
        ({"not": {"exists": H + "Nope"}}, True),
        ({"path": H + "Status_Code", "op": "eq", "value": "Open"}, True),
        ({"path": H + "Status_Code", "value": "Open"}, True),
        ({"path": H + "Nope"}, False),
        ({"path": H + "Status_Code", "op": "in", "value": ["X", "Open"]}, True),
        ({"expr": {"lower": H + "Status_Code"}, "op": "eq", "value": "open"}, True),
        (H + "DisplayID", True),
        (H + "Nope", False),
        (True, True),
    ],
)
def test_condition_forms(cond, expected):
    out = bod_to_data(LINES_XML, {"r": {"if": cond, "then": True, "else": False}}, single=True)
    assert out["r"] is expected


# --------------------------------------------------------- flat 2.5 rules
def test_flat_rules_still_work_and_are_detected():
    flat = {"ref": {"concat": ["PO-", "$" + H + "DisplayID"]}, "big": {
        "if": {"path": H + "ExtendedAmount", "op": "gt", "value": 1000}, "then": True, "else": False}}
    assert not is_template_rules(flat)
    rec = bod_to_data(LINES_XML, flat, single=True)
    assert rec["ref"] == "PO-PSU000051" and rec["big"] is True
    assert rec[H + "DisplayID"] == "PSU000051"  # merge mode keeps source
    wrapped = {"rules": {"x": "$Sync_TenantID"}, "mode": "only"}
    assert bod_to_data(LINES_XML, wrapped) == [{"x": "TEST_TST"}]
    assert Mapper(wrapped).kind == "flat"
    assert Mapper(wrapped).apply({"Sync_TenantID": "T"}) == {"x": "T"}
    # still accepted by to_records
    assert to_records(LINES_XML, "Sync", rules=flat)[0]["ref"] == "PO-PSU000051"


@pytest.mark.parametrize(
    "rules, template",
    [
        (RULES, True),
        ({"a": "$x"}, False),
        ({"a": "x"}, True),
        ({"a": ["$x"]}, True),
        ({"a": {"nested": "$x"}}, True),
        ({"a": {"repeat": "A_*", "item": {}}}, True),
        ({"a": {"upper": "$x"}}, False),
        ({"a": {"upper": "x"}}, True),
        ({"a": {"concat": ["x", "y"]}}, True),
        ({"a": {"concat": ["$x", "y"]}}, False),
        ({"a": {"literal": 1}}, True),
        ({"a": 1}, True),
        ("not a dict", True),
    ],
)
def test_detection(rules, template):
    assert is_template_rules(rules) is template


def test_kind_override_and_apply():
    m = Mapper({"a": "$x"}, kind="template")
    assert m.kind == "template" and m.apply({"x": "1"}) == {"a": "1"}
    with pytest.raises(BODTransformError, match="kind"):
        Mapper({}, kind="weird")
    with pytest.raises(BODTransformError, match="Separator"):
        Mapper({}, separator="")
    with pytest.raises(BODTransformError, match="dict"):
        Mapper({}).apply(["x"])  # type: ignore[arg-type]
    passed = Mapper(RULES)
    assert bod_to_data(LINES_XML, passed, single=True) == EXPECTED  # type: ignore[arg-type]


def test_custom_separator_and_explicit_verb():
    m = Mapper({"id": "PurchaseOrder.PurchaseOrderHeader.DisplayID",
                "lines": {"repeat": "PurchaseOrder.PurchaseOrderLine.*", "item": "LineNumber"}},
               separator=".")
    assert m.to_data(LINES_XML, "Sync", single=True) == {"id": "PSU000051",
                                                          "lines": ["10", "20", "30"]}
    assert json.loads(m.to_json(LINES_XML, indent=1)) == [{"id": "PSU000051",
                                                           "lines": ["10", "20", "30"]}]


def test_verb_detection_errors():
    with pytest.raises(BODStructureError, match="detect the verb"):
        bod_to_json("<X><DataArea><Sync/></DataArea></X>", {"a": "b"})
    with pytest.raises(BODStructureError):
        from BODtoJSON import BODConverter
        BODConverter().detect_verb("<X/>")
    from BODtoJSON import BODConverter
    assert BODConverter().detect_verb(LINES_XML) == "Sync"


# --------------------------------------------------------------- errors
@pytest.mark.parametrize(
    "rules, message",
    [
        ("not json and no file", "existing file path"),
        ("{bad json", "not valid JSON"),
        ({"a": {"repeat": "PurchaseOrder_Line"}}, r"\$\.a\.repeat.*must end with"),
        ({"a": {"repeat": "*"}}, "must end with"),
        ({"lines": {"repeat": "A_*", "item": {"x": "Bad_x*"}}}, r"\$\.lines\.item\.x.*whole path segment"),
        ({"a": "{Bad_x*}"}, "whole path segment"),
        ({"a": [{"b": object()}]}, r"\$\.a\[0\]\.b.*unsupported"),
        ({"a": {"if": {"bogus": ["x", 1]}, "then": 1}}, "unknown operator 'bogus'"),
        ({"a": {"if": {"eq": ["x"]}, "then": 1}}, r"needs \[path, value\]"),
        ({"a": {"if": {"exists": ["x", 1]}, "then": 1}}, "takes only a path"),
        ({"a": {"if": {"eq": []}, "then": 1}}, "at least a path"),
        ({"a": {"if": {"eq": ["x", 1], "ne": ["y", 1]}, "then": 1}}, "expected one operator"),
        ({"a": {"if": {"eq": ["x", 1], "ignore_case": 1}, "then": 1}}, "ignore_case"),
        ({"a": {"if": {"eq": [3, 1]}, "then": 1}}, "non-empty string"),
        ({"a": {"if": {"path": "x", "bogus": 1}, "then": 1}}, "unknown condition keys"),
        ({"a": {"if": {"path": "x", "op": "nope", "value": 1}, "then": 1}}, "Unknown operator"),
        ({"a": {"if": {"path": "x", "op": "gt"}, "then": 1}}, "needs a 'value'"),
        ({"a": {"if": {"path": "x", "op": "in", "value": 1}, "then": 1}}, "list 'value'"),
        ({"a": {"if": {"expr": {"upper": {"x": object()}}, "op": "exists"}, "then": 1}}, "unsupported"),
        ({"a": {"if": {"all": "x"}, "then": 1}}, "'all' needs a list"),
        ({"a": {"if": {"not": True, "x": 1}, "then": 1}}, "'not' takes"),
        ({"a": {"if": 3, "then": 1}}, "condition must be"),
        ({"a": {"if": [], "else": 1}}, "branch list is empty"),
        ({"a": {"if": [{"when": True}]}}, "each branch"),
        ({"a": {"if": [{"when": True, "then": 1}], "then": 2}}, "inside each branch"),
        ({"a": {"case": [{"when": True, "then": 1}], "when": {}}}, "drop 'when'"),
        ({"a": {"case": "x", "default": 1}}, "list of {when, then}"),
        ({"a": {"concat": "x"}}, "needs a list"),
        ({"a": {"concat": [], "sep": 1}}, "'sep'"),
        ({"a": {"template": 1}}, "needs a string"),
        ({"a": {"path": ""}}, "non-empty"),
        ({"a": {"replace": "x", "old": ""}}, "'old'"),
        ({"a": {"replace": "x", "old": "a", "new": 2}}, "'new'"),
        ({"a": {"substr": "x", "start": "1"}}, "integer"),
        ({"a": {1: "x"}}, "keys must be strings"),
        ({"a": {"repeat": "A_*", "where": 5}}, r"\$\.a\.where"),
    ],
)
def test_bad_rules_name_the_location(rules, message):
    with pytest.raises(BODTransformError, match=message):
        Mapper(rules)


def test_depth_limits():
    deep = "x"
    for _ in range(140):
        deep = {"n": deep}
    with pytest.raises(BODTransformError, match="deeper"):
        Mapper(deep)
    cond = True
    for _ in range(140):
        cond = {"not": cond}
    with pytest.raises(BODTransformError, match="deeper"):
        Mapper({"a": {"if": cond, "then": 1}})


def test_load_rules_bytes_and_bad_bytes():
    assert load_rules(b'\xef\xbb\xbf{"a": 1}') == {"a": 1}
    with pytest.raises(BODTransformError):
        load_rules("[1")
