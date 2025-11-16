#!/usr/bin/env bash

### On app server
debug=false
bkt_nme=s3://sst-s3-seab-sxm-uatmz-transfer

cft_hst=10.191.137.42
cft_usr=xe2_cft
cft_pwd=xe2_cft

enc_pwd='Helloncs$2025'
enc_pbk=/mnt/efsizapp/slift/2025/uat.iexams.seab.gov.sg.pfx
key_dir=/mnt/efsizapp/slift/Slift_keys

declare -A key_map=(
  [sc]='SC/UAT_SLIFT_iEXAMS2_AS_SENDER_TO_SC.cer'
)
declare -A intf_map=(
)

exe_cmd() {
  cmd=$1
  act_msg=$2
  echo "$> $cmd" >&2
  result=$(${cmd})
  if [ $? -eq 0 ]; then
    echo "> Succeeded to ${act_msg}" >&2
  else
    echo "> Failed to ${act_msg}" >&2
    exit 1
  fi
  echo "$result"
}

encrypt_zip() {
  echo "$> $bkt_nme/$fil_nme (+ $key_dir/${key_map[$intf]}) -> $cft_usr@$cft_hst" >&2
  [[ debug ]] && exit 0

  # 1. Copy text file from S3
  aws_cpy="aws s3 cp '$bkt_nme/$fil_nme' ."
  exe_cmd "$aws_cpy" "copy file '$fil_nme' from '$bkt_nme'"

  # 2. Zip the text file
  zip_fle="zip '$fil_nme.zip' '$fil_nme'"
  exe_cmd "$zip_fle" "zip '$fil_nme' to '$fil_nme.zip'"

  # 3. Encrypt the zip file
  enc_fle="/opt/slift/SLIFTEzClassicJ/run.sh -e -pfx $enc_pbk $enc_pwd -cer '$key_dir/${key_map[$intf]}' '$fil_nme.zip'"
  exe_cmd "$enc_fle" "encrypt zip file to '$fil_nme.zip.p7'"

  # 4.Push the encrypted file to CFT server
  scp_fle="scp './$fil_nme.zip.p7' '$cft_usr@$cft_hst:/sftp_data/xe2/$intf/out/'"
  exe_cmd "$scp_fle" "push file '$fil_nme.zip.p7' to CFT server"
}

### On SFTP server
declare -A dir_map=(
  [sc]='UAT_*'
)
declare -A cfg_map=(
  [sc]='putSC_config.cfg'
  [sh]='putSH_config.cfg'
)

put_zip() {
  echo "$> ${cfg_map[$intf]} -> ${dir_map[$intf]}" >&2
  [[ debug ]] && exit 0

  # 5. Import SFTP config
  source "~/cronjob/config/${cfg_map[$intf]}"

  # 6. Upload file to CFT server
  sftpg3 -K ${_PassKey} ${_user}@${_ip}:${_SouPath} <<sftp_commands
    put "$fil_nme.zip.p7"
    ls -l
    pwd
sftp_commands
}

usage_ez() {
  echo "Usage: $0 <command>"
  echo "  command (ez - encrypt zip; pz - put zip)"
  echo "    -i|--interface <interface-name>"
  echo "    -f|--file <file-name>"
  exit 1
}

parse_param() {
  root_cmd=$1
  shift
  cmd=("encrypt_zip")
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
    -i | --interface)
      intf="$2"
      shift 2
      ;;
    -i*)
      intf="${1#-i}"
      shift
      ;;
    -f | --file)
      fil_nme="$2"
      shift 2
      ;;
    -f*)
      fil_nme="${1#-i}"
      shift
      ;;
    -s3)
      s3=true
      shift
      ;;
    -d)
      debug=true
      shift
      ;;
    ez)
      cmd+=("encrypt_zip")
      shift
      ;;
    pz)
      cmd+=("put_zip")
      shift
      ;;
    *)
      echo "Unknown option: $1"
      usage_ez "$root_cmd"
      ;;
    esac
  done

  if [[ -z "$intf" || -z "$fil_nme" ]]; then
    usage_ez
  fi
}

parse_param $0 "$@"

if [[ "$cmd[@]" =~ "encrypt_zip" ]]; then
  echo "encrypt_zip -i $intf -f $fil_nme" >&2
  $(encrypt_zip)
fi

if [[ "$cmd[@]" =~ "put_zip" ]]; then
  echo "put_zip -i $intf -f $fil_nme" >&2
  $(put_zip)
fi
