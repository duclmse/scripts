"""JSON format — reads/writes a JSON array of objects"""

import json
from typing import Iterator

from file_format.base import FileFormat, Record


class JSONFormat(FileFormat, format_name="json", file_extensions=(".json",)):
    def __init__(self, indent: int | None = 2, encoding: str = "utf-8"):
        self.indent = indent
        self.encoding = encoding

    def read(self, source: str) -> Iterator[Record]:
        with open(source, "r", encoding=self.encoding) as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON array at top level, got {type(data).__name__}")
        yield from data

    def write(self, records: Iterator[Record], destination: str) -> int:
        rows = list(records)
        with open(destination, "w", encoding=self.encoding) as f:
            json.dump(rows, f, indent=self.indent, ensure_ascii=False)
        return len(rows)
