#!/system/bin/sh
# Cogan Power Mode: everything the WebUI and the Action button ask for. Output is JSON.
#
#   report.sh status              mode, temperatures, CPU limits, charging and settings
#   report.sh mode NAME           switch to hemat | seimbang | game
#   report.sh set KEY VALUE ...   change settings (only known keys, values within range)
#   report.sh detect              find the charging switch (the phone must be charging)
#   report.sh events [N]          the last N lines of the activity log, newest first
#   report.sh start | stop | restart

MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.   # started as "sh report.sh"
. "$MODDIR/common.sh"
load_config

controller_pid() {
  pid=$(cat "$CP_RUN/pid" 2>/dev/null)
  case "$pid" in ''|*[!0-9]*) return 1 ;; esac
  kill -0 "$pid" 2>/dev/null && grep -q controller "/proc/$pid/cmdline" 2>/dev/null && echo "$pid"
}

wake() { pid=$(controller_pid) && kill -HUP "$pid" 2>/dev/null; return 0; }   # check new settings now

start_controller() {
  [ -n "$(controller_pid)" ] && return 0
  mkdir -p "$CP_RUN"
  if command -v setsid > /dev/null 2>&1; then
    setsid sh "$MODDIR/controller.sh" < /dev/null > /dev/null 2>&1 &
  else
    nohup sh "$MODDIR/controller.sh" < /dev/null > /dev/null 2>&1 &
  fi
  i=0
  while [ $i -lt 20 ] && [ -z "$(controller_pid)" ]; do sleep 0.1 2>/dev/null || sleep 1; i=$((i + 1)); done
}

stop_controller() {
  if pid=$(controller_pid); then
    kill "$pid" 2>/dev/null
    i=0
    while [ $i -lt 30 ] && kill -0 "$pid" 2>/dev/null; do sleep 0.1 2>/dev/null || sleep 1; i=$((i + 1)); done
  fi
  # The controller restores everything when it stops; do it here too in case it was killed hard.
  restore
  log_mode none
  rm -f "$CP_RUN/pid" "$CP_RUN/mode"
}

set_values() {
  errors=""
  while [ $# -ge 2 ]; do
    set_key=$1; set_value=$2; shift 2   # not key/value: load_config reads into those
    case " $KEYS " in *" $set_key "*) ;; *) errors="$errors${errors:+, }$set_key"; continue ;; esac
    if valid "$set_key" "$set_value"; then eval "$set_key=\$set_value"; else errors="$errors${errors:+, }$set_key"; fi
  done
  if [ "$CHARGE_RESUME" -ge "$CHARGE_STOP" ]; then
    errors="$errors${errors:+, }CHARGE_RESUME harus di bawah CHARGE_STOP"
    load_config   # keep what was saved
  fi
  if [ -z "$errors" ]; then
    write_config
    wake
    echo '{"ok":1}'
  else
    printf '{"ok":0,"error":"Nilai tidak valid: %s"}\n' "$errors"
  fi
}

json_config() {
  printf '{"mode":"%s"' "$MODE"
  for key in $KEYS; do [ "$key" = MODE ] || eval "printf ',\"%s\":%d' $key \"\$$key\""; done
  printf '}'
}

json_policies() {
  sep=""
  printf '['
  for policy in "$CP_SYS"/devices/system/cpu/cpufreq/policy*; do
    max=$(cat "$policy/cpuinfo_max_freq" 2>/dev/null) || continue
    printf '%s{"name":"%s","max":%d,"limit":%d,"cur":%d}' "$sep" "${policy##*/}" "$max" \
      "$(cat "$policy/scaling_max_freq" 2>/dev/null || echo 0)" "$(cat "$policy/scaling_cur_freq" 2>/dev/null || echo 0)"
    sep=","
  done
  printf ']'
}

status_json() {
  pid=$(controller_pid) || pid=0
  set -- $(read_battery)
  monitor=0; monitor_installed && monitor=1
  fresh=0; read_monitor && fresh=1
  switch=$(cut -d '|' -f 1 "$CP_DATA/switch" 2>/dev/null)
  state=$(cat "$CP_RUN/state.json" 2>/dev/null)
  version=$(sed -n 's/^version=//p' "$MODDIR/module.prop" 2>/dev/null)
  printf '{"running":%d,"version":"%s","main":%d,"battery":{"level":%d,"status":"%s","temp":%d,"current":%d},' \
    "$([ "$pid" -gt 0 ] && echo 1 || echo 0)" "$version" "$(read_main_temp)" "$1" "$2" "$3" "$4"
  printf '"monitor":{"installed":%d,"fresh":%d,"cause":"%s","app":"%s"},"switch":"%s","no_switch":%d,"config":' \
    "$monitor" "$fresh" "$(printf '%s' "$M_CAUSE" | sed 's/[\\"]//g')" "$(printf '%s' "$M_APP" | sed 's/[\\"]//g')" \
    "$switch" "$([ -f "$CP_RUN/no_switch" ] && echo 1 || echo 0)"
  json_config
  printf ',"policies":'
  json_policies
  printf ',"state":%s}\n' "${state:-null}"
}

events_json() {
  n=$1
  case "$n" in ''|*[!0-9]*) n=30 ;; esac
  tail -n "$n" "$EVENTS" 2>/dev/null | awk -F '\t' '
    { ts[NR] = $1; text[NR] = $2; gsub(/[\\"]/, "", text[NR]) }
    END { printf "["; for (i = NR; i >= 1; i--) printf "%s{\"ts\":%d,\"text\":\"%s\"}", (i < NR ? "," : ""), ts[i], text[i]; print "]" }'
}

detect() {
  if ! is_charging; then
    echo '{"ok":0,"error":"Colokkan charger dulu: saklar hanya bisa dicari saat HP sedang mengecas"}'
    return 0
  fi
  mkdir -p "$CP_RUN"
  : > "$CP_RUN/detecting"
  rm -f "$CP_DATA/switch"
  if detect_switch > "$CP_RUN/detect.log"; then ok=1; rm -f "$CP_RUN/no_switch"; else ok=0; : > "$CP_RUN/no_switch"; fi
  rm -f "$CP_RUN/detecting" "$CP_RUN/charge_off"   # charging is on again after the test
  if [ "$ok" = 1 ]; then event "Saklar cas ditemukan: $(cut -d '|' -f 1 "$CP_DATA/switch")"
  else event "Saklar cas tidak ditemukan di HP ini"; fi
  printf '{"ok":%d,"switch":"%s","tried":[' "$ok" "$(cut -d '|' -f 1 "$CP_DATA/switch" 2>/dev/null)"
  awk '{ printf "%s{\"node\":\"%s\",\"result\":\"%s\"}", (NR > 1 ? "," : ""), $1, $2 }' "$CP_RUN/detect.log"
  echo ']}'
  wake
}

case "$1" in
  status) status_json ;;
  mode) set_values MODE "$2" ;;
  set) shift; set_values "$@" ;;
  detect) detect ;;
  events) events_json "$2" ;;
  start) start_controller; status_json ;;
  stop) stop_controller; status_json ;;
  restart) stop_controller; start_controller; status_json ;;
  *)
    echo "Pakai: report.sh status|mode NAME|set KEY VALUE ...|detect|events [N]|start|stop|restart" >&2
    exit 1
    ;;
esac
