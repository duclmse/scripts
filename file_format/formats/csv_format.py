"""CSV format — reads/writes comma-separated values with auto-delimiter detection"""

import csv
from typing import Iterator

from file_format.base import FileFormat, Record


class CSVFormat(FileFormat, format_name="csv", file_extensions=(".csv",)):
    def __init__(self, delimiter: str | None = None, encoding: str = "utf-8"):
        self.delimiter = delimiter
        self.encoding = encoding

    def _sniff_delimiter(self, f) -> str:
        sample = f.readline()
        f.seek(0)
        try:
            return csv.Sniffer().sniff(sample).delimiter
        except csv.Error:
            return ","

    def read(self, source: str) -> Iterator[Record]:
        with open(source, "r", encoding=self.encoding, newline="") as f:
            delimiter = self.delimiter or self._sniff_delimiter(f)
            reader = csv.DictReader(f, delimiter=delimiter)
            yield from reader

    def write(self, records: Iterator[Record], destination: str) -> int:
        count = 0
        rows = list(records)
        if not rows:
            return 0
        delimiter = self.delimiter or ","
        with open(destination, "w", encoding=self.encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
            count = len(rows)
        return count
