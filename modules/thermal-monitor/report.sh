#!/system/bin/sh
# Cogan Thermal Monitor: everything the WebUI and the Action button ask for. Output is JSON unless noted.
#
#   report.sh now                 latest sample + every sensor read right now
#   report.sh summary SECS        summary of the last SECS seconds
#   report.sh text SECS           the same summary as plain text
#   report.sh csv SECS            one CSV row per sample (text)
#   report.sh save SECS           write the summary (txt) and samples (csv) to $CT_OUT
#   report.sh status              sampler state and settings
#   report.sh set KEY VALUE ...   change settings (only known keys, plain numbers within range)
#   report.sh start | stop        start or stop the sampler
#   report.sh clear               delete the recorded history

MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.   # started as "sh report.sh"
. "$MODDIR/common.sh"
load_config

now=$(date +%s)
tzoff=$(date +%z | awk '{ s = substr($0, 1, 1) == "-" ? -1 : 1; print s * (substr($0, 2, 2) * 3600 + substr($0, 4, 2) * 60) }')
kfile=$CT_DATA/kernels.tsv
[ -f "$kfile" ] || kfile=/dev/null
mfile=$CT_DATA/modes.tsv   # written by Cogan Power Mode when installed
[ -f "$mfile" ] || mfile=/dev/null

# SECS as a number between one minute and 31 days (one hour when missing or not a number).
secs_arg() {
  case "$1" in ''|*[!0-9]*) echo 3600; return ;; esac
  if [ "$1" -lt 60 ]; then echo 60; elif [ "$1" -gt 2678400 ]; then echo 2678400; else echo "$1"; fi
}

run_awk() {   # run_awk MODE SECS FILES...
  mode=$1; secs=$2; shift 2
  awk -v mode="$mode" -v since=$((now - secs)) -v now="$now" -v secs="$secs" -v HOT=$((HOT_TEMP * 10)) \
      -v TZOFF="$tzoff" -v KFILE="$kfile" -v MFILE="$mfile" -v fresh="$fresh" -v release="$release" -v running="$running" \
      -f "$MODDIR/thermal.awk" -f "$MODDIR/report.awk" "$kfile" "$mfile" "$@"
}

# Day files that can hold samples from the last SECS seconds.
data_files() {
  min=$(awk -v mode=date -v since=$((now - $1)) -v TZOFF="$tzoff" -f "$MODDIR/thermal.awk" -f "$MODDIR/report.awk" < /dev/null)
  ls "$CT_DATA"/data/*.tsv 2>/dev/null | awk -v min="$min.tsv" '{ n = $0; sub(/.*\//, "", n); if (n >= min) print }'
}

report() {   # report MODE SECS
  run_awk "$1" "$2" $(data_files "$2")
}

sampler_pid() {
  pid=$(cat "$CT_RUN/sampler.pid" 2>/dev/null)
  case "$pid" in ''|*[!0-9]*) return 1 ;; esac
  kill -0 "$pid" 2>/dev/null && grep -q sampler "/proc/$pid/cmdline" 2>/dev/null && echo "$pid"
}

start_sampler() {
  [ -n "$(sampler_pid)" ] && return 0
  mkdir -p "$CT_RUN"
  set -- sh "$MODDIR/sampler.sh"
  command -v nice > /dev/null 2>&1 && set -- nice -n 10 "$@"
  if command -v setsid > /dev/null 2>&1; then
    setsid "$@" < /dev/null > /dev/null 2>&1 &
  else
    nohup "$@" < /dev/null > /dev/null 2>&1 &
  fi
  i=0
  while [ $i -lt 20 ] && [ -z "$(sampler_pid)" ]; do sleep 0.1 2>/dev/null || sleep 1; i=$((i + 1)); done
}

stop_sampler() {
  if pid=$(sampler_pid); then
    kill "$pid" 2>/dev/null
    i=0
    while [ $i -lt 20 ] && kill -0 "$pid" 2>/dev/null; do sleep 0.1 2>/dev/null || sleep 1; i=$((i + 1)); done
  fi
  rm -f "$CT_RUN/sampler.pid"
}

status_json() {
  pid=$(sampler_pid) || pid=0
  days=$(ls "$CT_DATA"/data/*.tsv 2>/dev/null | wc -l)
  first=$(ls "$CT_DATA"/data/*.tsv 2>/dev/null | head -n 1)
  first=${first##*/}; first=${first%.tsv}
  size=$(du -sk "$CT_DATA/data" 2>/dev/null | awk '{ print $1 + 0 }')
  version=$(sed -n 's/^version=//p' "$MODDIR/module.prop" 2>/dev/null)
  printf '{"running":%d,"pid":%d,"version":"%s","interval":%d,"retention":%d,"hot":%d,"notify":%d,"notify_temp":%d,' \
    "$([ "$pid" -gt 0 ] && echo 1 || echo 0)" "$pid" "$version" "$INTERVAL" "$RETENTION_DAYS" "$HOT_TEMP" "$NOTIFY" "$NOTIFY_TEMP"
  printf '"days":%d,"first":"%s","size_kb":%d,"out":"%s"}\n' "$days" "$first" "${size:-0}" "$CT_OUT"
}

set_values() {
  errors=""
  while [ $# -ge 2 ]; do
    set_key=$1; set_value=$2; shift 2   # not key/value: load_config reads into those
    case "$set_key" in
      INTERVAL|RETENTION_DAYS|HOT_TEMP|NOTIFY|NOTIFY_TEMP) ;;
      *) errors="$errors${errors:+, }$set_key"; continue ;;
    esac
    write_config
    echo "$set_key=$set_value" >> "$CONFIG"
    load_config
    eval "got=\$$set_key"   # one of the names above
    [ "$got" = "$set_value" ] || errors="$errors${errors:+, }$set_key"
  done
  write_config
  if [ -z "$errors" ]; then echo '{"ok":1}'; else printf '{"ok":0,"error":"Nilai tidak valid: %s"}\n' "$errors"; fi
}

save_log() {
  secs=$(secs_arg "$1")
  dir=$CT_OUT
  if ! mkdir -p "$dir" 2>/dev/null || ! [ -w "$dir" ]; then dir=$CT_DATA/logs; mkdir -p "$dir"; fi
  minutes=$((secs / 60))
  if [ $((minutes % 1440)) = 0 ]; then span="$((minutes / 1440))hari"
  elif [ $((minutes % 60)) = 0 ]; then span="$((minutes / 60))jam"
  else span="${minutes}menit"; fi
  name=cogan-thermal_$(date +%Y-%m-%d_%H-%M-%S)_$span
  files=$(data_files "$secs")
  device=$(getprop ro.product.marketname 2>/dev/null)
  [ -n "$device" ] || device=$(getprop ro.product.model 2>/dev/null)
  {
    run_awk text "$secs" $files
    echo
    echo "Perangkat: ${device:-?} · Android $(getprop ro.build.version.release 2>/dev/null) · kernel $(uname -r)"
    echo "Modul: $(sed -n 's/^version=//p' "$MODDIR/module.prop" 2>/dev/null) · cek tiap $INTERVAL detik · batas panas $HOT_TEMP °C"
    echo
    echo "Detail per sampel:"
    run_awk detail "$secs" $files
  } > "$dir/$name.txt"
  run_awk csv "$secs" $files > "$dir/$name.csv"
  rows=$(($(wc -l < "$dir/$name.csv") - 1))
  # Let the gallery/file pickers see the new files right away (best effort).
  for f in "$dir/$name.txt" "$dir/$name.csv"; do
    am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$f" > /dev/null 2>&1 &
  done
  printf '{"ok":1,"samples":%d,"dir":"%s","txt":"%s","csv":"%s"}\n' "$rows" "$dir" "$dir/$name.txt" "$dir/$name.csv"
}

case "$1" in
  now)
    fresh=$(read_zones)
    release=$(uname -r)
    if [ -n "$(sampler_pid)" ]; then running=1; else running=0; fi
    latest=$(ls "$CT_DATA"/data/*.tsv 2>/dev/null | tail -n 1)
    run_awk now 0 ${latest:-/dev/null}
    ;;
  summary) report json "$(secs_arg "$2")" ;;
  text) report text "$(secs_arg "$2")" ;;
  csv) report csv "$(secs_arg "$2")" ;;
  detail) report detail "$(secs_arg "$2")" ;;
  save) save_log "$2" ;;
  status) status_json ;;
  set) shift; set_values "$@" ;;
  start) start_sampler; status_json ;;
  stop) stop_sampler; status_json ;;
  restart) stop_sampler; sleep 1; start_sampler; status_json ;;
  clear)
    rm -f "$CT_DATA"/data/*.tsv "$CT_RUN/cpu.prev" "$CT_RUN/pids.prev" "$CT_RUN/net.prev" "$CT_RUN/last" "$CT_RUN/notified"
    printf '%s\t%s\n' "$now" "$(uname -r)" > "$CT_DATA/kernels.tsv"
    # Keep the Cogan Power Mode mode that is active now.
    current=$(tail -n 1 "$CT_DATA/modes.tsv" 2>/dev/null | cut -f 2)
    [ -n "$current" ] && printf '%s\t%s\n' "$now" "$current" > "$CT_DATA/modes.tsv"
    echo '{"ok":1}'
    ;;
  *)
    echo "Pakai: report.sh now|summary SECS|text SECS|csv SECS|save SECS|status|set KEY VALUE|start|stop|restart|clear" >&2
    exit 1
    ;;
esac
