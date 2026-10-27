"""Upload validation.

Threats this guards against:
- Path traversal / odd filenames: the client-supplied name is reduced to a safe basename
  and never used to build a path on its own (files live under a server-generated ID).
- Disguised content: the extension must be allowlisted *and* the bytes must look like that
  type (``%PDF-`` magic for PDFs, valid UTF-8 text for TXT/MD). Client ``Content-Type`` is
  informational only; it is never trusted.
- Resource exhaustion: a hard size limit is enforced while streaming, before the whole
  body is held in memory or written to disk.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

# extension -> canonical content type we record
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

_MAX_FILENAME_LENGTH = 120
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_PDF_MAGIC = b"%PDF-"


class FileValidationError(ValueError):
    """The upload is not acceptable (bad type, name, or content)."""


class FileTooLargeError(FileValidationError):
    """The upload exceeds the configured size limit."""


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    safe_name: str
    extension: str
    content_type: str
    size_bytes: int


def safe_filename(original: str) -> str:
    """Reduce an untrusted filename to a safe basename.

    Strips directories (both separators), normalises unicode, replaces anything outside
    ``[A-Za-z0-9._-]`` with ``_``, removes leading dots (hidden files / ``..``), and caps
    the length while preserving the extension.
    """
    name = PureWindowsPath(PurePosixPath(original).name).name
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = _UNSAFE_CHARS.sub("_", name).strip("._ ")
    if not name:
        name = "upload"

    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    ext = f".{ext.lower()}" if ext else ""
    stem = stem[: _MAX_FILENAME_LENGTH - len(ext)] or "upload"
    return f"{stem}{ext}"


def _looks_like_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        # Allow a cut-off multibyte sequence at the end of a sample.
        try:
            data[:-3].decode("utf-8")
        except UnicodeDecodeError:
            return False
    return True


def validate_upload(
    *,
    filename: str | None,
    size_bytes: int,
    head: bytes,
    max_bytes: int,
) -> ValidatedUpload:
    """Validate an upload from its name, size and the first bytes of its content.

    ``head`` should be the first few KB of the file; it is only used for type sniffing.
    """
    if not filename or not filename.strip():
        raise FileValidationError("A filename is required.")

    name = safe_filename(filename)
    extension = PurePosixPath(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise FileValidationError(f"Unsupported file type '{extension}'. Allowed: {allowed}.")

    if size_bytes <= 0:
        raise FileValidationError("The uploaded file is empty.")
    if size_bytes > max_bytes:
        raise FileTooLargeError(
            f"File is {size_bytes} bytes; the limit is {max_bytes // (1024 * 1024)} MB."
        )

    if extension == ".pdf":
        if not head.startswith(_PDF_MAGIC):
            raise FileValidationError("File has a .pdf extension but is not a PDF.")
    elif not _looks_like_text(head):
        raise FileValidationError("Text files must be UTF-8 encoded text.")

    return ValidatedUpload(
        safe_name=name,
        extension=extension,
        content_type=ALLOWED_EXTENSIONS[extension],
        size_bytes=size_bytes,
    )
