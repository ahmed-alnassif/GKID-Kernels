#!/system/bin/sh
# Cogan Thermal Monitor: background sampler. Every INTERVAL seconds it appends one line to
# $CT_DATA/data/<date>.tsv with every temperature and what the phone was doing at that moment:
#
#   ts  app  screen  charging  current_mA  battery_t10  cpu_x10  kernel_x10  gpu  top  net  freqs  zones
#
# top = "name:pct_x10;..." (busiest user processes), net = "wifi:kB/s,cell:kB/s",
# zones = "type=tenths_of_degC,...". Usage: sampler.sh [--once]

MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.   # started as "sh report.sh"
. "$MODDIR/common.sh"

sample() {
  now=$(date +%s)
  mkdir -p "$CT_DATA/data" "$CT_RUN"

  # CPU since the previous sample: the whole phone, kernel threads and the busiest processes.
  cpu_now=$(head -n 1 "$CT_PROC/stat")
  cpu_prev=$(cat "$CT_RUN/cpu.prev" 2>/dev/null)
  cat "$CT_PROC"/[0-9]*/stat > "$CT_RUN/pids.new" 2>/dev/null
  [ -f "$CT_RUN/pids.prev" ] || : > "$CT_RUN/pids.prev"
  awk -v prev="$cpu_prev" -v cur="$cpu_now" -f "$MODDIR/cpu.awk" "$CT_RUN/pids.prev" "$CT_RUN/pids.new" \
    > "$CT_RUN/cpu.out" 2>/dev/null
  mv "$CT_RUN/pids.new" "$CT_RUN/pids.prev"
  echo "$cpu_now" > "$CT_RUN/cpu.prev"
  cpu=-1; kernel=-1; top=""
  while read -r kind a b c; do
    case "$kind" in
      C) cpu=$a; kernel=$b ;;
      P) top="$top${top:+;}$(proc_name "$b" "$c"):$a" ;;
    esac
  done < "$CT_RUN/cpu.out"

  # Network speed since the previous sample.
  set -- $(read_net_bytes)
  wifi=$1; cell=$2
  net="-"
  if read -r pts pwifi pcell < "$CT_RUN/net.prev" 2>/dev/null && [ "$now" -gt "$pts" ]; then
    dt=$((now - pts))
    net="wifi:$(((wifi - pwifi) / 1024 / dt)),cell:$(((cell - pcell) / 1024 / dt))"
  fi
  echo "$now $wifi $cell" > "$CT_RUN/net.prev"

  screen=$(read_screen)
  if [ "$screen" = 0 ]; then app=screen_off; else app=$(read_foreground); fi
  set -- $(read_battery)
  charging=$1; current=$2; battery=$3
  gpu=$(read_gpu)
  freqs=$(read_freqs)
  zones=$(read_zones)

  day=$(date +%Y-%m-%d)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$now" "$app" "$screen" "$charging" "$current" \
    "$battery" "$cpu" "$kernel" "$gpu" "${top:--}" "$net" "$freqs" "${zones:--}" >> "$CT_DATA/data/$day.tsv"
  echo "$now" > "$CT_RUN/last"
  alert "$now" "$app" "$cpu" "$gpu" "$zones"
}

# Optional heat notification (NOTIFY=1), at most once every 10 minutes.
alert() {
  [ "$NOTIFY" = 1 ] || return 0
  main=$(awk -v mode=main -v zones="$5" -f "$MODDIR/thermal.awk" -f "$MODDIR/report.awk" < /dev/null 2>/dev/null)
  case "$main" in ''|*[!0-9-]*) return 0 ;; esac
  [ "$main" -ge $((NOTIFY_TEMP * 10)) ] || return 0
  last=$(cat "$CT_RUN/notified" 2>/dev/null || echo 0)
  [ $(($1 - last)) -ge 600 ] || return 0
  echo "$1" > "$CT_RUN/notified"
  text="Prosesor $((main / 10)) °C · $(awk -v mode=label -v app="$2" -f "$MODDIR/thermal.awk" -f "$MODDIR/report.awk" < /dev/null)"
  [ "$3" -ge 0 ] && text="$text · CPU $(($3 / 10))%"
  [ "$4" -ge 0 ] && text="$text · GPU $4%"
  cmd notification post -S bigtext -t "🔥 Cogan Thermal" cogan_thermal "$text" > /dev/null 2>&1 \
    || su 2000 -c "cmd notification post -S bigtext -t 'Cogan Thermal' cogan_thermal '$text'" > /dev/null 2>&1
}

prune() {
  find "$CT_DATA/data" -name '*.tsv' -mtime +"$RETENTION_DAYS" -exec rm -f {} + 2>/dev/null
}

load_config
mkdir -p "$CT_DATA/data" "$CT_RUN"
if [ "$1" = "--once" ]; then
  sample
  exit 0
fi

echo $$ > "$CT_RUN/sampler.pid"
# Kernel in use from now on, so reports can compare kernels (e.g. Cogan r3 against stock).
printf '%s\t%s\n' "$(date +%s)" "$(uname -r)" >> "$CT_DATA/kernels.tsv"
count=0
while :; do
  [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/remove" ] && break
  sample
  count=$((count + 1))
  [ $((count % 180)) = 1 ] && prune
  sleep "$INTERVAL"
  load_config
done
rm -f "$CT_RUN/sampler.pid"
