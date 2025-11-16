#!/usr/bin/env bash

# INI File Reader for Bash
# Usage: source ini_reader.sh
#       ini_reader <filename> [section]

ini() {
  local file="$1"
  local section="${2:-}"
  local current_section=""
  local -A config
  local line key value

  # Check if file exists
  [[ -f "$file" ]] || {
    echo "Error: INI file not found: $file" >&2
    return 1
  }

  while IFS= read -r line; do
    # Remove comments and trim spaces
    line="${line%%[#;]*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    # echo "Processing line: $line" >&2 # Debug output

    [[ -z "$line" ]] && continue # Skip empty lines

    # Parse section headers
    if [[ "$line" =~ ^\[([a-zA-Z0-9_\.-]+)\]$ ]]; then
      current_section="${BASH_REMATCH[1]}"
      continue
    fi

    # Parse key-value pairs
    if [[ ! "$line" =~ ^([a-zA-Z0-9_\.-]+)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
      echo "Warning: Invalid line format - $line" >&2
      continue
    fi
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"

    # Remove quotes if present
    if [[ "$value" =~ ^\".+\"$ || "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:-1}"
    fi

    # Create section prefix
    local section_prefix=""
    [[ -n "$current_section" ]] && section_prefix="${current_section}_"

    # Store configuration
    if [[ -z "$section" || "$section" == "$current_section" ]]; then
      config["${key}"]="$value"
    fi
  done <"$file"

  if [[ -n $3 ]]; then
    echo "${config[$3]}" >&2
    return
  fi
  # Return configuration as variables
  for key in "${!config[@]}"; do
    printf '%s=%q\n' "$key" "${config[$key]}"
  done
}

ini "$@"

# Example Usage:
# eval "$(ini_reader config.ini)"
# eval "$(ini_reader config.ini database)"
