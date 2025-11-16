#!/bin/bash

# Function to display subcommand usage
usage() {
  echo "Usage: $0 <subcommand> [parameters]"
  echo "Available subcommands:"
  echo "  h|hello"
  echo "  g|goodbye"
  echo "  s|status"
  exit 1
}

# Function to display usage for each subcommand
usage_hello() {
  echo "Usage: $0 h|hello"
  echo "  -n|--name <name>"
  echo "  -g|--greeting <greeting>"
  echo "  -p|--punctuation <punctuation>"
  exit 1
}

usage_goodbye() {
  echo "Usage: $0 g|goodbye"
  echo "  -n|--name <name>"
  echo "  -m|--message <message>"
  exit 1
}

usage_status() {
  echo "Usage: $0 s|status"
  echo "  -s|--system <system>"
  echo "  -d|--detail <detail>"
  exit 1
}

hello() {
  local name=""
  local greeting="Hello"
  local punctuation="!"
  
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      -n|--name)
        name="$2"
        shift 2
        ;;
      -n*)
        name="${1#-n}"
        shift
        ;;
      -g|--greeting)
        greeting="$2"
        shift 2
        ;;
      -g*)
        greeting="${1#-g}"
        shift
        ;;
      -p|--punctuation)
        punctuation="$2"
        shift 2
        ;;
      -p*)
        punctuation="${1#-p}"
        shift
        ;;
      *)
        echo "Unknown option: $1"
        usage_hello
        ;;
    esac
  done
  
  if [ -z "$name" ]; then
    usage_hello
  fi
  
  echo "$greeting, $name$punctuation"
}

goodbye() {
  local name=""
  local message="See you next time!"
  
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      -n|--name)
        name="$2"
        shift 2
        ;;
      -n*)
        name="${1#-n}"
        shift
        ;;
      -m|--message)
        message="$2"
        shift 2
        ;;
      -m*)
        message="${1#-m}"
        shift
        ;;
      *)
        echo "Unknown option: $1"
        usage_goodbye
        ;;
    esac
  done
  
  if [ -z "$name" ]; then
    usage_goodbye
  fi
  
  echo "Goodbye, $name! $message"
}

status() {
  local system=""
  local detail=""
  
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      -s|--system)
        system="$2"
        shift 2
        ;;
      -s*)
        system="${1#-s}"
        shift
        ;;
      -d|--detail)
        detail="$2"
        shift 2
        ;;
      -d*)
        detail="${1#-d}"
        shift
        ;;
      *)
        echo "Unknown option: $1"
        usage_status
        ;;
    esac
  done
  
  if [ -z "$system" ] || [ -z "$detail" ]; then
    usage_status
  fi
  
  echo "System status for $system: $detail"
}

# Check if a subcommand is provided
if [ "$#" -lt 1 ]; then
  usage
fi

# Dispatch the subcommand
case "$1" in
  h|hello)
    shift
    hello "$@"
    ;;
  g|goodbye)
    shift
    goodbye "$@"
    ;;
  s|status)
    shift
    status "$@"
    ;;
  *)
    echo "Unknown subcommand: $1"
    usage
    ;;
esac
