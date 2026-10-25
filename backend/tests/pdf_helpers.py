"""test_attachment_service.py／test_api_attachment.pyで共通して使うPDF生成処理
（CLAUDE.md DRYの原則。ai_context_helpers.pyと同じ位置づけ）。

pypdfはPDFの読み取り専用で作成機能を持たないため、xrefオフセットを正しく計算した
最小構成のPDF（1ページ、Helveticaでtextを描画）をバイト列として直接組み立てる。
"""


def build_minimal_pdf(text: str) -> bytes:
    content_stream = f"BT /F1 24 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>"
        b"/MediaBox[0 0 300 300]/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length " + str(len(content_stream)).encode() + b">>\nstream\n"
        + content_stream
        + b"\nendstream",
    ]

    chunks: list[bytes] = [b"%PDF-1.4\n"]
    offset = len(chunks[0])
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(offset)
        chunk = f"{i} 0 obj".encode() + body + b"endobj\n"
        chunks.append(chunk)
        offset += len(chunk)

    xref_offset = offset
    xref_chunks: list[bytes] = [b"xref\n", f"0 {len(objects) + 1}\n".encode(), b"0000000000 65535 f \n"]
    for entry_offset in offsets:
        xref_chunks.append(f"{entry_offset:010d} 00000 n \n".encode())
    xref_chunks.append(b"trailer\n")
    xref_chunks.append(f"<</Size {len(objects) + 1}/Root 1 0 R>>\n".encode())
    xref_chunks.append(b"startxref\n")
    xref_chunks.append(f"{xref_offset}\n".encode())
    xref_chunks.append(b"%%EOF")

    return b"".join(chunks) + b"".join(xref_chunks)


def build_pdf_without_text() -> bytes:
    """テキストを一切持たないPDF（画像のみのページ等を模す、A4）。"""
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/Resources<<>>/MediaBox[0 0 300 300]>>",
    ]
    chunks: list[bytes] = [b"%PDF-1.4\n"]
    offset = len(chunks[0])
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(offset)
        chunk = f"{i} 0 obj".encode() + body + b"endobj\n"
        chunks.append(chunk)
        offset += len(chunk)

    xref_offset = offset
    xref_chunks: list[bytes] = [b"xref\n", f"0 {len(objects) + 1}\n".encode(), b"0000000000 65535 f \n"]
    for entry_offset in offsets:
        xref_chunks.append(f"{entry_offset:010d} 00000 n \n".encode())
    xref_chunks.append(b"trailer\n")
    xref_chunks.append(f"<</Size {len(objects) + 1}/Root 1 0 R>>\n".encode())
    xref_chunks.append(b"startxref\n")
    xref_chunks.append(f"{xref_offset}\n".encode())
    xref_chunks.append(b"%%EOF")

    return b"".join(chunks) + b"".join(xref_chunks)
