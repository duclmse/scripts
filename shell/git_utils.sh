#!/bin/bash

# Configuration: Add your repository paths here
REPO_PATHS=(
  "/path/to/repo1"
  "/path/to/repo2"
  # Add more paths as needed
)

# Check for valid command
if [ $# -lt 1 ]; then
  echo "Usage: $0 <command> [remote]"
  echo "Commands:"
  echo "  fetch     - Fetch from both remotes"
  echo "  pull      - Pull from specified remote (requires remote name)"
  echo "  push      - Push to specified remote (requires remote name)"
  echo "  status    - Show repository status"
  echo "  remotes   - List configured remotes"
  exit 1
fi

COMMAND=$1
REMOTE=$2

for repo in "${REPO_PATHS[@]}"; do
  echo -e "\n\033[1;34mProcessing ${repo}\033[0m"

  if [ ! -d "${repo}/.git" ]; then
    echo "Not a Git repository! Skipping."
    continue
  fi

  case $COMMAND in
  fetch)
    git -C "$repo" fetch --all
    ;;

  pull | push)
    if [ -z "$REMOTE" ]; then
      echo "Error: Remote name required for $COMMAND"
      exit 1
    fi
    git -C "$repo" $COMMAND $REMOTE
    ;;

  status)
    git -C "$repo" status -sb
    ;;

  remotes)
    git -C "$repo" remote -v
    ;;

  *)
    echo "Error: Unknown command '$COMMAND'"
    exit 1
    ;;
  esac
done

