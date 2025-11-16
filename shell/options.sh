#!/usr/bin/env bash

# Reads options from file and allows multiple selections

# Configuration
OPTIONS_FILE="options.txt" # File containing one option per line
TITLE="Select Options"     # Menu title
SELECTED=()                # Array to store selected options
OPT_SINGLE=false

# Terminal colors
CL_RED='\e[0;31m'
CL_GRN='\e[0;32m'
CL_RST='\e[0m' # Reset colors

CHECKED="${CL_GRN}✓${CL_RST}"
UNCHECKED=" "
OPT_CHKBX="[%b]"
OPT_RDOBT="(%b)"

# Check if options file exists
if [[ ! -f "$OPTIONS_FILE" ]]; then
  echo "${CL_RED}Error: Options file '$OPTIONS_FILE' not found!${CL_RST}"
  exit 1
fi

# Display functions
draw_menu() {
  clear
  echo -e "${CL_RED}$TITLE${CL_RST}: Use arrow keys to navigate, space to select, enter to confirm\n"

  for ((i = 0; i < $length; i++)); do
    [[ $i -eq $CURSOR ]] && PTR=">" || PTR=" "

    $OPT_SINGLE && { OPT=$OPT_RDOBT; } || { OPT=$OPT_CHKBX; }
    [[ ${SELECTION[$i]} -eq 1 ]] && { CHECK="${CHECKED}"; } || { CHECK="${UNCHECKED}"; }

    printf "%s $OPT %s\n" "$PTR" "$CHECK" "${OPTIONS[$i]}" >&2
  done
}

reset_selection() {
  for ((i = 0; i < $length; i++)); do
    SELECTION[$i]=0
  done
}

select_option() {
  # Read options from file into array
  mapfile -t OPTIONS <"$OPTIONS_FILE"
  length="${#OPTIONS[@]}"
  # Initialize selection status (all unchecked)
  declare -a SELECTION
  reset_selection

  # Main loop
  CURSOR=0
  while true; do
    draw_menu

    # Read single character input
    read -s -N 1 key
    case "$key" in
    $'\x1b') # Escape sequence
      read -rsn2 -t 0.1 key2
      case "$key2" in
      '[A' | '[D') # Up arrow
        ((CURSOR--))
        [[ $CURSOR -lt 0 ]] && CURSOR=$(($length - 1))
        ;;
      '[B' | '[C') # Down arrow
        ((CURSOR++))
        [[ $CURSOR -ge $length ]] && CURSOR=0
        ;;
      esac
      ;;
    $'\x20') # Space to toggle selection
      crt_val="${SELECTION[$CURSOR]}"
      $OPT_SINGLE && reset_selection
      SELECTION[$CURSOR]=$((1 - $crt_val))
      ;;
    $'\x0a') # Enter to confirm
      break
      ;;
    *)
      echo "key=$key" >&2
      ;;
    esac
  done

  # Process selected options
  for ((i = 0; i < $length; i++)); do
    if [[ ${SELECTION[$i]} -eq 1 ]]; then
      SELECTED+=("${OPTIONS[$i]}")
    fi
  done
}

select_option

# Display results
# clear
if [[ ${#SELECTED[@]} -eq 0 ]]; then
  echo "No options were selected."
  exit
fi

echo "You selected:"
printf ' - %s\n' "${SELECTED[@]}"

# Here you can add code to process the selected items
# for item in "${SELECTED[@]}"; do
#     echo "Processing $item..."
# done
