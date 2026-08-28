\
import re
import zipfile
from typing import List, Optional, Tuple, Dict

def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

def _rpr_times12(underline: bool = False) -> str:
    ul = '<w:u w:val="single"/>' if underline else ''
    return (
        '<w:rPr>'
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman"/>'
        '<w:sz w:val="24"/><w:szCs w:val="24"/>'
        f'{ul}'
        '</w:rPr>'
    )

def _ppr(line_rule: str, line_twips: int, first_line_twips: int = 0) -> str:
    ind = f'<w:ind w:firstLine="{first_line_twips}"/>' if first_line_twips else ''
    return (
        '<w:pPr>'
        f'<w:spacing w:line="{line_twips}" w:lineRule="{line_rule}"/>'
        f'{ind}'
        '</w:pPr>'
    )

def _run_with_tabs(text: str, underline: bool) -> str:
    # Convert \t into <w:tab/>
    parts = text.split("\t")
    out = []
    for i, part in enumerate(parts):
        if part:
            out.append(f'<w:r>{_rpr_times12(underline)}<w:t xml:space="preserve">{_xml_escape(part)}</w:t></w:r>')
        if i != len(parts) - 1:
            out.append('<w:r>' + _rpr_times12(False) + '<w:tab/></w:r>')
    return "".join(out)

def _p_text_with_underline_phrase(text: str, phrase: str, ppr_xml: str) -> str:
    if text == "":
        return f"<w:p>{ppr_xml}</w:p>"

    if not phrase:
        return f"<w:p>{ppr_xml}{_run_with_tabs(text, False)}</w:p>"

    # underline every occurrence, case-insensitive
    pattern = re.compile(re.escape(phrase), re.IGNORECASE)
    pos = 0
    runs = []
    for m in pattern.finditer(text):
        if m.start() > pos:
            runs.append((text[pos:m.start()], False))
        runs.append((text[m.start():m.end()], True))
        pos = m.end()
    if pos < len(text):
        runs.append((text[pos:], False))

    run_xml = []
    for seg, ul in runs:
        if seg:
            run_xml.append(_run_with_tabs(seg, ul))
    return f"<w:p>{ppr_xml}{''.join(run_xml)}</w:p>"

def write_docx_paragraphs(out_path: str, paragraphs: List[Dict], underline_phrase: str = ""):
    """
    paragraphs: list of dicts:
      {"text": "...", "double": True/False, "indent_first": True/False}
    """
    body_parts = []
    for p in paragraphs:
        text = p.get("text", "")
        double = bool(p.get("double", True))
        indent_first = bool(p.get("indent_first", False))

        # line spacing in twips
        # single approx 240, double approx 480
        line_twips = 480 if double else 240
        ppr_xml = _ppr("auto", line_twips, first_line_twips=720 if indent_first else 0)

        body_parts.append(_p_text_with_underline_phrase(text, underline_phrase, ppr_xml))

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {''.join(body_parts)}
    <w:sectPr/>
  </w:body>
</w:document>
"""

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>
"""

    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>
"""

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
