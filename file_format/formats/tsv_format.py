"""TSV format — tab-separated values (subclass of CSVFormat)"""

from file_format.formats.csv_format import CSVFormat


class TSVFormat(CSVFormat, format_name="tsv", file_extensions=(".tsv",)):
    def __init__(self, encoding: str = "utf-8"):
        super().__init__(delimiter="\t", encoding=encoding)
