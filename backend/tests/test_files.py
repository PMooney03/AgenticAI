import pytest

from app.security import (
    FileTooLargeError,
    FileValidationError,
    safe_filename,
    validate_upload,
)

MB = 1024 * 1024


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32\\notes.txt", "notes.txt"),
        ("C:\\Users\\me\\Q3 Results (final).PDF", "Q3_Results_final_.pdf"),
        (".hidden.md", "hidden.md"),
        ("...", "upload"),
        ("", "upload"),
        ("caf\u00e9 r\u00e9sum\u00e9.txt", "cafe_resume.txt"),
        ("weird\x00name.txt", "weird_name.txt"),
    ],
)
def test_safe_filename(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected


def test_safe_filename_caps_length_but_keeps_extension() -> None:
    name = safe_filename("a" * 500 + ".pdf")
    assert len(name) <= 120
    assert name.endswith(".pdf")


def test_validate_accepts_pdf_with_magic() -> None:
    result = validate_upload(
        filename="doc.pdf", size_bytes=1000, head=b"%PDF-1.7 ...", max_bytes=MB
    )
    assert result.content_type == "application/pdf"
    assert result.safe_name == "doc.pdf"


def test_validate_accepts_utf8_text_and_markdown() -> None:
    txt = validate_upload(filename="n.txt", size_bytes=5, head=b"hello", max_bytes=MB)
    md = validate_upload(filename="n.md", size_bytes=7, head="# caf\u00e9".encode(), max_bytes=MB)
    assert txt.content_type == "text/plain"
    assert md.content_type == "text/markdown"


def test_validate_rejects_disallowed_extension() -> None:
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        validate_upload(filename="malware.exe", size_bytes=10, head=b"MZ", max_bytes=MB)


def test_validate_rejects_pdf_extension_without_pdf_content() -> None:
    with pytest.raises(FileValidationError, match="not a PDF"):
        validate_upload(filename="fake.pdf", size_bytes=10, head=b"MZ\x90\x00", max_bytes=MB)


def test_validate_rejects_binary_disguised_as_text() -> None:
    with pytest.raises(FileValidationError, match="UTF-8"):
        validate_upload(filename="x.txt", size_bytes=10, head=b"\x00\x01\x02", max_bytes=MB)


def test_validate_rejects_empty_and_oversized() -> None:
    with pytest.raises(FileValidationError, match="empty"):
        validate_upload(filename="x.txt", size_bytes=0, head=b"", max_bytes=MB)
    with pytest.raises(FileTooLargeError):
        validate_upload(filename="x.txt", size_bytes=MB + 1, head=b"a", max_bytes=MB)


def test_validate_requires_filename() -> None:
    with pytest.raises(FileValidationError, match="filename"):
        validate_upload(filename=None, size_bytes=1, head=b"a", max_bytes=MB)
