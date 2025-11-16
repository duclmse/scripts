#!/usr/bin/env python3

import abc
import json
import argparse
from typing import List, Tuple, Dict, Any, Union


class ValueConverter:
    pass


class FileFormat(abc.ABC):
    @abc.abstractmethod
    def read(self, input):
        pass

    @abc.abstractmethod
    def write(self, output):
        pass


class PositionText(FileFormat):
    def __init__(self, field_names: Union[List[str], str], field_positions: Union[List[str], str]):
        """
        Initialize the processor with field names and their positions.

        Args:
            field_names: List of field names or comma-separated string
            field_positions: List of position ranges or comma-separated string (e.g., '1-8, 9-12, ...')
        """
        self.field_names = self._parse_field_names(field_names)
        self.field_ranges = self._parse_positions(field_positions)

        name_len = len(self.field_names)
        range_len = len(self.field_ranges)
        if name_len != range_len:
            raise ValueError(
                f"No. of field names ({name_len}) must match number of field positions ({range_len})")

    def _parse_field_names(self, field_names: Union[List[str], str]) -> List[str]:
        """
        Parse field names from string or list.

        Args:
            field_names: Either a list of field names or a comma-separated string

        Returns:
            List of field names
        """
        if isinstance(field_names, str):
            return [name.strip() for name in field_names.split(',')]
        return field_names

    def _parse_positions(self, positions: Union[List[str], str]) -> List[Tuple[int, int]]:
        """
        Parse position strings into (start, end) tuples.
        Converts 1-based positions to 0-based for Python slicing.

        Args:
            positions: List of position ranges or comma-separated string like '1-8, 9-12, 13-14'

        Returns:
            List of (start, end) tuples for Python slicing
        """
        if isinstance(positions, str):
            # Split by comma and clean up whitespace
            position_list = [pos.strip() for pos in positions.split(',')]
        else:
            position_list = positions

        ranges = []
        for pos in position_list:
            try:
                start_str, end_str = pos.strip().split('-')
                start = int(start_str) - 1  # Convert to 0-based indexing
                # End is inclusive, so no -1 needed for slicing
                end = int(end_str)
                ranges.append((start, end))
            except ValueError:
                raise ValueError(
                    f"Invalid position format: {pos}. Expected format: 'start-end'")

        return ranges

    @classmethod
    def from_definition_files(cls, header_file: str, positions_file: str, encoding: str = 'utf-8'):
        """
        Create a FlatFileProcessor from definition files.

        Args:
            header_file: Path to file containing field names
            positions_file: Path to file containing field positions
            encoding: File encoding

        Returns:
            FlatFileProcessor instance
        """
        with open(header_file, 'r', encoding=encoding) as f:
            field_names = f.read().strip()

        with open(positions_file, 'r', encoding=encoding) as f:
            field_positions = f.read().strip()

        return cls(field_names, field_positions)

    @classmethod
    def from_definition_strings(cls, header_string: str, positions_string: str):
        """
        Create a FlatFileProcessor from definition strings.

        Args:
            header_string: Comma-separated field names
            positions_string: Comma-separated field positions

        Returns:
            FlatFileProcessor instance
        """
        print(f"header={header_string}\npos={positions_string}")
        return cls(header_string, positions_string)

    def parse_line(self, line: str) -> Dict[str, Any]:
        """
        Parse a single line of fixed-width data into a dictionary.

        Args:
            line: A line from the flat file

        Returns:
            Dictionary with field names as keys and extracted values
        """
        record = {}

        for field_name, (start, end) in zip(self.field_names, self.field_ranges):
            # Extract the field value and strip whitespace
            value = line[start:end].strip() if len(line) > start else ""

            # Try to convert to appropriate data type
            record[field_name] = self._convert_value(value)

        return record


class FlatFileProcessor:
    def __init__(self, input: FileFormat, output: FileFormat):
        """
        """
        pass

    def _convert_value(self, value: str) -> Any:
        """
        Convert string value to appropriate data type.

        Args:
            value: String value to convert

        Returns:
            Converted value (int, float, or string)
        """
        if not value:
            return None

        # Try to convert to integer
        try:
            return int(value)
        except ValueError:
            pass

        # Try to convert to float
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string if no conversion possible
        return value

    def process_file(self, input_file: str, output_file: str, encoding: str = 'utf-8'):
        """
        Process the entire flat file and write JSON output.

        Args:
            input_file: Path to input flat file
            output_file: Path to output JSON file
            encoding: File encoding (default: utf-8)
        """
        records = []

        try:
            with open(input_file, 'r', encoding=encoding) as infile:
                for line_num, line in enumerate(infile, 1):
                    # Remove newline characters but preserve other whitespace for positioning
                    line = line.rstrip('\n\r')

                    try:
                        record = self.parse_line(line)
                        records.append(record)
                    except Exception as e:
                        print(f"Error processing line {line_num}: {e}")
                        print(f"Line content: {repr(line)}")
                        continue

            # Write JSON output
            with open(output_file, 'w', encoding=encoding) as outfile:
                json.dump(records, outfile, indent=None, ensure_ascii=False)

            print(
                f"Successfully processed {len(records)} records from {input_file} to {output_file}")

        except FileNotFoundError:
            print(f"Error: Input file '{input_file}' not found")
        except Exception as e:
            print(f"Error processing file: {e}")


def main():
    # Command line argument parsing
    parser = argparse.ArgumentParser(description='Convert flat file to JSON')
    parser.add_argument('input_file', help='Path to input flat file')
    parser.add_argument('output_file', help='Path to output JSON file')

    # Field definition options (mutually exclusive groups)
    field_group = parser.add_mutually_exclusive_group(required=True)
    field_group.add_argument(
        '--header-string', help='Comma-separated field names string')
    field_group.add_argument(
        '--header-file', help='Path to file containing field names')

    pos_group = parser.add_mutually_exclusive_group(required=True)
    pos_group.add_argument('--positions-string',
                           help='Comma-separated field positions string')
    pos_group.add_argument(
        '--positions-file', help='Path to file containing field positions')

    parser.add_argument('--encoding', default='utf-8',
                        help='File encoding (default: utf-8)')

    args = parser.parse_args()

    # Validate argument combinations
    if bool(args.header_string) != bool(args.positions_string):
        parser.error(
            "--header-string and --positions-string must be used together")
    if bool(args.header_file) != bool(args.positions_file):
        parser.error(
            "--header-file and --positions-file must be used together")

    # Create processor based on arguments
    try:
        if args.header_string and args.positions_string:
            processor = FlatFileProcessor.from_definition_strings(
                args.header_string, args.positions_string
            )
        else:
            processor = FlatFileProcessor.from_definition_files(
                args.header_file, args.positions_file, args.encoding
            )

        processor.process_file(
            args.input_file, args.output_file, args.encoding)
    except Exception as e:
        print(f"Error: {e}")


# Example usage without command line arguments:
def example_usage():
    """
    Example of how to use the FlatFileProcessor class directly
    """
    # Using your example strings directly
    header_string = "centreIndex,subjectCode,subjectGrade,hurdleGrade,paperNo1,paperGrade1,paperNo2,paperGrade2,paperNo3,paperGrade3,paperNo4,paperGrade4,paperNo5,paperGrade5,paperNo6,paperGrade6,paperNo7,paperGrade7,paperNo8,paperGrade8,paperNo9,paperGrade9"

    positions_string = "1-8,9-12,13-14,15-15, 16-17, 18-18, 19-20, 21-21, 22-23, 24-24, 25-26, 27-27, 28-29, 30-30, 31-32, 33-33, 34-35, 36-36, 37-38, 39-39, 40-41, 42-42"

    # Create processor from strings
    processor = FlatFileProcessor.from_definition_strings(
        header_string, positions_string)

    # Process a sample line
    processor.process_file("input.txt", "output.txt", "utf-8")

    # Process a file
    # processor.process_file('input.txt', 'output.json')


if __name__ == "__main__":
    # main()
    example_usage()
    # demo_with_your_examples()
