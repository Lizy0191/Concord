import hashlib
from pathlib import Path

from app.domain.errors import DomainError
from app.domain.models import new_id
from app.ports.providers import DocumentChunk


class LightweightDocumentParser:
    def parse(self, content: bytes, filename: str) -> list[DocumentChunk]:
        if Path(filename).suffix.lower() not in {".txt", ".md", ".csv", ".log"}:
            raise DomainError(
                "Lightweight parser accepts text/Markdown/CSV/log only. "
                "Enable Docling for complex documents."
            )
        if len(content) > 1024 * 1024:
            raise DomainError("Lightweight text import is limited to 1 MiB")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DomainError("Text import requires UTF-8") from exc
        digest = hashlib.sha256(content).hexdigest()
        chunks = []
        for page_number, page in enumerate(text.split("\f"), start=1):
            for offset in range(0, len(page), 1600):
                snippet = page[offset : offset + 1600].strip()
                if snippet:
                    chunks.append(
                        DocumentChunk(
                            id=new_id(),
                            text=snippet,
                            page=page_number,
                            location=f"characters {offset}-{offset + len(snippet)}",
                            source_hash=digest,
                            parser="lightweight/1",
                        )
                    )
        if not chunks:
            raise DomainError("Document contains no readable text")
        return chunks
