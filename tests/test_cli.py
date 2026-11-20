"""Command-line interface (python -m BODtoJSON / bodtojson)."""

import io
import json
import runpy
import sys
from pathlib import Path

import pytest

from BODtoJSON import to_records
from BODtoJSON.cli import main

DATA = Path(__file__).parent / "data"
EXAMPLES = Path(__file__).parent.parent / "examples"
XML = DATA / "sync_PO_PSU000049.xml"


def test_to_json_default_and_indent(capsys):
    assert main(["to-json", str(XML)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["PurchaseOrder_PurchaseOrderHeader_DisplayID"] == "PSU000049"
    assert main(["to-json", str(XML), "--indent", "2"]) == 0
    assert capsys.readouterr().out.startswith("{\n  ")


def test_to_json_with_rules_ndjson_records(tmp_path, capsys):
    rules = EXAMPLES / "rules_purchase_order.json"
    assert main(["to-json", str(XML), "--format", "ndjson", "--include-header",
                 "--rules", str(rules)]) == 0
    line = json.loads(capsys.readouterr().out)
    assert line["orderReference"] == "PO-PSU000049"
    assert "ApplicationArea_BODID" not in line  # dropped by the example rules

    out = tmp_path / "recs.json"
    assert main(["to-json", str(XML), "--format", "records", "-o", str(out)]) == 0
    assert json.loads(out.read_text())[0]["PurchaseOrder_PurchaseOrderHeader_DisplayID"]


def test_round_trip_through_files(tmp_path):
    recs = tmp_path / "recs.json"
    xml_out = tmp_path / "out.xml"
    assert main(["to-json", str(XML), "--format", "records", "--include-header",
                 "-o", str(recs)]) == 0
    assert main(["to-bod", str(recs), "-o", str(xml_out), "--version-id", "2.14.x"]) == 0
    original = to_records(XML.read_text(), "Sync", include_header=True)
    assert to_records(xml_out.read_text(), "Sync", include_header=True) == original


def test_to_bod_stdin_options(monkeypatch, capsys):
    payload = json.dumps({"PurchaseOrderHeader_DisplayID": "P9"}).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload)))
    assert main(["to-bod", "-", "--noun", "PurchaseOrder", "--action-code", "Replace",
                 "--namespace", "", "--release-id", "", "--no-application-area",
                 "--compact", "--root", "SyncPO"]) == 0
    out = capsys.readouterr().out
    assert out.startswith('<?xml version="1.0" encoding="UTF-8"?><SyncPO><DataArea>')
    assert '<ActionExpression actionCode="Replace"/>' in out


def test_to_bod_with_reverse_rules(capsys):
    assert main(["to-bod", str(EXAMPLES / "order.json"), "--noun", "PurchaseOrder",
                 "--rules", str(EXAMPLES / "rules_json_to_bod.json")]) == 0
    assert "<ID>PO-1001</ID>" in capsys.readouterr().out


def test_errors_return_1(tmp_path, capsys):
    bad = tmp_path / "bad.xml"
    bad.write_text("<not-closed>")
    assert main(["to-json", str(bad)]) == 1
    assert "bodtojson: error:" in capsys.readouterr().err
    assert main(["to-json", str(tmp_path / "missing.xml")]) == 1
    rules = tmp_path / "rules.json"
    rules.write_text('{"a": {"if": {"bogus": ["x", 1]}, "then": 1}}')
    assert main(["to-json", str(XML), "--rules", str(rules)]) == 1


def test_usage_errors_exit_2():
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_to_json_with_template_rules(capsys):
    tpl = EXAMPLES / "ion_purchase_order_template.json"
    lines = DATA / "sync_PO_lines.xml"
    assert main(["to-json", str(lines), "--rules", str(tpl)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list) and len(out[0]["purchaseOrderLines"]) == 3
    assert main(["to-json", str(XML), "--rules", str(tpl), "--single", "--missing-empty",
                 "--indent", "2"]) == 0
    single = json.loads(capsys.readouterr().out)
    assert single["supplier"] == "" and single["purchaseOrderLines"] == []


def test_to_json_detects_verb(tmp_path, capsys):
    proc = tmp_path / "p.xml"
    proc.write_text(XML.read_text().replace("<Sync>", "<Process>").replace("</Sync>", "</Process>"))
    assert main(["to-json", str(proc), "--format", "records", "--include-header"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["Process_TenantID"] == "TEST_TST"


def test_python_dash_m(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["bodtojson", "--version"])
    with pytest.raises(SystemExit) as e:
        runpy.run_module("BODtoJSON", run_name="__main__")
    assert e.value.code == 0
    assert "bodtojson 2." in capsys.readouterr().out
