#!/usr/bin/env bash

usage() {
  echo "Usage: $0 <tree-file>"
  exit 1
}

parse_params() {
  debug=false
  while [[ "$#" -gt 0 ]]; do
    opt=$1
    case "$opt" in
    -r | --root)
      root=$2
      shift 2
      ;;
    -f | --file)
      tree_file=$2
      shift 2
      ;;
    -d | --debug)
      debug=true
      shift
      ;;
    *)
      tree_file=$1
      shift
      # echo "Unknown option: $opt"
      # usage
      ;;
    esac
  done

  if [[ ! -f "$tree_file" ]]; then
    echo "Error: File '$tree_file' not found"
    usage
    exit 1
  fi
}

parse_params "$@"

# Read the entire file into an array
lines=()
while IFS= read -r line; do lines+=("$line"); done <"$tree_file"

# Initialize variables
stack=()
current_depth=0

printf "" >log.txt
# Process each line
for line in "${lines[@]}"; do
  if [[ -z "$line" || ! "$line" =~ ^([^[:alnum:]_]+)([^[:space:]]+)/?( *#.*)?$ ]]; then
    continue
  fi

  indent="${BASH_REMATCH[1]}"
  item="${BASH_REMATCH[2]}"

  # Get the actual item name (remove tree characters)
  depth=$(((${#line} - ${#indent}) / 4))

  # Skip lines without valid content
  if [ -z "$item" ]; then
    continue
  fi
  # Handle directory depth changes
  # $debug && printf "$>>> %-30s @ cd=%2d >> d=%2d; #l=%2d; #i=%2d\n" \
  #   $item $current_depth $depth "${#line}" "${#item}" >&2
  while [[ $depth -le $current_depth ]]; do
    index=$((${#stack[@]} - 1))
    unset "stack[$index]"
    ((current_depth--))
  done

  # Determine if it's a directory or file
  if [[ "$item" == */ ]]; then
    # Directory - remove trailing slash
    dir_name="${item%/}"
    stack+=("$dir_name")
    current_depth=$depth
    full_path=$(printf "%s/" "${stack[@]}")
    printf "> $full_path\n" >&2 # >>log.txt
    [[ ! debug ]] && mkdir -p "$root/$full_path"
  else
    full_path=$(printf "%s/" "${stack[@]}")
    printf "> $full_path$item\n" >&2 # >>log.txt
    [[ ! debug ]] && touch "$root/$full_path$item"
  fi
  printf "\n" >>log.txt
done

echo "File structure created successfully!" >&2
