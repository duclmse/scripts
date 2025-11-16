#!/usr/bin/env bash

jks_usr="appuser"
jks_hst="10.250.66.78"
jks_dir="/mnt/xe2drive/service-sec"

svc_usr="appuser"
svc_dir="/app/xe2/iexams2-sec-%s"
svc_tmp="iexams2-sec-%s.service"
jar_tmp="iexams2-sec-%s.jar"

declare -A server_map=(
  [w1]="192.168.0.111"
  [w2]="192.168.0.112"
  [centre]="10.250.66.76"
  [cmm]="10.250.66.76"
  [config]="10.250.66.76"
  [epm]="10.250.66.76"
  [mrm]="10.250.66.76"
  [report]="10.250.66.76"
  [elm]="10.250.66.77"
  [exercise]="10.250.66.77"
  [fmm]="10.250.66.77"
  [finance]="10.250.66.77"
  [sam]="10.250.66.77"
  [scheduler]="10.250.66.77"
)
declare -A service_map=(
  [centre]="centre-cem"
  [config]="config-cem"
  [exercise]="exercise-cem"
)
debug=true

exe_cmd() {
  cmd=$1
  act_msg=$2
  echo "$> $cmd" >&2
  res=$($cmd)
  if [ $? -eq 0 ]; then
    echo "> Succeeded to ${act_msg}" >&2
  else
    echo "> Failed to ${act_msg}" >&2
    exit 1
  fi
  echo "$res"
}

svc=$1
svc_hst="${server_map[$svc]}"
service="${service_map[$svc]}"
if [[ -z $service ]]; then
  service=$svc
fi

ls="ssh -q $jks_usr@$jks_hst ls $jks_dir | grep $svc"
[[ debug ]] && echo "$> $ls" >&2

grp=$(exe_cmd "$ls" "find '$svc'") >&2

readarray -t files < <(echo "$grp") >&2

length=${#files[@]}
if [[ $length -le 0 ]]; then
  echo "< Cannot find any matching file!"
  exit
fi

indices=("${!files[@]}")
for index in "${indices[@]}"; do
  if [[ $index -eq $((length - 1)) ]]; then
    printf "%3d. [%s]\n" "$index" "${files[$index]}"
  else
    printf "%3d.  %s\n" "$index" "${files[$index]}"
  fi
done

read -p "> Choose file to transfer [$index]: " choice
if [[ -z $choice ]]; then
  choice=$index
fi
if ! [[ "$choice" =~ ^[0-9]+$ ]] || [[ choice -lt 0 || choice -gt $(($length - 1)) ]]; then
  echo "Invalid selection."
  exit 1
fi

chs_jar=${files[$choice]}
src=$(printf "${jks_usr}@${jks_hst}:${jks_dir}/${chs_jar}")
dst=$(printf "${svc_usr}@${svc_hst}:${svc_dir}/${jar_tmp}" "$service" "$service")
cpy_cmd="scp -3 ${src} ${dst}"
exe_cmd "$cpy_cmd" "copy from ${jks_hst} to ${svc_hst}"

rst_cmd=$(printf "ssh ${svc_usr}@${svc_hst} 'systemctl restart ${svc_tmp}'" "$service")
exe_cmd "$rst_cmd" "restart $service"
