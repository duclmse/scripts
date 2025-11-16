"""Import all format modules to trigger auto-registration in FormatRegistry"""

from file_format.formats.csv_format import CSVFormat
from file_format.formats.tsv_format import TSVFormat
from file_format.formats.json_format import JSONFormat
from file_format.formats.fixed_width import PositionText
from file_format.formats.sql_format import SQLFormat
from file_format.formats.yaml_format import YAMLFormat

__all__ = [
    "CSVFormat",
    "TSVFormat",
    "JSONFormat",
    "PositionText",
    "SQLFormat",
    "YAMLFormat"
]
