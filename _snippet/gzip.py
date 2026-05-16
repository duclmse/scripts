import gzip
import zipfile
from io import BytesIO
import os


def gzip_to_zip_in_memory(gzip_paths, output_zip_path):
    """
    Convert multiple gzip files to a zip file without disk intermediates
    """
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for gzip_path in gzip_paths:
            # Read gzip file and decompress in memory
            with open(gzip_path, 'rb') as f:
                compressed_data = f.read()

            # Decompress in memory
            with gzip.GzipFile(fileobj=BytesIO(compressed_data)) as gz_file:
                decompressed_data = gz_file.read()

            # Get original filename (remove .gz extension)
            original_name = os.path.basename(gzip_path)
            if original_name.endswith('.gz'):
                original_name = original_name[:-3]

            # Add to zip directly from memory
            zipf.writestr(original_name, decompressed_data)
            print(f"Added {original_name} to zip")


# Usage
gzip_files = ['file1.txt.gz', 'file2.log.gz']
gzip_to_zip_in_memory(gzip_files, 'output.zip')


def gzip_to_zip_streaming(gzip_paths, output_zip_path, chunk_size=8192):
    """
    Stream gzip files to zip without loading entire files into memory
    """
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for gzip_path in gzip_paths:
            # Get original filename
            original_name = os.path.basename(gzip_path)
            if original_name.endswith('.gz'):
                original_name = original_name[:-3]

            # Create in-memory buffer for decompressed data
            decompressed_buffer = BytesIO()

            # Stream decompress
            with open(gzip_path, 'rb') as compressed_file:
                with gzip.GzipFile(fileobj=compressed_file) as gz_file:
                    while True:
                        chunk = gz_file.read(chunk_size)
                        if not chunk:
                            break
                        decompressed_buffer.write(chunk)

            # Add to zip
            decompressed_buffer.seek(0)
            zipf.writestr(original_name, decompressed_buffer.read())
            decompressed_buffer.close()

            print(f"Streamed {original_name} to zip")


# Usage
gzip_to_zip_streaming(['large_file.gz'], 'output.zip')
