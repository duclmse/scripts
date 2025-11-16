"""
file_format — convert between text file formats.

Supported formats (auto-detected by file extension):
  csv, tsv, json, yaml/yml, sql (write-only), fixed_width / .txt / .dat

Usage:
    from file_format import FlatFileProcessor, CSVFormat, JSONFormat

    processor = FlatFileProcessor(CSVFormat(), JSONFormat())
    processor.process_file("data.csv", "output.json")

CLI:
    python -m file_format data.csv output.json
    python -m file_format data.txt output.csv --input-format fixed_width \\
        --field-names "id,name" --field-positions "1-4,5-20"
"""

# Import formats first so all classes register themselves
from file_format import formats as formats  # noqa: F401

from file_format.base import FileFormat, FormatRegistry, Record
from file_format.processor import FlatFileProcessor
from file_format.value_converter import ValueConverter
from file_format.formats import (
    CSVFormat,
    TSVFormat,
    JSONFormat,
    PositionText,
    SQLFormat,
    YAMLFormat,
)

__all__ = [
    "FileFormat",
    "FormatRegistry",
    "FlatFileProcessor",
    "ValueConverter",
    "Record",
    "CSVFormat",
    "TSVFormat",
    "JSONFormat",
    "PositionText",
    "SQLFormat",
    "YAMLFormat",
]
