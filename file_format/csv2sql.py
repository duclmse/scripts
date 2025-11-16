#!/usr/bin/env python3
"""
CSV to SQL Converter Script

This script converts CSV data to SQL INSERT statements with automatic data type detection.
Supports various CSV formats and provides options for table creation and data insertion.
"""

import csv
import re
import traceback
import sys
from typing import List, Dict, Any, Optional
import argparse


class CSVToSQLConverter:
    def __init__(self, table_name: str = "your_table_name"):
        self.table_name = table_name
        self.column_types = {}

    def detect_data_type(self, value: str) -> str:
        """Detect SQL data type based on value content."""
        if not value or value.upper() == "NULL":
            return "VARCHAR(255)"  # Default for NULL values

        # Integer
        if re.match(r"^-?\d+$", value):
            return "INT"

        # Float/Decimal
        if re.match(r"^-?\d+\.\d+$", value):
            return "DECIMAL(10,4)"

        # Date (YYYY-MM-DD)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return "DATE"

        # DateTime (various formats)
        datetime_patterns = [
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",  # YYYY-MM-DD HH:MM:SS
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO format
        ]
        for pattern in datetime_patterns:
            if re.match(pattern, value):
                return "DATETIME"

        # Boolean-like values
        if value.upper() in ["TRUE", "FALSE", "T", "F", "Y", "N", "YES", "NO"]:
            return "CHAR(1)"

        # Default to VARCHAR with dynamic length
        # Dynamic sizing with limits
        length = min(max(len(value) * 2, 50), 1000)
        return f"VARCHAR({length})"

    def determine_column_types(self, rows: List[Dict[str, Any]]) -> Dict[str, str]:
        """Analyze all rows to determine the best data type for each column."""
        column_types = {}

        for column in rows[0].keys():
            types_found = set()
            max_length = 0

            for row in rows:
                value = str(row[column]).strip(
                ) if row[column] is not None else "NULL"
                if value and value.upper() != "NULL":
                    data_type = self.detect_data_type(value)
                    types_found.add(data_type)
                    if "VARCHAR" in data_type:
                        max_length = max(max_length, len(value))

            # Prioritize data types (most specific first)
            if any("DATETIME" in t for t in types_found):
                column_types[column] = "DATETIME"
            elif any("DATE" in t for t in types_found):
                column_types[column] = "DATE"
            elif any("DECIMAL" in t for t in types_found):
                column_types[column] = "DECIMAL(15,4)"
            elif any("INT" in t for t in types_found):
                column_types[column] = "INT"
            elif any("CHAR(1)" in t for t in types_found):
                column_types[column] = "CHAR(1)"
            else:
                # For VARCHAR, use the maximum length found, with a reasonable minimum
                length = min(max(max_length * 2, 50), 1000)
                column_types[column] = f"VARCHAR({length})"

        return column_types

    def format_value(self, value: Any, column_name: str) -> str:
        """Format value for SQL insertion based on its data type."""
        if value is None or str(value).strip().upper() in ["NULL", ""]:
            return "NULL"

        value_str = str(value).strip()
        column_type = self.column_types.get(column_name, "VARCHAR(255)")

        # Don't quote numeric values
        if column_type in ["INT", "DECIMAL", "DECIMAL(15,4)", "DECIMAL(10,4)"]:
            return value_str

        # Quote string values and escape single quotes
        escaped_value = value_str.replace("'", "''")
        return f"'{escaped_value}'"

    def read_csv_file(
        self, file_path: str, delimiter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Read CSV file and return list of dictionaries."""
        rows = []

        # Try to detect delimiter if not provided
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            if delimiter is None:
                sample = f.readline()
                f.seek(0)
                sniffer = csv.Sniffer().sniff(sample)
                delimiter = sniffer.delimiter
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                rows.append(row)
        return rows

    def read_csv_text(
        self, csv_text: str, delimiter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Read CSV from text string and return list of dictionaries."""
        lines = csv_text.strip().split("\n")

        # Auto-detect delimiter if not provided
        if delimiter is None:
            sniffer = csv.Sniffer().sniff(lines[0])
            delimiter = sniffer.delimiter

        reader = csv.DictReader(lines, delimiter=delimiter)
        return list(reader)

    def generate_create_table_sql(self) -> str:
        """Generate CREATE TABLE SQL statement."""
        sql_parts = [f"CREATE TABLE {self.table_name} ("]

        column_definitions = []
        for column, data_type in self.column_types.items():
            column_definitions.append(f"    {column} {data_type}")

        sql_parts.append(",\n".join(column_definitions))
        sql_parts.append(");")

        return "\n".join(sql_parts)

    def generate_insert_sql(
        self, rows: List[Dict[str, Any]], batch_size: int = 100
    ) -> str:
        """Generate INSERT SQL statements."""
        if not rows:
            return ""

        columns = list(rows[0].keys())
        column_list = ", ".join(columns)

        sql_parts = []

        # Process in batches
        for i in range(0, len(rows), batch_size):
            batch = rows[i: i + batch_size]

            sql_parts.append(f"INSERT INTO {self.table_name} ({column_list})")
            sql_parts.append("VALUES")

            value_rows = []
            for row in batch:
                formatted_values = [self.format_value(
                    row[col], col) for col in columns]
                value_rows.append(f"    ({', '.join(formatted_values)})")

            sql_parts.append(",\n".join(value_rows) + ";")
            sql_parts.append("")  # Empty line between batches

        return "\n".join(sql_parts)

    def convert(
        self,
        input_data,
        input_type: str = "file",
        delimiter: Optional[str] = None,
        include_create_table: bool = True,
        batch_size: int = 100,
    ) -> str:
        """
        Main conversion method.

        Args:
            input_data: File path (if input_type='file') or CSV text (if input_type='text')
            input_type: 'file' or 'text'
            delimiter: CSV delimiter (auto-detected if None)
            include_create_table: Whether to include CREATE TABLE statement
            batch_size: Number of rows per INSERT statement
        """
        # Read data
        if input_type == "file":
            rows = self.read_csv_file(input_data, delimiter)
        else:
            rows = self.read_csv_text(input_data, delimiter)

        if not rows:
            return "-- No data found in CSV"

        # Determine column types
        self.column_types = self.determine_column_types(rows)
        print(f"$> Columns: {self.column_types}")

        # Generate SQL
        sql_parts = ["-- SQL statements generated from CSV data", ""]

        if include_create_table:
            sql_parts.append("-- Create table structure")
            sql_parts.append(self.generate_create_table_sql())
            sql_parts.append("")

        sql_parts.append("-- Insert data")
        sql_parts.append(self.generate_insert_sql(rows, batch_size))

        return "\n".join(sql_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Convert CSV to SQL INSERT statements")
    parser.add_argument(
        "--input",
        "-i",
        default="data.csv",
        help="CSV file path or use --text for text input",
    )
    parser.add_argument(
        "--table-name",
        "-t",
        default="your_table_name",
        help="SQL table name (default: your_table_name)",
    )
    parser.add_argument(
        "--delimiter", "-d", help="CSV delimiter (auto-detected if not specified)"
    )
    parser.add_argument(
        "--no-create-table", action="store_true", help="Skip CREATE TABLE statement"
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=100,
        help="Number of rows per INSERT statement (default: 100)",
    )
    parser.add_argument(
        "--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument(
        "--text", action="store_true", help="Read CSV from stdin instead of file"
    )

    args = parser.parse_args()

    converter = CSVToSQLConverter(args.table_name)

    try:
        if args.text:
            print("$> Paste CSV data then Ctrl+D (Unix) or Ctrl+Z (Windows):")
            csv_text = sys.stdin.read()
            sql_output = converter.convert(
                csv_text,
                input_type="text",
                delimiter=args.delimiter,
                include_create_table=not args.no_create_table,
                batch_size=args.batch_size,
            )
        else:
            print(f"$> reading from file {args.input}")
            sql_output = converter.convert(
                args.input,
                input_type="file",
                delimiter=args.delimiter,
                include_create_table=not args.no_create_table,
                batch_size=args.batch_size,
            )

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(sql_output)
            print(f"SQL output written to {args.output}")
        else:
            print(sql_output)

    except Exception as e:
        _, _, e_trace = sys.exc_info()
        tb_frame = e_trace.tb_frame
        print(
            f"Error @ [{tb_frame.f_code.co_name}:{tb_frame.f_lineno}]: {e}",
            file=sys.stderr,
        )
        traceback.print_exc()
        sys.exit(1)


# Example usage as a module
if __name__ == "__main__":
    # Command-line usage
    main()

    # Example programmatic usage (commented out)
    """
    # Example 1: Convert from file
    converter = CSVToSQLConverter("my_table")
    sql_output = converter.convert("data.csv", input_type='file')
    print(sql_output)

    # Example 2: Convert from text
    csv_data = '''ID,NAME,AGE,EMAIL
    1,John Doe,30,john@email.com
    2,Jane Smith,25,jane@email.com'''

    converter = CSVToSQLConverter("users")
    sql_output = converter.convert(csv_data, input_type='text')
    print(sql_output)
    """
