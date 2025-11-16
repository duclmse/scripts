"""Fixed-width (positional) flat file format"""

from typing import Any, Iterator

from file_format.base import FileFormat, Record
from file_format.value_converter import ValueConverter


class PositionText(FileFormat, format_name="fixed_width", file_extensions=(".txt", ".dat")):
    """
    Reads fixed-width flat files where each field occupies a fixed column range.

    Example:
        pt = PositionText("id,name,age", "1-4, 5-20, 21-23")
        for record in pt.read("data.txt"):
            print(record)
    """

    def __init__(
        self,
        field_names: list[str] | str,
        field_positions: list[str] | str,
        encoding: str = "utf-8",
    ):
        self.field_names = self._parse_field_names(field_names)
        self.field_ranges = self._parse_positions(field_positions)
        self.encoding = encoding

        if len(self.field_names) != len(self.field_ranges):
            raise ValueError(
                f"Field names ({len(self.field_names)}) must match "
                f"field positions ({len(self.field_ranges)})"
            )

    # -- Class factories --

    @classmethod
    def from_definition_files(
        cls, header_file: str, positions_file: str, encoding: str = "utf-8"
    ) -> "PositionText":
        with open(header_file, "r", encoding=encoding) as f:
            field_names = f.read().strip()
        with open(positions_file, "r", encoding=encoding) as f:
            field_positions = f.read().strip()
        return cls(field_names, field_positions, encoding)

    @classmethod
    def from_definition_strings(cls, header_string: str, positions_string: str) -> "PositionText":
        return cls(header_string, positions_string)

    # -- FileFormat interface --

    def read(self, source: str) -> Iterator[Record]:
        with open(source, "r", encoding=self.encoding) as f:
            for line in f:
                line = line.rstrip("\n\r")
                yield self.parse_line(line)

    def write(self, records: Iterator[Record], destination: str) -> int:
        """Write records as fixed-width lines padded to field widths."""
        widths = [end - start for start, end in self.field_ranges]
        count = 0
        with open(destination, "w", encoding=self.encoding) as f:
            for record in records:
                parts = []
                for name, width in zip(self.field_names, widths):
                    value = str(record.get(name, ""))
                    parts.append(value[:width].ljust(width))
                f.write("".join(parts) + "\n")
                count += 1
        return count

    # -- Parsing helpers --

    def parse_line(self, line: str) -> Record:
        """Parse a single fixed-width line into a dict, inferring value types."""
        record: Record = {}
        for field_name, (start, end) in zip(self.field_names, self.field_ranges):
            raw = line[start:end].strip() if len(line) > start else ""
            record[field_name] = ValueConverter.infer(raw)
        return record

    def _parse_field_names(self, field_names: list[str] | str) -> list[str]:
        if isinstance(field_names, str):
            return [n.strip() for n in field_names.split(",")]
        return list(field_names)

    def _parse_positions(self, positions: list[str] | str) -> list[tuple[int, int]]:
        """Parse '1-8, 9-12' into [(0, 8), (8, 12)] (0-based, end-exclusive)."""
        if isinstance(positions, str):
            position_list = [p.strip() for p in positions.split(",")]
        else:
            position_list = list(positions)

        ranges = []
        for pos in position_list:
            try:
                start_str, end_str = pos.strip().split("-")
                start = int(start_str) - 1  # 1-based → 0-based
                end = int(end_str)          # inclusive end → exclusive slice end
                ranges.append((start, end))
            except ValueError:
                raise ValueError(f"Invalid position format '{pos}'. Expected 'start-end'.")
        return ranges
