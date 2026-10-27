"""Test helpers."""


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    """Build a minimal but valid multi-page PDF with one line of Helvetica text per page.

    Written by hand so tests do not depend on a PDF-authoring library. pypdf extracts the
    text from the ``Tj`` operators, which is enough to exercise per-page loading.
    """
    objects: list[bytes] = []

    def add(body: str) -> int:
        objects.append(body.encode("latin-1"))
        return len(objects)  # 1-based object number

    font_obj = 1 + 2 + 2 * len(pages)  # allocated after catalog, pages tree and page objs
    add("<< /Type /Catalog /Pages 2 0 R >>")
    pages_obj_index = add("PLACEHOLDER")  # filled once kid numbers are known

    kids: list[int] = []
    for text in pages:
        page_num = len(objects) + 1
        content_num = page_num + 1
        kids.append(page_num)
        add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_num} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>"
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({_pdf_escape(text)}) Tj ET"
        add(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")

    assert add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>") == font_obj
    kids_ref = " ".join(f"{k} 0 R" for k in kids)
    objects[pages_obj_index - 1] = (
        f"<< /Type /Pages /Kids [{kids_ref}] /Count {len(kids)} >>".encode("latin-1")
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("latin-1") + body + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("latin-1")
    out += f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    return bytes(out)
