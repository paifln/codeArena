"""Validate bounded attachments without executing or rendering document content."""

import io
import re
import zipfile
from pathlib import PurePosixPath

MAX_DOCUMENT = 5 * 1024 * 1024


def validate_document(name, blob):
    name = re.sub(r"[\x00-\x1f\x7f/\\]", "_", name or "document")[:180]
    suffix = PurePosixPath(name.lower()).suffix
    if not blob or len(blob) > MAX_DOCUMENT:
        raise ValueError("Document must be between 1 byte and 5 MB")
    if suffix == ".pdf" and blob.startswith(b"%PDF-") and b"%%EOF" in blob[-2048:]:
        return name, "application/pdf"
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                items = archive.infolist()
                names = {i.filename for i in items}
                if (
                    len(items) > 500
                    or len(names) != len(items)
                    or sum(i.file_size for i in items) > 20 * 1024 * 1024
                ):
                    raise ValueError("DOCX archive exceeds limits")
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    raise ValueError("Invalid DOCX document")
                if any(
                    i.flag_bits & 1
                    or ".." in PurePosixPath(i.filename).parts
                    or i.filename.startswith("/")
                    or "\\" in i.filename
                    or "vbaproject" in i.filename.lower()
                    or i.filename.startswith("word/embeddings/")
                    for i in items
                ):
                    raise ValueError(
                        "Encrypted documents, macros and embedded objects are unsupported"
                    )
                # Verify CRCs inside the bounded archive; never extract files.
                if archive.testzip() is not None:
                    raise ValueError("Corrupt DOCX document")
                return (
                    name,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
            raise ValueError("Invalid DOCX document") from None
    raise ValueError("Upload a PDF or DOCX document")
