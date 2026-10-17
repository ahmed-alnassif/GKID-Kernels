#!/system/bin/sh
# Cogan Power Mode: the control loop. Every INTERVAL seconds it reads the processor temperature,
# the battery and the latest report of Cogan Thermal Monitor (what heats the phone), then:
#
#   CPU     Hemat caps the big cores at SAVER_CAP %; Seimbang (TARGET_TEMP) and Hemat (3 °C lower)
#           lower the CPU top speed 10 % per step while too hot and give it back when cool again;
#           Game runs free and only steps in at GAME_LIMIT.
#   Charge  stops at CHARGE_STOP % and resumes at CHARGE_RESUME %, pauses while the battery is
#           hotter than BATT_TEMP_STOP and, in Seimbang, while charging is what heats the phone.
#
# Usage: controller.sh [--once]

MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.   # started as "sh controller.sh"
. "$MODDIR/common.sh"

state() { cat "$CP_RUN/$1" 2>/dev/null || echo "$2"; }

step() {
  now=$(date +%s)
  main=$(read_main_temp)
  case "$main" in ''|*[!0-9-]*) main=-9999 ;; esac
  set -- $(read_battery)
  level_pct=$1; status=$2; btemp=$3; current=$4

  # What heats the phone: Cogan Thermal Monitor's report, or a simple guess without it.
  if read_monitor; then
    source=monitor; cause=$M_CAUSE; app=$M_APP
  else
    source=sensor; app=""; cause=""
    [ "$status" = charging ] && [ "$current" -ge 1500 ] && cause="Cas cepat"
  fi

  # A new mode starts from full speed.
  if [ "$(state mode "")" != "$MODE" ]; then
    [ -n "$(state mode "")" ] && event "Mode: $(mode_label "$MODE")"
    echo "$MODE" > "$CP_RUN/mode"
    log_mode "$MODE"
    rm -f "$CP_RUN/level" "$CP_RUN/cool"
  fi

  # Charging first: when the monitor says charging is the heat source, pausing it may be enough.
  charge_step

  # CPU: one step (10 %) down per check while too hot and not already cooling, one step up after
  # two checks at least 2 °C under the limit. While charging is paused for heat, the CPU only
  # steps in if the temperature still rises.
  case "$MODE" in
    hemat) limit=$((TARGET_TEMP - 3)) ;;
    game) limit=$GAME_LIMIT ;;
    *) limit=$TARGET_TEMP ;;
  esac
  step_level=$(state level 0); cool=$(state cool 0); prev=$(state prev "$main")
  old_level=$step_level
  rising=$((prev - 5))
  case " $(state charge_off "") " in *" panas "*) rising=$prev ;; esac
  [ "$paused_for_heat" = 1 ] && rising=9999   # charging was just paused: give that a check first
  if [ "$main" -ge $((limit * 10)) ]; then
    cool=0
    [ "$main" -gt "$rising" ] && [ "$step_level" -lt 6 ] && step_level=$((step_level + 1))
  elif [ "$main" -le $(((limit - 2) * 10)) ] && [ "$step_level" -gt 0 ]; then
    cool=$((cool + 1))
    [ "$cool" -ge 2 ] && { step_level=$((step_level - 1)); cool=0; }
  else
    cool=0
  fi
  echo "$step_level" > "$CP_RUN/level"; echo "$cool" > "$CP_RUN/cool"; echo "$main" > "$CP_RUN/prev"
  if [ "$MODE" = hemat ]; then big=$((SAVER_CAP - step_level * 10)); else big=$((100 - step_level * 10)); fi
  [ "$big" -lt 20 ] && big=20
  little=$((big + 20)); [ "$little" -gt 100 ] && little=100
  set_cpu_cap "$big" "$little"
  if [ "$step_level" -gt "$old_level" ]; then
    event "Suhu $(deg "$main") °C ≥ $limit °C${cause:+ ($cause)}: CPU dibatasi $big%"
  elif [ "$step_level" -lt "$old_level" ]; then
    event "Suhu turun ke $(deg "$main") °C: CPU $big%"
  fi
  if [ "$MODE" = game ] && [ "$GAME_BOOST" = 1 ]; then set_boost 1; else set_boost 0; fi
  write_state
}

charge_step() {
  paused_for_heat=0
  [ -f "$CP_RUN/detecting" ] && return 0   # the WebUI is testing switches right now
  was=$(state charge_off "")
  reasons=""
  if [ "$CHARGE_CTRL" = 1 ] && [ "$level_pct" -ge 0 ]; then
    case " $was " in
      *" batas "*) [ "$level_pct" -gt "$CHARGE_RESUME" ] && reasons="batas" ;;
      *) [ "$CHARGE_STOP" -lt 100 ] && [ "$level_pct" -ge "$CHARGE_STOP" ] && { [ "$status" = charging ] || [ "$status" = full ]; } && reasons="batas" ;;
    esac
    case " $was " in
      *" baterai "*) [ "$btemp" -gt $(((BATT_TEMP_STOP - 3) * 10)) ] && reasons="$reasons baterai" ;;
      *) [ "$btemp" -ge $((BATT_TEMP_STOP * 10)) ] && [ "$status" = charging ] && reasons="$reasons baterai" ;;
    esac
    if [ "$MODE" = seimbang ] && [ "$HEAT_PAUSE_CHARGE" = 1 ]; then
      case " $was " in
        *" panas "*) [ "$main" -gt $(((TARGET_TEMP - 3) * 10)) ] && reasons="$reasons panas" ;;
        *) [ "$status" = charging ] && [ "$main" -ge $((TARGET_TEMP * 10)) ] && case "$cause" in "Cas cepat"|Mengecas*) reasons="$reasons panas" ;; esac ;;
      esac
    fi
    [ "$level_pct" -le 15 ] && reasons=""   # a nearly empty battery always charges
  fi
  reasons=${reasons# }

  if [ "$reasons" = "$was" ]; then
    # Some chargers turn charging back on after a replug: switch it off again.
    [ -n "$reasons" ] && [ "$status" = charging ] && charge_set off
    return 0
  fi
  if [ -z "$reasons" ]; then
    charge_set on
    rm -f "$CP_RUN/charge_off"
    event "Cas dilanjutkan (baterai $level_pct%, $(deg "$btemp") °C)"
    return 0
  fi
  if ! read_switch; then
    # Finding the switch needs the phone to be charging right now; try once per start.
    [ -f "$CP_RUN/no_switch" ] || [ "$status" != charging ] && return 0
    event "Mencari saklar cas…"
    if detect_switch > "$CP_RUN/detect.log"; then
      event "Saklar cas ditemukan: $(cut -d '|' -f 1 "$CP_DATA/switch")"
    else
      : > "$CP_RUN/no_switch"
      event "Saklar cas tidak ditemukan di HP ini: auto cut charging tidak bisa dipakai"
      return 0
    fi
  fi
  charge_set off
  echo "$reasons" > "$CP_RUN/charge_off"
  case " $was " in *" panas "*) ;; *) case " $reasons " in *" panas "*) paused_for_heat=1 ;; esac ;; esac
  case " $reasons " in
    *" panas "*) event "Panas $(deg "$main") °C karena cas: cas dijeda sampai $((TARGET_TEMP - 3)) °C" ;;
    *" baterai "*) event "Baterai $(deg "$btemp") °C: cas dijeda sampai $((BATT_TEMP_STOP - 3)) °C" ;;
    *) event "Baterai $level_pct%: cas dihentikan, lanjut di $CHARGE_RESUME%" ;;
  esac
}

mode_label() { case "$1" in hemat) echo Hemat ;; game) echo Game ;; *) echo Seimbang ;; esac; }

jstr() { printf '%s' "$1" | sed 's/[\\"]//g'; }

write_state() {
  printf '{"ts":%d,"mode":"%s","main":%d,"limit":%d,"level":%d,"big":%d,"little":%d,"battery":{"level":%d,"status":"%s","temp":%d,"current":%d},"charge_off":"%s","source":"%s","cause":"%s","app":"%s","boost":%d}\n' \
    "$now" "$MODE" "$main" "$limit" "$step_level" "$big" "$little" "$level_pct" "$status" "$btemp" "$current" \
    "$(state charge_off "")" "$source" "$(jstr "$cause")" "$(jstr "$app")" "$([ -f "$CP_RUN/uclamp.orig" ] && echo 1 || echo 0)" \
    > "$CP_RUN/state.json.tmp" && mv "$CP_RUN/state.json.tmp" "$CP_RUN/state.json"
}

load_config
mkdir -p "$CP_RUN"
if [ "$1" = "--once" ]; then
  step
  exit 0
fi

echo $$ > "$CP_RUN/pid"
rm -f "$CP_RUN/mode" "$CP_RUN/no_switch"
event "Cogan Power Mode mulai: mode $(mode_label "$MODE")"
stop=0; sleeper=""
trap 'stop=1; [ -n "$sleeper" ] && kill "$sleeper" 2>/dev/null' TERM INT
trap '[ -n "$sleeper" ] && kill "$sleeper" 2>/dev/null' HUP   # new settings: check right away
count=0
while [ "$stop" = 0 ]; do
  [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/remove" ] && break
  load_config
  step
  count=$((count + 1))
  if [ $((count % 360)) = 0 ] && [ "$(wc -l < "$EVENTS")" -gt 300 ]; then
    tail -n 200 "$EVENTS" > "$EVENTS.tmp" && mv "$EVENTS.tmp" "$EVENTS"
  fi
  sleep "$INTERVAL" &
  sleeper=$!
  wait "$sleeper"
  sleeper=""
done
restore
log_mode none
event "Cogan Power Mode berhenti: CPU dan cas kembali normal"
rm -f "$CP_RUN/pid" "$CP_RUN/mode"
