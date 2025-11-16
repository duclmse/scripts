"""FlatFileProcessor — conversion engine between any two FileFormat instances"""

from core.logger import Logger
from file_format.base import FileFormat
from file_format.value_converter import ValueConverter


class FlatFileProcessor:
    """
    Converts files between any two registered FileFormat types.

    Example:
        from file_format.formats.fixed_width import PositionText
        from file_format.formats.json_format import JSONFormat

        processor = FlatFileProcessor(
            PositionText("id,name", "1-4, 5-20"),
            JSONFormat()
        )
        processor.process_file("data.txt", "output.json")
    """

    def __init__(self, input_format: FileFormat, output_format: FileFormat):
        self.input_format = input_format
        self.output_format = output_format

    def process_file(self, input_path: str, output_path: str) -> int:
        """
        Stream records from input_path via input_format and write to output_path
        via output_format. Returns the number of records processed.
        """
        Logger.info(f"Converting {input_path} → {output_path}")
        Logger.info(
            f"  {self.input_format.describe()} → {self.output_format.describe()}"
        )
        records = self.input_format.read(input_path)
        count = self.output_format.write(records, output_path)
        Logger.info(f"Done — {count} records written to {output_path}")
        return count

    # Backward compat: old callers used FlatFileProcessor._convert_value()
    def _convert_value(self, value: str) -> int | float | str | None:
        return ValueConverter.infer(value)
