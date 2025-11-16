# Common parameters and default values
VERBOSE=false
NAMESPACE="database"
OUTPUT_FORMAT="text"
APP_LABEL=""

SUBCOMMAND_ARGS=()

#region Utilities

required() {
  [[ -z "$1" ]] && {
    if [[ $# -eq 3 ]]; then
      echo "Error: $2 is required for $3." >&2
    elif [[ $# -eq 2 ]]; then
      echo "Error: $2 requires an argument." >&2
    else
      echo "Error: Missing required parameter." >&2
    fi
    exit 1
  }
}

get_pod() {
  $VERBOSE && echo "kubectl get pod -n $NAMESPACE -l app=$1 -o jsonpath='{.items[0].metadata.name}'" >&2
  local pod=$(kubectl get pod -n $NAMESPACE -l app=$1 -o jsonpath='{.items[0].metadata.name}')
  if [[ -z "$pod" ]]; then
    echo "Error: No pod found with label 'app=$1' in namespace '$NAMESPACE'" >&2
    exit 1
  fi
  echo "$pod"
}
#endregion Utilities

#region Common Parser Functions
usg_global_opts() {
  cat <<EOF
Global Options:
  -v, --verbose         Enable verbose output
  -n, --namespace N     Set namespace (default: default)
  -o, --output FORMAT   Output format (text|json|yaml, default: text)

Global options can be placed anywhere.
EOF
}

parse_all_params() {
  while [[ $# -gt 0 ]]; do
    local param="$1"
    case "$param" in
    -a | --app)
      required "$2" "$param"
      APP_LABEL="$2"
      shift 2
      ;;
    -v | --verbose)
      VERBOSE=true
      shift
      ;;
    -n | --namespace)
      required "$2" "$param"
      NAMESPACE="$2"
      shift 2
      ;;
    -o | --output)
      required "$2" "$param"
      OUTPUT_FORMAT="$2"
      shift 2
      ;;
    --)
      shift
      SUBCOMMAND_ARGS+=("$@")
      break
      ;;
    *)
      SUBCOMMAND_ARGS+=("$1")
      shift
      ;;
    esac
  done
}
#endregion Common Parser Functions

#region Subcommand Implementations

#region Logs Subcommand
usg_logs() {
  cat <<EOF
View pod logs

Usage:
  $0 logs [OPTIONS] POD_NAME

Options:
  -f, --follow       Follow log output
  -t, --tail LINES   Number of lines to show (default: 100)

EOF
  usg_global_opts
}

cmd_logs() {
  local FOLLOW=true
  local TAIL_LINES=100
  local POD_NAME=""
  local SUB_ARGS=("$@")

  while [[ ${#SUB_ARGS[@]} -gt 0 ]]; do
    case "${SUB_ARGS[0]}" in
    -f | --follow)
      FOLLOW=true
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      ;;
    -F | --not-follow)
      FOLLOW=false
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      ;;
    -t | --tail)
      if [[ -z "${SUB_ARGS[1]}" || ! "${SUB_ARGS[1]}" =~ ^[0-9]+$ ]]; then
        echo "Error: --tail requires a number" >&2
        exit 1
      fi
      TAIL_LINES="${SUB_ARGS[1]}"
      SUB_ARGS=("${SUB_ARGS[@]:2}")
      ;;
    -h | --help)
      usg_logs
      exit 0
      ;;
    -*)
      POD_NAME="${SUB_ARGS[0]}"
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      ;;
    *)
      POD_NAME="${SUB_ARGS[0]}"
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      break
      ;;
    esac
  done

  if [[ ${#APP_LABEL} -gt 0 ]]; then
    POD_NAME=$(get_pod "$APP_LABEL")
  fi

  required "$POD_NAME" "POD_NAME" "logging"

  if $VERBOSE; then
    echo "Fetching logs for pod: $POD_NAME" >&2
    echo "  Namespace: $NAMESPACE" >&2
    echo "  Follow: $FOLLOW" >&2
    echo "  Tail lines: $TAIL_LINES" >&2
    echo "" >&2
  fi

  local FLAGS=(-n "$NAMESPACE")
  $FOLLOW && FLAGS+=(--follow)

  echo "kubectl logs ${FLAGS[@]} --tail=$TAIL_LINES $POD_NAME" >&2
  kubectl logs ${FLAGS[@]} --tail=$TAIL_LINES $POD_NAME
}
#endregion Logs Subcommand

#region Status Subcommand
usg_status() {
  cat <<EOF
Check resource status

Usage:
  $0 status [OPTIONS] RESOURCE_NAME

Options:
  -t, --type TYPE   Resource type (pod|deployment|service, default: pod)
  -j, --jsonpath    Filter output in JSON path expression
EOF
  usg_global_opts
}

cmd_status() {
  local RESOURCE_TYPE="pod"
  local RESOURCE_NAME=""
  local JSON_PATH=""
  local SUB_ARGS=("$@")

  while [[ ${#SUB_ARGS[@]} -gt 0 ]]; do
    case "${SUB_ARGS[0]}" in
    -t | --type)
      required "${SUB_ARGS[1]}" "$param"
      RESOURCE_TYPE="${SUB_ARGS[1]}"
      SUB_ARGS=("${SUB_ARGS[@]:2}")
      ;;
    -j | --jsonpath)
      required "${SUB_ARGS[1]}" "$param"
      JSON_PATH="${SUB_ARGS[1]}"
      SUB_ARGS=("${SUB_ARGS[@]:2}")
      ;;
    -h | --help)
      usg_status
      exit 0
      ;;
    -*)
      RESOURCE_NAME="${SUB_ARGS[0]}"
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      ;;
    *)
      RESOURCE_NAME="${SUB_ARGS[0]}"
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      break
      ;;
    esac
  done

  required "$RESOURCE_NAME" "RESOURCE_NAME" "checking status"

  if $VERBOSE; then
    echo "Checking status for: $RESOURCE_TYPE/$RESOURCE_NAME" >&2
    echo "  Namespace: $NAMESPACE" >&2
    echo "  Output format: $OUTPUT_FORMAT" >&2
    echo "" >&2
  fi

  local FLAGS=(-n "$NAMESPACE")
  [[ -n "$JSON_PATH" ]] && FLAGS+=(-o jsonpath="$JSON_PATH")

  echo "kubectl get $RESOURCE_TYPE $RESOURCE_NAME ${FLAGS[@]} -n $NAMESPACE \
    -o $OUTPUT_FORMAT" >&2
  kubectl get "$RESOURCE_TYPE" "$RESOURCE_NAME" "${FLAGS[@]}" -n "$NAMESPACE" \
    -o "$OUTPUT_FORMAT"
}
#endregion Status Subcommand

#region Delete Subcommand
usg_delete() {
  cat <<EOF
Delete a resource

Usage:
  $0 delete [OPTIONS] RESOURCE_NAME

Options:
  -f, --force       Force deletion
  -t, --type TYPE   Resource type (pod|deployment|service, default: pod)
EOF
  usg_global_opts
}

cmd_delete() {
  local FORCE=false
  local RESOURCE_TYPE="pod"
  local RESOURCE_NAME=""
  local SUB_ARGS=("$@")

  while [[ ${#SUB_ARGS[@]} -gt 0 ]]; do
    case "${SUB_ARGS[0]}" in
    -f | --force)
      FORCE=true
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      ;;
    -t | --type)
      required "${SUB_ARGS[1]}" "$param"
      RESOURCE_TYPE="${SUB_ARGS[1]}"
      SUB_ARGS=("${SUB_ARGS[@]:2}")
      ;;
    -a | --app)
      required "${SUB_ARGS[1]}" "$param"
      APP_LABEL="${SUB_ARGS[1]}"
      SUB_ARGS=("${SUB_ARGS[@]:2}")
      ;;
    -h | --help)
      usg_delete
      exit 0
      ;;
    -*)
      RESOURCE_NAME="${SUB_ARGS[0]}"
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      ;;
    *)
      RESOURCE_NAME="${SUB_ARGS[0]}"
      SUB_ARGS=("${SUB_ARGS[@]:1}")
      break
      ;;
    esac
  done

  if [[ ${#APP_LABEL} -gt 0 ]]; then
    RESOURCE_NAME=$(get_pod "$APP_LABEL")
  fi

  required "$RESOURCE_NAME" "RESOURCE_NAME" "deleting"

  if $VERBOSE; then
    echo "Deleting $RESOURCE_TYPE: $RESOURCE_NAME" >&2
    echo "  Namespace: $NAMESPACE" >&2
    echo "  Force: $FORCE" >&2
    echo "" >&2
  fi

  local FLAGS=(-n "$NAMESPACE")
  $FORCE && FLAGS+=(--force --grace-period=0)

  echo "kubectl delete $RESOURCE_TYPE $RESOURCE_NAME ${FLAGS[@]}"
  kubectl delete $RESOURCE_TYPE $RESOURCE_NAME ${FLAGS[@]}
}
#endregion Delete Subcommand

#endregion Subcommand Implementations

#region Main Script
show_help() {
  cat <<EOF
Kubernetes Resource Manager

Usage:
  $0 <SUBCOMMAND> [OPTIONS]

Subcommands:
  l, logs     View pod logs
  s, status   Check resource status
  d, delete   Delete a resource
  h, help     Show this help message

Run '$0 <SUBCOMMAND> --help' for subcommand-specific help
EOF
}

main() {
  [[ $# -eq 0 ]] && {
    show_help
    exit 0
  }

  parse_all_params "$@"

  [[ ${#SUBCOMMAND_ARGS[@]} -eq 0 ]] && {
    echo "Error: Subcommand required" >&2
    show_help
    exit 1
  }

  local SUBCOMMAND="${SUBCOMMAND_ARGS[0]}"
  SUBCOMMAND_ARGS=("${SUBCOMMAND_ARGS[@]:1}")

  # echo "SUBCOMMAND=($SUBCOMMAND)" >&2
  # echo "SUBCOMMAND_ARGS=($SUBCOMMAND_ARGS)" >&2

  case "$SUBCOMMAND" in
  l | logs)
    cmd_logs "${SUBCOMMAND_ARGS[@]}"
    ;;
  s | status)
    cmd_status "${SUBCOMMAND_ARGS[@]}"
    ;;
  d | delete)
    cmd_delete "${SUBCOMMAND_ARGS[@]}"
    ;;
  -h | --help | help)
    show_help
    ;;
  *)
    echo "Error: Unknown subcommand '$SUBCOMMAND'" >&2
    show_help
    exit 1
    ;;
  esac
}

main "$@"
#endregion Main Script

# vim: set ts=2 sw=2 et:
