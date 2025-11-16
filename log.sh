#!/usr/bin/env bash

# Reads options from file and allows multiple selections

# Configuration
OPTIONS_FILE="log.txt" # File containing one option per line
TITLE="Select Options" # Menu title
SELECTED=()            # Array to store selected options
OPT_SINGLE=true

# Terminal colors
R='\e[0;31m'
G='\e[0;32m'
B='\e[0;34m'
Z='\e[0m' # Reset colors

CHECKED="${G}✓"
UNCHECKED=" "
OPT_CHKBX="[%b]"
OPT_RDOBT="(%b)"

# Check if options file exists
if [[ ! -f "$OPTIONS_FILE" ]]; then
  echo "${R}Error: Options file '$OPTIONS_FILE' not found!${Z}"
  exit 1
fi

# Display functions
draw_menu() {
  clear
  echo -e "${R}$TITLE${Z}: Use arrow keys to navigate, space to select, enter to confirm\n"

  for ((i = 0; i < $length; i++)); do
    [[ $i -eq $CURSOR ]] && PTR="${B}>" || PTR=" "

    $OPT_SINGLE && { OPT=$OPT_RDOBT; } || { OPT=$OPT_CHKBX; }
    [[ ${SELECTION[$i]} -eq 1 ]] && { CHECK="${CHECKED}"; } || { CHECK="${UNCHECKED}"; }
    CHECK=$(printf "$OPT" "$CHECK")

    OPTION="${OPTIONS[$i]}"
    printf "%b %s %s$Z\n" "$PTR" "$CHECK" "$OPTION" >&2
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

files=$(echo "${SELECTED[@]}" | awk '{print $3}')
nvim ${files}
