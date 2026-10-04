from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .._http import HttpClient


@dataclass(frozen=True)
class ParsedFile:
    """A file's text from POST /v1/files/parse. Nothing is stored.

    Images and scanned PDF pages are transcribed through the workspace's
    model routing on paid plans; transcribed_pages lists which.
    """

    file_name: str
    format: str
    text: str
    warnings: List[str]
    pages: Optional[int] = None
    transcribed_pages: Optional[List[int]] = None
    textless_pages: Optional[List[int]] = None

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "ParsedFile":
        return cls(
            file_name=data["file_name"],
            format=data["format"],
            text=data["text"],
            warnings=data.get("warnings", []),
            pages=data.get("pages"),
            transcribed_pages=data.get("transcribed_pages"),
            textless_pages=data.get("textless_pages"),
        )


class FilesResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def parse(self, *, file_name: str, file_base64: str) -> ParsedFile:
        """Return a file's text without storing it. file_base64 may be a data: URL; max 15 MB decoded.

        Workflow runs can take files directly instead: pass
        {"file_name": ..., "file_base64": ...} entries in input["attachments"].
        """
        data = self._http.post("/v1/files/parse", {"file_name": file_name, "file_base64": file_base64})
        return ParsedFile._from_dict(data)
