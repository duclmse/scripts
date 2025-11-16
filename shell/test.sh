#!/bin/bash

# Usage: ./script.sh [search_directory] [pattern]

search_dir="${1:-.}"  # Default to current directory
pattern="${2:-*.log}" # Default pattern for all .gz files

# Find and process .gz files
find "$search_dir" -type f -name "$pattern" -print0 | while IFS= read -r -d '' file; do
  # Get last modified date in YYYY-MM-DD HH:MM:SS format
  mod_date=$(date -r "$file" "+%Y-%m-%d %H:%M:%S")

  # Remove .gz extension from filename (handles multiple .gz extensions)
  base_name=$(basename "$file")
  clean_name=${base_name%%.gz*}

  # Print in requested format
  printf "%s - %s\n" "$mod_date" "$clean_name"
done
