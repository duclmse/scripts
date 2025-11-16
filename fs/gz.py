import sys
import gzip
import shutil
import argparse
from datetime import datetime
from pathlib import Path


def list_files_with_suffix_by_date(directory, suffix, target_date):
    if not directory.exists():
        raise FileNotFoundError(f"Directory {directory} does not exist")

    matching_files = []
    for file_path in directory.glob(f"*{suffix}"):
        if not file_path.is_file():
            continue

        mtime = file_path.stat().st_mtime
        if (datetime.fromtimestamp(mtime).date() == target_date):
            matching_files.append(file_path)

    return matching_files


def unzip_files_to_directory(files, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    unzipped_files = []
    for gzipped_file in files:
        # Remove .gz extension for output filename
        output_filename = gzipped_file.stem  # This removes .gz
        output_file_path = output_path / output_filename

        try:
            with gzip.open(gzipped_file, 'rb') as f_in:
                with open(output_file_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            unzipped_files.append(output_file_path)
            print(f"Unzipped: {gzipped_file} -> {output_file_path}")

        except Exception as e:
            print(f"Error unzipping {gzipped_file}: {e}")

    return unzipped_files


def zip_directory(directory, output_zip_path):
    output_zip_path = Path(output_zip_path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory {directory} does not exist")

    shutil.make_archive(str(output_zip_path.with_suffix('')), 'zip', directory)

    zip_file_path = output_zip_path.with_suffix('.zip')
    print(f"Created zip file: {zip_file_path}")

    return zip_file_path


def main():
    parser = argparse.ArgumentParser(description='Process gzipped files from a specific date')
    parser.add_argument('--source-dir', required=True, help='Source directory containing gzipped files')
    parser.add_argument('--suffix', required=True, help='File prefix to look for (e.g., .log.gz)')
    parser.add_argument('--date', required=True, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--temp-dir', default='./temp_unzipped', help='Temporary directory for unzipped files')
    parser.add_argument('--output-zip', default='./processed_files',
                        help='Output zip file path (without .zip extension)')

    args = parser.parse_args()

    try:
        target_date = datetime.strptime(args.date, '%Y-%m-%d')

        print(f"Searching for files with suffix '{args.prefix}' from {args.date} in {args.source_dir}")

        # Step 1: List files with suffix from specific date
        matching_files = list_files_with_suffix_by_date(args.source_dir, args.suffix, target_date)

        if not matching_files:
            print(f"No files found with suffix '{args.suffix}' from {args.date}")
            return

        print(f"Found {len(matching_files)} matching files:")
        for file in matching_files:
            print(f"  - {file}")

        # Step 2: Un-gzip files to temporary directory
        print(f"\nUnzipping files to {args.temp_dir}")
        unzipped_files = unzip_files_to_directory(matching_files, args.temp_dir)

        if not unzipped_files:
            print("No files were successfully unzipped")
            return

        print(f"Successfully unzipped {len(unzipped_files)} files")

        # Step 3: Zip the temporary directory
        print(f"\nCreating zip file: {args.output_zip}.zip")
        zip_file_path = zip_directory(args.temp_dir, args.output_zip)

        print(f"\nProcess completed successfully!")
        print(f"Zip file created: {zip_file_path}")
        print(f"Temporary files location: {args.temp_dir}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
