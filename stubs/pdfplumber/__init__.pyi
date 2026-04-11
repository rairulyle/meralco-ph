from contextlib import AbstractContextManager
from typing import IO

class Page:
    def extract_tables(self) -> list[list[list[str | None]]]: ...
    def extract_text(self) -> str | None: ...

class PDF(AbstractContextManager["PDF"]):
    pages: list[Page]
    def __enter__(self) -> "PDF": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None: ...

def open(path_or_fp: str | IO[bytes]) -> PDF: ...
