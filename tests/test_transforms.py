"""Declarative transformation rules (if/else, case, concat, template, ...)."""

import json
from pathlib import Path

import pytest

from BODtoJSON import (
    BODConverter,
    BODTransformError,
    TransformRules,
    apply_rules,
    compile_rules,
    project,
    to_json,
    to_ndjson,
    to_records,
)

PO = "PurchaseOrder_PurchaseOrderHeader"

LINES_XML = """<SyncPurchaseOrder xmlns="http://schema.infor.com/InforOAGIS/2">
<DataArea><Sync><AccountingEntityID>3555</AccountingEntityID></Sync>
<PurchaseOrder>
  <PurchaseOrderHeader><DisplayID>PO1</DisplayID>
    <Contact><FirstName>Ada</FirstName><LastName>Lovelace</LastName></Contact>
    <Status><Code>2</Code></Status>
  </PurchaseOrderHeader>
  <PurchaseOrderLine><LineNumber>10</LineNumber><Quantity unitCode="EA">5</Quantity></PurchaseOrderLine>
  <PurchaseOrderLine><LineNumber>20</LineNumber><Quantity unitCode="KG">0</Quantity></PurchaseOrderLine>
</PurchaseOrder>
</DataArea></SyncPurchaseOrder>"""

ONE_LINE_XML = LINES_XML.replace(
    '<PurchaseOrderLine><LineNumber>20</LineNumber><Quantity unitCode="KG">0</Quantity></PurchaseOrderLine>',
    "",
)

REC = {
    "First": "Ada",
    "Last": "Lovelace",
    "Middle": None,
    "Status": "2",
    "Amount": "2500",
    "Country": "fi",
    "Empty": "  ",
    "Id_#text": "X1",
    "Id_@type": "PO",
}


def run(rules, record=None):
    return TransformRules({"rules": rules, "mode": "only"}).apply(record or REC)


# ---------------------------------------------------------------- values
def test_path_literal_and_escape():
    out = run(
        {
            "a": "$First",
            "b": "plain text",
            "c": "$$First",
            "d": 42,
            "e": None,
            "f": {"literal": ["x", 1]},
            "g": {"path": "Nope", "default": "dflt"},
            "h": {"path": "$Last"},
            "i": "$Id",  # falls back to Id_#text
            "j": "$Missing",
        }
    )
    assert out == {
        "a": "Ada",
        "b": "plain text",
        "c": "$First",
        "d": 42,
        "e": None,
        "f": ["x", 1],
        "g": "dflt",
        "h": "Lovelace",
        "i": "X1",
        "j": None,
    }


def test_concat_and_template():
    out = run(
        {
            "full": {"concat": ["$First", "$Middle", "$Last"], "sep": " "},
            "keep": {"concat": ["$First", "$Middle", "$Last"], "sep": "|", "skip_empty": False},
            "pre": {"concat": ["PO-", "$Id_#text"]},
            "tpl": {"template": "{{{Last}}}, {First} ({Missing}) {Id_@type}"},
            "num": {"concat": [1, True, "$First"]},
        }
    )
    assert out["full"] == "Ada Lovelace"
    assert out["keep"] == "Ada||Lovelace"
    assert out["pre"] == "PO-X1"
    assert out["tpl"] == "{Lovelace}, Ada () PO"
    assert out["num"] == "1trueAda"


def test_if_else_and_elif_chain():
    rules = {
        "big": {
            "if": {"path": "Amount", "op": "gt", "value": 1000},
            "then": "BIG",
            "else": "small",
        },
        "tier": {
            "if": [
                {"when": {"path": "Amount", "op": ">=", "value": 5000}, "then": "gold"},
                {"when": {"path": "Amount", "op": ">=", "value": 1000}, "then": "silver"},
            ],
            "else": "bronze",
        },
        "none": {"if": {"path": "Amount", "op": "lt", "value": 1}, "then": "x"},
        "nordic": {
            "if": {"path": "Country", "op": "in", "value": ["FI", "SE"], "ignore_case": True},
            "then": {"upper": "$Country"},
            "else": "other",
        },
    }
    out = run(rules)
    assert out == {"big": "BIG", "tier": "silver", "none": None, "nordic": "FI"}


def test_case_mapping_forms():
    out = run(
        {
            "status": {"case": "$Status", "when": {"1": "Open", "2": "Closed"}, "default": "?"},
            "miss": {"case": "$Status", "when": {"9": "x"}, "default": "$First"},
            "list": {
                "case": "$Country",
                "when": [
                    {"match": ["se", "no"], "then": "Scandi"},
                    {"match": "FI", "then": "Finland"},
                ],
                "ignore_case": True,
            },
            "dictic": {"case": "$Country", "when": {"FI": 1}, "ignore_case": True},
            "nodefault": {"case": "$Status", "when": {"7": "x"}},
            "listmiss": {"case": "$Status", "when": [{"match": "7", "then": "x"}]},
        }
    )
    assert out == {
        "status": "Closed",
        "miss": "Ada",
        "list": "Finland",
        "dictic": 1,
        "nodefault": None,
        "listmiss": None,
    }


def test_string_helpers_and_number():
    out = run(
        {
            "co": {"coalesce": ["$Middle", "$Empty", "$Last"]},
            "co_none": {"coalesce": ["$Middle", "$Missing"]},
            "up": {"upper": "$First"},
            "low": {"lower": "$First"},
            "trim": {"trim": {"concat": ["  ", "$First", "  "], "skip_empty": False}},
            "up_none": {"upper": "$Missing"},
            "rep": {"replace": "$Last", "old": "e", "new": "3"},
            "rep_none": {"replace": "$Missing", "old": "e"},
            "sub": {"substr": "$Last", "start": 0, "end": 4},
            "sub_none": {"substr": "$Missing", "end": 1},
            "n_int": {"number": "$Amount"},
            "n_float": {"number": "12.5"},
            "n_bad": {"number": "$First", "default": 0},
            "n_bad2": {"number": "$First"},
            "n_bool": {"number": True},
            "n_lit": {"number": 7},
        }
    )
    assert out == {
        "co": "Lovelace",
        "co_none": None,
        "up": "ADA",
        "low": "ada",
        "trim": "Ada",
        "up_none": None,
        "rep": "Lov3lac3",
        "rep_none": None,
        "sub": "Love",
        "sub_none": None,
        "n_int": 2500,
        "n_float": 12.5,
        "n_bad": 0,
        "n_bad2": None,
        "n_bool": None,
        "n_lit": 7,
    }


@pytest.mark.parametrize(
    "cond, expected",
    [
        ({"path": "Status", "op": "eq", "value": "2"}, True),
        ({"path": "Status", "value": 2}, True),
        ({"path": "Status", "op": "eq", "value": 2.0}, True),
        ({"path": "Amount", "op": "==", "value": "2500.0"}, False),
        ({"path": "Status", "op": "ne", "value": "2"}, False),
        ({"path": "Status", "op": "!=", "value": "3"}, True),
        ({"path": "Amount", "op": "gt", "value": "999"}, True),
        ({"path": "Amount", "op": "ge", "value": 2500}, True),
        ({"path": "Amount", "op": "lt", "value": 2500}, False),
        ({"path": "Amount", "op": "le", "value": 2500}, True),
        ({"path": "Amount", "op": "lte", "value": 1}, False),
        ({"path": "First", "op": "gt", "value": "Aa"}, True),
        ({"path": "Missing", "op": "gt", "value": "A"}, False),
        ({"path": "First", "op": "contains", "value": "d"}, True),
        ({"path": "First", "op": "not_contains", "value": "d"}, False),
        ({"path": "First", "op": "starts_with", "value": "a", "ignore_case": True}, True),
        ({"path": "First", "op": "startswith", "value": "a"}, False),
        ({"path": "Last", "op": "ends_with", "value": "ace"}, True),
        ({"path": "Country", "op": "eq", "value": "FI", "ignore_case": True}, True),
        ({"path": "Country", "op": "eq", "value": "FI"}, False),
        ({"path": "Status", "op": "in", "value": ["1", "2"]}, True),
        ({"path": "Status", "op": "not_in", "value": ["1", "2"]}, False),
        ({"path": "Middle", "op": "exists"}, True),
        ({"path": "Middle", "op": "empty"}, True),
        ({"path": "Empty", "op": "empty"}, True),
        ({"path": "Missing", "op": "missing"}, True),
        ({"path": "Missing", "op": "not_exists"}, True),
        ({"path": "First"}, True),
        ({"path": "Middle", "op": "not_empty"}, False),
        ({"path": "First", "op": "eq", "value": "$First"}, True),
        ({"path": "$First", "op": "eq", "value": "Ada"}, True),
        ({"expr": {"concat": ["$First", "$Last"]}, "op": "eq", "value": "AdaLovelace"}, True),
        ({"expr": "$Missing", "op": "exists"}, False),
        ({"all": [{"path": "First"}, {"path": "Last"}]}, True),
        ({"and": [{"path": "First"}, {"path": "Missing"}]}, False),
        ({"any": [{"path": "Missing"}, {"path": "Last"}]}, True),
        ({"or": [{"path": "Missing"}]}, False),
        ({"not": {"path": "Missing"}}, True),
        ("$First", True),
        ("$Empty", False),
        (True, True),
        (False, False),
        ({"path": "Flag", "op": "eq", "value": True}, True),
        ({"path": "Middle", "op": "eq", "value": ""}, True),
    ],
)
def test_condition_operators(cond, expected):
    rec = dict(REC, Flag="TRUE")
    out = run({"r": {"if": cond, "then": True, "else": False}}, rec)
    assert out["r"] is expected


# ---------------------------------------------------------------- modes
def test_merge_mode_keeps_source_and_chains_rules():
    rules = {
        "Full": {"concat": ["$First", "$Last"], "sep": " "},
        "Greeting": {"template": "Hi {Full}"},
        "First": {"upper": "$First"},
    }
    out = apply_rules(REC, rules)
    assert out["Last"] == "Lovelace"
    assert out["Greeting"] == "Hi Ada Lovelace"
    assert out["First"] == "ADA"
    assert list(out)[: len(REC)] == list(REC)


def test_only_mode_sees_source_and_outputs():
    out = run({"Full": {"concat": ["$First", "$Last"]}, "Again": "$Full"})
    assert out == {"Full": "AdaLovelace", "Again": "AdaLovelace"}


def test_drop_globs_but_keeps_rule_targets():
    cfg = {"rules": {"Id_#text": "$Id_#text"}, "drop": ["Id_*", "Empty"]}
    out = apply_rules(REC, cfg)
    assert "Id_@type" not in out and "Empty" not in out
    assert out["Id_#text"] == "X1"


def test_apply_rules_list_json_text_and_compile_passthrough():
    compiled = compile_rules('{"x": "$First"}')
    assert compile_rules(compiled) is compiled
    assert compiled.targets == ["x"]
    assert compiled(REC)["x"] == "Ada"
    assert apply_rules([REC, {"First": "Bob"}], compiled)[1]["x"] == "Bob"
    with pytest.raises(BODTransformError):
        compiled.apply(["not", "a", "dict"])  # type: ignore[arg-type]


def test_custom_separator():
    tr = TransformRules({"rules": {"A.Line.*.T": "$A.Line.*.Q"}}, separator=".")
    out = tr.apply({"A.Line.0.Q": "1", "A.Line.1.Q": "2"})
    assert out["A.Line.0.T"] == "1" and out["A.Line.1.T"] == "2"


# ------------------------------------------------------- repeated lines
def test_star_rules_per_repeated_line():
    rules = {
        "PurchaseOrder_PurchaseOrderLine_*_Label": {
            "concat": [
                "$PurchaseOrder_PurchaseOrderHeader_DisplayID",
                "$PurchaseOrder_PurchaseOrderLine_*_LineNumber",
            ],
            "sep": "/",
        },
        "PurchaseOrder_PurchaseOrderLine_*_Kind": {
            "if": {"path": "PurchaseOrder_PurchaseOrderLine_*_Quantity", "op": "gt", "value": 0},
            "then": {"case": "$PurchaseOrder_PurchaseOrderLine_*_Quantity_@unitCode",
                     "when": {"EA": "each", "KG": "weight"}},
            "else": "zero",
        },
    }
    rec = to_records(LINES_XML, "Sync", rules=rules)[0]
    assert rec["PurchaseOrder_PurchaseOrderLine_0_Label"] == "PO1/10"
    assert rec["PurchaseOrder_PurchaseOrderLine_1_Label"] == "PO1/20"
    assert rec["PurchaseOrder_PurchaseOrderLine_0_Kind"] == "each"
    assert rec["PurchaseOrder_PurchaseOrderLine_1_Kind"] == "zero"

    single = to_records(ONE_LINE_XML, "Sync", rules=rules)[0]
    assert single["PurchaseOrder_PurchaseOrderLine_Label"] == "PO1/10"
    assert single["PurchaseOrder_PurchaseOrderLine_Kind"] == "each"


def test_star_rule_with_no_matches_adds_nothing():
    out = apply_rules({"A": "1"}, {"Line_*_X": "$Line_*_Y"})
    assert out == {"A": "1"}


def test_star_template_and_two_stars():
    rec = {
        "O_L_0_S_0_V": "a", "O_L_0_S_1_V": "b", "O_L_1_S_0_V": "c",
    }
    out = apply_rules(rec, {"rules": {"O_L_*_S_*_W": {"template": "<{O_L_*_S_*_V}>"}}, "mode": "only"})
    assert out == {"O_L_0_S_0_W": "<a>", "O_L_0_S_1_W": "<b>", "O_L_1_S_0_W": "<c>"}


# ------------------------------------------------- converter integration
def test_to_json_ndjson_project_with_rules(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    rules = {
        "OrderRef": {"concat": ["PO-", f"${PO}_DocumentID_ID"]},
        "Currency": {"case": f"${PO}_ExtendedAmount_@currencyID",
                     "when": {"EUR": "Euro", "USD": "Dollar"}, "default": "Other"},
        "IsLarge": {"if": {"path": f"{PO}_ExtendedAmount", "op": "gt", "value": 1000},
                    "then": True, "else": False},
    }
    data = json.loads(to_json(xml, "Sync", rules=rules))
    assert data["OrderRef"] == "PO-PSU000049"
    assert data["Currency"] == "Euro"
    assert data["IsLarge"] is True
    assert data[f"{PO}_DisplayID"] == "PSU000049"  # merge mode keeps source

    line = json.loads(to_ndjson(xml, "Sync", rules={"rules": rules, "mode": "only"}))
    assert set(line) == {"OrderRef", "Currency", "IsLarge"}

    hdr = json.loads(
        to_ndjson(xml, "Sync", include_header=True, rules={"E": "$Sync_AccountingEntityID"})
    )
    assert hdr["E"] == "3555" and "ApplicationArea_BODID" in hdr

    items = project(
        xml,
        "Sync",
        schema={"ref": "OrderRef", "label": "{OrderRef}:{Currency}"},
        rules=rules,
    )
    assert items == [{"ref": "PO-PSU000049", "label": "PO-PSU000049:Euro"}]


def test_header_fields_with_rules(xml_loader):
    xml = xml_loader.load("sync_PO_PSU000049.xml")
    rules = {"Company": {"template": "company[{Sync_AccountingEntityID}]"}}
    rec = BODConverter().to_records(xml, "Sync", include_header=True, rules=rules)[0]
    assert rec["Company"] == "company[3555]"


def test_invalid_rules_raise_even_without_raise_on_error():
    with pytest.raises(BODTransformError):
        to_json("<x/>", "Sync", rules={"a": {"bogus": 1}})


def test_rules_from_example_file(xml_loader):
    path = Path(__file__).parent.parent / "examples" / "rules_purchase_order.json"
    xml = xml_loader.load("sync_PO_PSU000050.xml")
    rec = to_records(xml, "Sync", include_header=True, rules=path.read_text())[0]
    assert rec["orderReference"] == "PO-PSU000050"
    assert rec["company"] == "company[3555]"


# ------------------------------------------------------------ validation
@pytest.mark.parametrize(
    "config, message",
    [
        ("not json", "not valid JSON"),
        ("[1, 2]", "JSON object"),
        ({"rules": {}, "mode": "weird"}, "mode"),
        ({"rules": {}, "drop": "x"}, "drop"),
        ({"rules": {}, "extra": 1}, "Unknown top-level"),
        ({"": "$a"}, "non-empty"),
        ({"a": ["$x"]}, "Lists are not expressions"),
        ({"a": {"concat": ["$x"], "path": "y"}}, "exactly one operator"),
        ({"a": {}}, "exactly one operator"),
        ({"a": {"concat": "x"}}, "needs a list"),
        ({"a": {"concat": [], "sep": 1}}, "'sep'"),
        ({"a": {"concat": [], "skip_empty": "no"}}, "'skip_empty'"),
        ({"a": {"concat": [], "bogus": 1}}, "does not accept"),
        ({"a": {"template": 1}}, "needs a string"),
        ({"a": {"template": "{A_x*}"}}, "whole segment"),
        ({"a": {"if": []}}, "empty"),
        ({"a": {"if": [{"when": True}]}}, "Each 'if' branch"),
        ({"a": {"if": [{"when": True, "then": 1}], "then": 2}}, "inside each branch"),
        ({"a": {"case": "$x"}}, "'when'"),
        ({"a": {"case": "$x", "when": [{"match": 1}]}}, "Each 'case' branch"),
        ({"a": {"case": "$x", "when": {}, "ignore_case": 1}}, "ignore_case"),
        ({"a": {"replace": "$x", "old": ""}}, "'old'"),
        ({"a": {"replace": "$x", "old": "a", "new": 1}}, "'new'"),
        ({"a": {"substr": "$x", "start": "1"}}, "integer"),
        ({"a": {"substr": "$x", "end": True}}, "integer"),
        ({"a": "$"}, "non-empty"),
        ({"a": "$*_x"}, "cannot start"),
        ({"a": {"path": 3}}, "non-empty string"),
        ({"a": {"if": "First", "then": 1}}, r"'\$path'"),
        ({"a": {"if": 3, "then": 1}}, "condition must be"),
        ({"a": {"if": {"all": "x"}, "then": 1}}, "'all'"),
        ({"a": {"if": {"not": True, "x": 1}, "then": 1}}, "'not'"),
        ({"a": {"if": {"path": "x", "bogus": 1}, "then": 1}}, "Unknown condition"),
        ({"a": {"if": {"op": "eq", "value": 1}, "then": 1}}, "exactly one of"),
        ({"a": {"if": {"path": "x", "op": "gt"}, "then": 1}}, "needs a 'value'"),
        ({"a": {"if": {"path": "x", "op": "in", "value": "a"}, "then": 1}}, "list 'value'"),
        ({"a": {"if": {"path": "x", "op": "regex", "value": "a"}, "then": 1}}, "Unknown operator"),
        ({"a": {"if": {"path": "x", "op": 5, "value": "a"}, "then": 1}}, "'op' must be"),
        ({"a": {"if": {"path": "x", "value": 1, "ignore_case": "y"}, "then": 1}}, "ignore_case"),
        ({"a": object()}, "Unsupported expression"),
        ({"L_*_x": "$y"}, "needs at least one"),
        ({"L_x": "$L_*_y"}, "'*' segment"),
    ],
)
def test_invalid_rule_definitions(config, message):
    with pytest.raises(BODTransformError, match=message):
        TransformRules(config)


def test_rule_depth_and_count_limits(monkeypatch):
    expr = "$x"
    for _ in range(70):
        expr = {"upper": expr}
    with pytest.raises(BODTransformError, match="deeper"):
        TransformRules({"a": expr})
    cond = True
    for _ in range(70):
        cond = {"not": cond}
    with pytest.raises(BODTransformError, match="deeper"):
        TransformRules({"a": {"if": cond, "then": 1}})

    import BODtoJSON.transforms as t

    monkeypatch.setattr(t, "MAX_RULES", 1)
    with pytest.raises(BODTransformError, match="Too many"):
        TransformRules({"a": 1, "b": 2})


def test_empty_separator_rejected():
    with pytest.raises(BODTransformError):
        TransformRules({"a": 1}, separator="")


def test_no_eval_or_exec_in_source():
    import re

    src_dir = Path(__file__).parent.parent / "src" / "BODtoJSON"
    for name in ("transforms.py", "reverse.py"):
        src = (src_dir / name).read_text()
        for token in ("eval", "exec", "compile", "__import__", "getattr"):
            assert not re.search(rf"(?<![\w.]){token}\(", src), (name, token)
