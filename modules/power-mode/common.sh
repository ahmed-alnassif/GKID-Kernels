# Cogan Power Mode: shared paths, settings and the few system knobs it touches.
# POSIX sh (Android mksh, KernelSU busybox sh). It only writes CPU frequency limits, the top-app
# uclamp boost and the charging switch, and puts all of them back when it stops.
# The CP_* / CT_* paths can be overridden, which the offline tests use with a fake /sys.

MODDIR=${MODDIR:-${0%/*}}
CP_DATA=${CP_DATA:-/data/adb/cogan_power}
CP_SYS=${CP_SYS:-/sys}
CP_PROC=${CP_PROC:-/proc}
CP_CPUCTL=${CP_CPUCTL:-/dev/cpuctl}
CT_DATA=${CT_DATA:-/data/adb/cogan_thermal}           # Cogan Thermal Monitor's data
CT_MOD=${CT_MOD:-/data/adb/modules/cogan_thermal}     # and its module folder
CP_RUN=$CP_DATA/run
CONFIG=$CP_DATA/config
EVENTS=$CP_DATA/events.tsv
BATTERY=$CP_SYS/class/power_supply/battery

# Settings (the WebUI writes $CONFIG; only these keys and values within range are accepted).
KEYS="MODE TARGET_TEMP GAME_LIMIT SAVER_CAP GAME_BOOST CHARGE_CTRL CHARGE_STOP CHARGE_RESUME BATT_TEMP_STOP HEAT_PAUSE_CHARGE INTERVAL"
MODE=seimbang          # hemat | seimbang | game
TARGET_TEMP=42         # Seimbang keeps the processor at or below this (°C); Hemat 3 °C lower
GAME_LIMIT=48          # Game only steps in at this temperature (°C)
SAVER_CAP=60           # Hemat: top speed of the big cores (% of their maximum)
GAME_BOOST=1           # Game: give the app on screen a minimum CPU share (uclamp)
CHARGE_CTRL=1          # auto cut charging on/off
CHARGE_STOP=80         # stop charging at this battery level (%), 100 = never
CHARGE_RESUME=75       # charge again at this level (%)
BATT_TEMP_STOP=42      # pause charging while the battery is this hot (°C), resume 3 °C lower
HEAT_PAUSE_CHARGE=1    # Seimbang: pause charging when charging is what heats the phone
INTERVAL=10            # seconds between checks

limits() {   # limits KEY -> "min max" of a numeric setting
  case "$1" in
    TARGET_TEMP) echo "35 55" ;;
    GAME_LIMIT) echo "40 60" ;;
    SAVER_CAP) echo "30 90" ;;
    GAME_BOOST|CHARGE_CTRL|HEAT_PAUSE_CHARGE) echo "0 1" ;;
    CHARGE_STOP) echo "50 100" ;;
    CHARGE_RESUME) echo "40 99" ;;
    BATT_TEMP_STOP) echo "35 50" ;;
    INTERVAL) echo "5 60" ;;
    *) return 1 ;;
  esac
}

valid() {   # valid KEY VALUE
  if [ "$1" = MODE ]; then
    case "$2" in hemat|seimbang|game) return 0 ;; *) return 1 ;; esac
  fi
  case "$2" in ''|*[!0-9]*) return 1 ;; esac
  set -- "$2" $(limits "$1")
  [ $# = 3 ] && [ "$1" -ge "$2" ] && [ "$1" -le "$3" ]
}

load_config() {
  [ -f "$CONFIG" ] || return 0
  while IFS='=' read -r key value; do
    valid "$key" "$value" && eval "$key=\$value"   # key is one of the settings above
  done < "$CONFIG"
  [ "$CHARGE_RESUME" -lt "$CHARGE_STOP" ] || CHARGE_RESUME=$((CHARGE_STOP - 5))
}

write_config() {
  mkdir -p "$CP_DATA"
  for key in $KEYS; do eval "echo \"$key=\$$key\""; done > "$CONFIG.tmp" && mv "$CONFIG.tmp" "$CONFIG"
}

event() {   # one line in the WebUI's activity log
  mkdir -p "$CP_DATA"
  printf '%s\t%s\n' "$(date +%s)" "$*" >> "$EVENTS"
}

deg() { echo "$(($1 / 10)).$(( ($1 < 0 ? -$1 : $1) % 10 ))"; }

# Hottest CPU/GPU sensor in tenths of °C.
read_main_temp() {
  for zone in "$CP_SYS"/class/thermal/thermal_zone*; do
    [ -r "$zone/temp" ] || continue
    echo "$(cat "$zone/type" 2>/dev/null) $(cat "$zone/temp" 2>/dev/null)"
  done | awk -f "$MODDIR/power.awk"
}

# Battery: "level status temp_tenths current_mA"; status is charging, full, discharging or idle.
read_battery() {
  level=$(cat "$BATTERY/capacity" 2>/dev/null)
  status=$(cat "$BATTERY/status" 2>/dev/null)
  temp=$(cat "$BATTERY/temp" 2>/dev/null)
  current=$(cat "$BATTERY/current_now" 2>/dev/null)
  design=$(cat "$BATTERY/charge_full_design" 2>/dev/null)
  case "$level" in ''|*[!0-9]*) level=-1 ;; esac
  case "$temp" in ''|*[!0-9-]*) temp=-999 ;; esac
  case "$current" in ''|*[!0-9-]*) current=0 ;; esac
  case "$design" in ''|*[!0-9]*) design=0 ;; esac
  current=${current#-}
  if [ "$current" -ge 20000 ] || [ "$design" -ge 100000 ]; then current=$((current / 1000)); fi   # microamps
  case "$status" in Charging) status=charging ;; Full) status=full ;; Discharging) status=discharging ;; *) status=idle ;; esac
  echo "$level $status $temp $current"
}

monitor_installed() { [ -f "$CT_MOD/module.prop" ] && [ ! -f "$CT_MOD/disable" ]; }

# Latest report of Cogan Thermal Monitor (see its sampler.sh) when it is at most 90 s old:
# sets M_MAIN, M_APP and M_CAUSE.
read_monitor() {
  M_MAIN=""; M_APP=""; M_CAUSE=""
  IFS='	' read -r m_ts m_main _ _ m_app m_cause < "$CT_DATA/run/latest" 2>/dev/null || return 1
  case "$m_ts" in ''|*[!0-9]*) return 1 ;; esac
  [ $(($(date +%s) - m_ts)) -le 90 ] || return 1
  M_MAIN=$m_main; M_APP=$m_app; M_CAUSE=$m_cause
}

# Tell Cogan Thermal Monitor which mode is active from now on; its summaries report per mode.
log_mode() {
  [ -d "$CT_DATA" ] || return 0
  last=$(tail -n 1 "$CT_DATA/modes.tsv" 2>/dev/null | cut -f 2)
  [ "$last" = "$1" ] || printf '%s\t%s\n' "$(date +%s)" "$1" >> "$CT_DATA/modes.tsv"
}

# CPU top speed: the big clusters at BIG % of their maximum, the slowest cluster at LITTLE %.
# The nearest real frequency step at or below the target is used when the kernel lists them.
set_cpu_cap() {
  big=$1; little=$2
  lowest=$(cat "$CP_SYS"/devices/system/cpu/cpufreq/policy*/cpuinfo_max_freq 2>/dev/null | sort -n | head -n 1)
  highest=$(cat "$CP_SYS"/devices/system/cpu/cpufreq/policy*/cpuinfo_max_freq 2>/dev/null | sort -n | tail -n 1)
  for policy in "$CP_SYS"/devices/system/cpu/cpufreq/policy*; do
    max=$(cat "$policy/cpuinfo_max_freq" 2>/dev/null)
    min=$(cat "$policy/cpuinfo_min_freq" 2>/dev/null)
    case "$max$min" in ''|*[!0-9]*) continue ;; esac
    pct=$big
    [ "$max" = "$lowest" ] && [ "$lowest" != "$highest" ] && pct=$little
    if [ "$pct" -ge 100 ]; then
      freq=$max
    else
      want=$((max / 100 * pct))
      [ "$want" -lt "$min" ] && want=$min
      freq=$(awk -v want="$want" '{ for (i = 1; i <= NF; i++) if ($i + 0 <= want && $i + 0 > best) best = $i + 0 } END { print best + 0 }' \
        "$policy/scaling_available_frequencies" 2>/dev/null)
      [ "${freq:-0}" -gt 0 ] || freq=$want
    fi
    [ "$(cat "$policy/scaling_max_freq" 2>/dev/null)" = "$freq" ] || echo "$freq" > "$policy/scaling_max_freq" 2>/dev/null
  done
}

# Game boost: the app on screen gets at least 20 % CPU capacity (uclamp.min of the top-app group).
set_boost() {   # set_boost 0|1
  node=$CP_CPUCTL/top-app/cpu.uclamp.min
  [ -f "$node" ] || return 0
  if [ "$1" = 1 ]; then
    [ -f "$CP_RUN/uclamp.orig" ] && return 0
    mkdir -p "$CP_RUN"
    cat "$node" > "$CP_RUN/uclamp.orig" 2>/dev/null
    echo 20 > "$node" 2>/dev/null
  elif [ -f "$CP_RUN/uclamp.orig" ]; then
    cat "$CP_RUN/uclamp.orig" > "$node" 2>/dev/null
    rm -f "$CP_RUN/uclamp.orig"
  fi
}

# Charging switches known from many phones, as "node|on|off" (proc/... is under /proc, the rest
# under /sys). The first one that really stops and restarts charging is kept in $CP_DATA/switch.
SWITCHES="class/power_supply/battery/input_suspend|0|1
class/power_supply/battery/charging_enabled|1|0
class/power_supply/battery/battery_charging_enabled|1|0
class/power_supply/battery/charge_disable|0|1
class/qcom-battery/input_suspend|0|1
class/power_supply/usb/input_suspend|0|1
class/power_supply/main/input_suspend|0|1
devices/platform/charger/bypass_charger|0|1
proc/mtk_battery_cmd/current_cmd|0 0|0 1
proc/mtk_battery_cmd/en_power_path|1|0
class/power_supply/battery/batt_slate_mode|0|1
class/power_supply/battery/op_disable_charge|0|1
class/power_supply/battery/mmi_charging_enable|1|0"

switch_node() {
  case "$1" in proc/*) echo "$CP_PROC/${1#proc/}" ;; *) echo "$CP_SYS/$1" ;; esac
}

read_switch() {   # sets SW_NODE SW_ON SW_OFF from the saved switch
  IFS='|' read -r sw_rel SW_ON SW_OFF < "$CP_DATA/switch" 2>/dev/null || return 1
  [ -n "$sw_rel" ] || return 1
  SW_NODE=$(switch_node "$sw_rel")
}

charge_set() {   # charge_set on|off
  read_switch || return 1
  if [ "$1" = on ]; then value=$SW_ON; else value=$SW_OFF; fi
  echo "$value" > "$SW_NODE" 2>/dev/null
}

is_charging() { [ "$(cat "$BATTERY/status" 2>/dev/null)" = Charging ]; }

wait_charging() {   # wait_charging yes|no SECONDS
  i=0
  while :; do
    if is_charging; then [ "$1" = yes ] && return 0; else [ "$1" = no ] && return 0; fi
    [ "$i" -ge "$2" ] && return 1
    sleep 1
    i=$((i + 1))
  done
}

# Try each switch while the phone charges; print one "node result" line per switch tried.
detect_switch() {
  is_charging || return 2
  found=1
  while IFS='|' read -r rel on off; do
    node=$(switch_node "$rel")
    [ -f "$node" ] || continue
    if ! echo "$off" > "$node" 2>/dev/null; then echo "$rel tidak_bisa_ditulis"; continue; fi
    if wait_charging no 6; then
      echo "$on" > "$node" 2>/dev/null
      if wait_charging yes 15; then
        echo "$rel|$on|$off" > "$CP_DATA/switch"
        echo "$rel ok"
        found=0
        break
      fi
      echo "$rel tidak_lanjut"
    else
      echo "$rel tidak_berpengaruh"
    fi
    echo "$on" > "$node" 2>/dev/null
    wait_charging yes 10
  done <<EOF
$SWITCHES
EOF
  return $found
}

# Back to normal: full CPU speed, no boost, charging on.
restore() {
  set_cpu_cap 100 100
  set_boost 0
  charge_set on
  rm -f "$CP_RUN/charge_off" "$CP_RUN/level" "$CP_RUN/cool" "$CP_RUN/prev"
}
