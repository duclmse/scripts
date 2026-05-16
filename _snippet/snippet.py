import os
import gzip
import shutil
from datetime import datetime
from pathlib import Path


def process_gzipped_files(source_dir, suffix, target_date, temp_dir="./temp_unzipped", output_zip="./processed_files"):
    """
    Simplified function to process gzipped files.
    """
    source_path = Path(source_dir)
    temp_path = Path(temp_dir)
    target_date_obj = datetime.strptime(target_date, '%Y-%m-%d')

    # Create temp directory
    temp_path.mkdir(parents=True, exist_ok=True)

    # Find and unzip matching files
    for file_path in source_path.glob(f"*{suffix}"):
        if not file_path.is_file():
            continue

        # Check date
        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        if (file_mtime.year == target_date_obj.year and
            file_mtime.month == target_date_obj.month and
                file_mtime.day == target_date_obj.day):

            # Unzip file
            output_file = temp_path / file_path.stem  # Remove .gz
            with gzip.open(file_path, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print(f"Unzipped: {file_path.name}")

    # Create zip file
    if any(temp_path.iterdir()):
        shutil.make_archive(output_zip, 'zip', temp_dir)
        print(f"Created zip file: {output_zip}.zip")
    else:
        print("No files were processed")


# Example usage
if __name__ == "__main__":
    process_gzipped_files(
        source_dir="/path/to/your/files",
        suffix=".log.gz",
        target_date="2024-01-15",
        temp_dir="./unzipped_files",
        output_zip="./final_archive"
    )
