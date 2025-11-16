#!/usr/bin/env bash

usage() {
  echo "Usage: $0 [options] <markdown_file>"
  echo "Options:"
  echo "  -r|--root <path>"
  exit 1
}

parse_param() {
  local option=""

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
    -r | --root)
      root="$2"
      shift 2
      ;;
    -r*)
      root="${1#-r}"
      shift
      ;;
    -*)
      echo "Unknown option: $1"
      usage
      ;;
    *)
      inp_fle="$1"
      shift
      ;;
    esac
  done

  if [[ -z "$inp_fle" || ! -f "$inp_fle" ]]; then
    usage
  fi

  if [ -z "$root" ]; then
    root="$inp_fle.dir"
  fi
  if [[ ! -d "$root" ]]; then
    if [[ $root == */ ]]; then
      root="${root%%/}"
    fi
    echo "$> mkdir -p '$root'" >&2
    mkdir -p "$root"
  fi
}

# Language to file extension map
declare -A lang_ext=(
  [kotlin]="kt"
  [java]="java"
  [rust]="rs"
  [bash]="sh"
  [shell]="sh"
  [javascript]="js"
  [js]="js"
  [typescript]="ts"
  [ts]="ts"
  [html]="html"
  [yml]="yml"
  [yaml]="yml"
)

# Language to comment token map
declare -A lang_comment=(
  [kotlin]="//"
  [java]="//"
  [rust]="//"
  [bash]="#"
  [js]="//"
  [ts]="//"
  [html]="<!-- -->"
  [yml]="#"
  [yaml]="#"
)

parse_param "$@"

in_blk=0
blk_cnt=0
fle_sfx="txt"
out_fle=""
fnd_fle=""
html_cmt="^[[:space:]]*\<!--[[:space:]]*([^ ]+)[[:space:]]*--\>"

while IFS= read -r line; do
  if [[ "$line" =~ ^\`\`\` ]]; then
    in_blk=$((!in_blk))
    if [[ "$in_blk" -eq 0 ]]; then
      continue
    fi
    blk_cnt=$((blk_cnt + 1))
    lang=$(echo "$line" | sed 's/^```//')
    if [[ -z "${lang_ext[$lang]}" ]]; then
      echo -e "> Cannot find lang '$lang' -> 'txt'" >&2
      fle_sfx="txt"
    else
      fle_sfx="${lang_ext[$lang]:-txt}"
    fi
    out_fle="${inp_fle##*/}.${blk_cnt}.${fle_sfx}"
    fnd_fle=""
    echo "" >"$root/$out_fle"
    continue
  fi

  if [[ "$in_blk" -eq 1 ]]; then
    if [[ -z "$fnd_fle" ]]; then
      comment_token="${lang_comment[$lang]}"

      fle_rgx="$html_cmt"
      if [[ "$comment_token" != "<!-- -->" ]]; then
        fle_rgx="^[[:space:]]*${comment_token}[[:space:]]*([^ ]+)"
      fi
      if [[ "$line" =~ $fle_rgx ]]; then
        fnd_fle="${BASH_REMATCH[1]}"
        if [[ "$fnd_fle" == *"$fle_sfx" ]]; then
          if [[ "$fnd_fle" == */* ]]; then
            mkdir -p "$root/${fnd_fle%%/*}"
          fi
          mv "$root/$out_fle" "$root/$fnd_fle"
          out_fle="$fnd_fle"
        else
          fnd_fle="$out_fle"
        fi
        # printf "found $fnd_fle\n" >&2
        printf "Code block #%3d => File: %s\n" "$blk_cnt" "$root/$out_fle" >&2
        continue
      fi
    fi
    echo "$line" >>"$root/$out_fle"
  fi
done <"$inp_fle"

echo "----------------------------------------" >&2
printf "< %3d code blocks extracted.\n" "$blk_cnt" >&2
echo "----------------------------------------" >&2
