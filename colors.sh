#!/usr/bin/env bash

echo "== 16 Standard Colors (Foreground) =="
for code in {30..37} {90..97}; do
  printf "\e[${code}m %3s \e[0m" "$code"
  [[ $(((code - 29) % 8)) == 0 ]] && echo
done
echo

echo "== 16 Background Colors =="
for code in {40..47} {100..107}; do
  printf "\e[${code}m %3s \e[0m" "$code"
  [[ $(((code - 39) % 8)) == 0 ]] && echo
done
echo

echo "== Bold Foreground Colors =="
for code in {30..37} {90..97}; do
  printf "\e[1;${code}m %3s \e[0m" "$code"
  [[ $(((code - 29) % 8)) == 0 ]] && echo
done
echo

echo "== 256 Colors (Foreground) =="
for i in {0..255}; do
  printf "\e[38;5;${i}m%03d " "$i"
  if (((i + 1) % 8 == 0)); then echo; fi
done
echo

echo "== 256 Colors (Background) =="
for i in {0..255}; do
  printf "\e[48;5;${i}m%03d " "$i"
  if (((i + 1) % 8 == 0)); then printf '\e[0;0;0m\n'; fi
done
echo
