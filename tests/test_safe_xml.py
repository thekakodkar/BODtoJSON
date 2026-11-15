"""Direct tests for the stdlib-only hardened XML parser."""
from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from BODtoJSON.safe_xml import SafeXMLError, parse_xml

SECRET = Path("/tmp/bodtojson-2.4.0-secret.txt")
SAMPLES = Path(__file__).parent / "data"


@pytest.fixture(scope="module", autouse=True)
def _secret_file():
    SECRET.write_text("SECRET_SHOULD_NOT_LEAK\n", encoding="utf-8")
    yield
    try:
        SECRET.unlink()
    except OSError:
        pass


def _must_reject(source, **kwargs):
    with pytest.raises(SafeXMLError) as exc:
        parse_xml(source, **kwargs)
    text = str(exc.value)
    assert "SECRET_SHOULD_NOT_LEAK" not in text
    return text


def test_samples_parse():
    for name in ("sync_PO_PSU000049.xml", "sync_PO_PSU000050.xml"):
        root = parse_xml((SAMPLES / name).read_text())
        display = None
        for el in root.iter():
            local = el.tag.split("}", 1)[-1] if "}" in el.tag else el.tag
            if local == "DisplayID" and el.text:
                display = el.text
                break
        assert display and display.startswith("PSU")


def test_xxe_file_entity_rejected():
    xml = f"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO [ <!ENTITY xxe SYSTEM "file://{SECRET}"> ]>
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>&xxe;</Note></PO></DataArea></SyncPO>"""
    _must_reject(xml)


def test_external_dtd_rejected():
    xml = f"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO SYSTEM "file://{SECRET}">
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>ok</Note></PO></DataArea></SyncPO>"""
    _must_reject(xml)


def test_billion_laughs_rejected():
    entities = ['<!ENTITY e0 "AAAAAAAAAA">']
    for i in range(1, 6):
        entities.append(f'<!ENTITY e{i} "{("&e" + str(i - 1) + ";") * 10}">')
    xml = f"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO [ {''.join(entities)} ]>
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>&e5;</Note></PO></DataArea></SyncPO>"""
    msg = _must_reject(xml)
    assert "DOCTYPE" in msg or "ENTITY" in msg or "Entity" in msg


def test_quadratic_blowup_rejected():
    chunk = "B" * 10000
    refs = "&q;" * 200
    xml = f"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO [ <!ENTITY q "{chunk}"> ]>
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>{refs}</Note></PO></DataArea></SyncPO>"""
    _must_reject(xml)


def test_param_entity_rejected():
    xml = f"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO [
      <!ENTITY % pe SYSTEM "file://{SECRET}">
      %pe;
    ]>
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>ok</Note></PO></DataArea></SyncPO>"""
    _must_reject(xml)


def test_utf16_le_doctype_rejected():
    xml = """<?xml version="1.0" encoding="utf-16"?>
    <!DOCTYPE SyncPO [ <!ENTITY xxe SYSTEM "file:///tmp/nope"> ]>
    <SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><Note>&xxe;</Note></PO></DataArea></SyncPO>
    """.encode("utf-16")  # includes LE BOM
    _must_reject(xml)


def test_utf16_be_doctype_rejected():
    xml = """<?xml version="1.0"?>
    <!DOCTYPE SyncPO [ <!ENTITY e "AAAA"> ]>
    <SyncPO><DataArea><Sync/><PO><Note>&e;</Note></PO></DataArea></SyncPO>""".encode(
        "utf-16-be"
    )
    _must_reject(xml)


def test_utf32_le_doctype_rejected():
    xml = """<?xml version="1.0"?>
    <!DOCTYPE SyncPO [ <!ENTITY e "AAAA"> ]>
    <SyncPO><DataArea><Sync/><PO><Note>&e;</Note></PO></DataArea></SyncPO>""".encode(
        "utf-32-le"
    )
    _must_reject(xml)


def test_utf8_bom_doctype_rejected():
    xml = codecs_bom_doctype()
    _must_reject(xml)


def codecs_bom_doctype():
    return b"\xef\xbb\xbf" + (
        b"""<?xml version="1.0"?>
    <!DOCTYPE SyncPO [ <!ENTITY e "AAAA"> ]>
    <SyncPO><DataArea><Sync/><PO><Note>&e;</Note></PO></DataArea></SyncPO>"""
    )


def test_doctype_after_comment_rejected():
    _must_reject(
        '<?xml version="1.0"?><!-- comment --><!DOCTYPE r [ <!ENTITY e "A"> ]><r>&e;</r>'
    )


def test_size_and_depth_caps():
    with pytest.raises(SafeXMLError, match="maximum allowed size"):
        parse_xml("x" * 200, max_size=50)
    deep = "<L>leaf</L>"
    for _ in range(30):
        deep = f"<N>{deep}</N>"
    xml = f'<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO>{deep}</PO></DataArea></SyncPO>'
    with pytest.raises(SafeXMLError, match="depth"):
        parse_xml(xml, max_depth=10)
    root = parse_xml(xml, max_depth=256)
    assert "SyncPO" in root.tag


def test_valid_oagis_still_parses_after_attacks():
    xml = """<?xml version="1.0"?>
    <SyncPurchaseOrder xmlns="http://schema.infor.com/InforOAGIS/2">
      <DataArea>
        <Sync><AccountingEntityID>3555</AccountingEntityID></Sync>
        <PurchaseOrder><PurchaseOrderHeader><DisplayID>PO1</DisplayID></PurchaseOrderHeader></PurchaseOrder>
      </DataArea>
    </SyncPurchaseOrder>
    """
    root = parse_xml(xml)
    assert "SyncPurchaseOrder" in root.tag


def test_encode_needles_unknown_encoding():
    from BODtoJSON.safe_xml import _encode_needles

    assert _encode_needles("x", "not-a-real-encoding") == []


def test_raw_scan_clean_bytes_returns_false():
    from BODtoJSON.safe_xml import _raw_contains_forbidden

    assert _raw_contains_forbidden(b"<SyncPO><DataArea/></SyncPO>") is False


def test_detect_and_decode_encodings():
    from BODtoJSON.safe_xml import _decode, _detect_encoding

    body = '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><ID>Z</ID></PO></DataArea></SyncPO>'
    cases = {
        "utf-8-sig": (codecs.BOM_UTF8 + body.encode("utf-8"), "utf-8-sig"),
        "utf-16-le-bom": (codecs.BOM_UTF16_LE + body.encode("utf-16-le"), "utf-16-le"),
        "utf-16-be-bom": (codecs.BOM_UTF16_BE + body.encode("utf-16-be"), "utf-16-be"),
        "utf-32-le-bom": (codecs.BOM_UTF32_LE + body.encode("utf-32-le"), "utf-32-le"),
        "utf-32-be-bom": (codecs.BOM_UTF32_BE + body.encode("utf-32-be"), "utf-32-be"),
        "utf-16-le-no-bom": (body.encode("utf-16-le"), "utf-16-le"),
        "utf-16-be-no-bom": (body.encode("utf-16-be"), "utf-16-be"),
        "utf-32-le-no-bom": (body.encode("utf-32-le"), "utf-32-le"),
        "utf-32-be-no-bom": (body.encode("utf-32-be"), "utf-32-be"),
        "decl": (b'<?xml version="1.0" encoding="UTF-8"?>' + body.encode("utf-8"), "UTF-8"),
    }
    for name, (raw, expected) in cases.items():
        enc = _detect_encoding(raw)
        assert enc.lower().replace("-", "") == expected.lower().replace("-", "") or enc == expected, (
            name,
            enc,
            expected,
        )
        text = _decode(raw)
        assert "SyncPO" in text or "DataArea" in text


def test_decode_unicode_error():
    from BODtoJSON.safe_xml import SafeXMLError, _decode

    # Declaration claims utf-8 but payload is invalid utf-8
    raw = b'<?xml version="1.0" encoding="utf-8"?>\xff\xfe'
    with pytest.raises(SafeXMLError, match="Unable to decode"):
        _decode(raw)


def test_parse_string_with_bom_and_utf16_bytes():
    xml = "\ufeff" + '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><ID>G</ID></PO></DataArea></SyncPO>'
    root = parse_xml(xml)
    texts = [el.text for el in root.iter() if el.text]
    assert "G" in texts

    raw = '<SyncPO xmlns="http://ex.com"><DataArea><Sync/><PO><ID>H</ID></PO></DataArea></SyncPO>'.encode(
        "utf-16"
    )
    root = parse_xml(raw)
    texts = [el.text for el in root.iter() if el.text]
    assert "H" in texts


def test_expat_handlers_reject_dtd_and_entities():
    """Second-line expat handlers, bypassing the pre-scan."""
    from xml.etree.ElementTree import ParseError

    from BODtoJSON.safe_xml import _expat_parse

    with pytest.raises(SafeXMLError, match="DOCTYPE"):
        _expat_parse('<!DOCTYPE r [ <!ENTITY e "A"> ]><r>&e;</r>')

    with pytest.raises((SafeXMLError, ParseError)):
        _expat_parse("<not-closed>")


# Import codecs used by the new encoding tests.
