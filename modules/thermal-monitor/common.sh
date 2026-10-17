# Cogan Thermal Monitor: shared paths, settings and sensor readers.
# POSIX sh (Android mksh, KernelSU busybox sh). Only reads the system; never writes to /sys.
# The CT_* paths can be overridden, which the offline tests use with a fake /sys and /proc.

MODDIR=${MODDIR:-${0%/*}}
CT_DATA=${CT_DATA:-/data/adb/cogan_thermal}
CT_SYS=${CT_SYS:-/sys}
CT_PROC=${CT_PROC:-/proc}
CT_OUT=${CT_OUT:-/sdcard/Download/CoganThermal}
CT_RUN=$CT_DATA/run
CONFIG=$CT_DATA/config

# Settings (WebUI writes $CONFIG; only these keys and plain numbers are accepted).
INTERVAL=20
RETENTION_DAYS=7
HOT_TEMP=42
NOTIFY=0
NOTIFY_TEMP=45

load_config() {
  [ -f "$CONFIG" ] || return 0
  while IFS='=' read -r key value; do
    case "$value" in ''|*[!0-9]*) continue ;; esac
    case "$key" in
      INTERVAL) [ "$value" -ge 10 ] && [ "$value" -le 300 ] && INTERVAL=$value ;;
      RETENTION_DAYS) [ "$value" -ge 1 ] && [ "$value" -le 30 ] && RETENTION_DAYS=$value ;;
      HOT_TEMP) [ "$value" -ge 30 ] && [ "$value" -le 90 ] && HOT_TEMP=$value ;;
      NOTIFY) [ "$value" -le 1 ] && NOTIFY=$value ;;
      NOTIFY_TEMP) [ "$value" -ge 30 ] && [ "$value" -le 90 ] && NOTIFY_TEMP=$value ;;
    esac
  done < "$CONFIG"
}

write_config() {
  mkdir -p "$CT_DATA"
  {
    echo "INTERVAL=$INTERVAL"
    echo "RETENTION_DAYS=$RETENTION_DAYS"
    echo "HOT_TEMP=$HOT_TEMP"
    echo "NOTIFY=$NOTIFY"
    echo "NOTIFY_TEMP=$NOTIFY_TEMP"
  } > "$CONFIG.tmp" && mv "$CONFIG.tmp" "$CONFIG"
}

# Every thermal zone as "type=tenths_of_degC", comma separated; one value per type (the highest).
read_zones() {
  for zone in "$CT_SYS"/class/thermal/thermal_zone*; do
    [ -r "$zone/temp" ] || continue
    type=$(cat "$zone/type" 2>/dev/null) || continue
    temp=$(cat "$zone/temp" 2>/dev/null) || continue
    echo "$type $temp"
  done | awk '
    {
      t = $NF + 0; name = $1
      gsub(/[^A-Za-z0-9_.+-]/, "_", name)
      v = (t >= 1000 || t <= -1000) ? int(t / 100) : t * 10   # millidegrees or degrees
      if (v == 0 || v < -400 || v > 1500 || name == "") next   # 0 = sensor not in use
      if (!(name in best) || v > best[name]) { if (!(name in best)) order[++n] = name; best[name] = v }
    }
    END { for (i = 1; i <= n; i++) printf "%s%s=%d", (i > 1 ? "," : ""), order[i], best[order[i]] }'
}

# Battery: "charging current_mA temp_tenths" (charging 1/0, current as a positive number).
read_battery() {
  bat=$CT_SYS/class/power_supply/battery
  status=$(cat "$bat/status" 2>/dev/null)
  current=$(cat "$bat/current_now" 2>/dev/null)
  temp=$(cat "$bat/temp" 2>/dev/null)
  case "$status" in Charging) charging=1 ;; *) charging=0 ;; esac
  case "$current" in ''|*[!0-9-]*) current=0 ;; esac
  case "$temp" in ''|*[!0-9-]*) temp=-999 ;; esac
  current=${current#-}
  # The kernel ABI says microamps (most phones); a few report milliamps. A design capacity in
  # microamp-hours (e.g. 5000000) means microamps too, so a small charging current stays right.
  design=$(cat "$bat/charge_full_design" 2>/dev/null)
  case "$design" in ''|*[!0-9]*) design=0 ;; esac
  if [ "$current" -ge 20000 ] || [ "$design" -ge 100000 ]; then current=$((current / 1000)); fi
  echo "$charging $current $temp"
}

# GPU load in percent, or -1 when the kernel does not expose it.
read_gpu() {
  for node in "$CT_SYS/kernel/ged/hal/gpu_utilization" "$CT_SYS/class/kgsl/kgsl-3d0/gpu_busy_percentage" \
              "$CT_SYS/class/misc/mali0/device/utilization" "$CT_SYS/kernel/gpu/gpu_busy"; do
    [ -r "$node" ] || continue
    value=$(awk '{ v = $1; gsub(/[^0-9]/, "", v); if (v != "") { print v + 0; exit } }' "$node" 2>/dev/null)
    case "$value" in ''|*[!0-9]*) continue ;; esac
    [ "$value" -le 100 ] && { echo "$value"; return; }
  done
  echo -1
}

# Screen: 1 on, 0 off, -1 unknown. The panel backlight needs no dumpsys call; Android's own
# screen state is the fallback.
read_screen() {
  for node in "$CT_SYS"/class/leds/lcd-backlight/brightness "$CT_SYS"/class/backlight/*/brightness; do
    [ -r "$node" ] || continue
    value=$(cat "$node" 2>/dev/null)
    case "$value" in ''|*[!0-9]*) continue ;; esac
    [ "$value" -gt 0 ] && echo 1 || echo 0
    return
  done
  case "$(dumpsys deviceidle get screen 2>/dev/null)" in
    true*) echo 1 ;;
    false*) echo 0 ;;
    *) echo -1 ;;
  esac
}

# Foreground app package from the focused window or app ("-" when unknown). The short
# "displays" section is enough on Android 10+; the full dump is the fallback.
focus_pkg() {
  sed -n -e 's#.*mCurrentFocus=.* u[0-9]* \([A-Za-z0-9_.]*\)/.*#\1#p' \
         -e 's#.*mFocusedApp=.* u[0-9]* \([A-Za-z0-9_.]*\)/.*#\1#p' | head -n 1
}
read_foreground() {
  pkg=$(dumpsys window displays 2>/dev/null | focus_pkg)
  [ -n "$pkg" ] || pkg=$(dumpsys window 2>/dev/null | focus_pkg)
  echo "${pkg:--}"
}

# CPU frequency per policy in MHz: "p0:1800,p4:2850".
read_freqs() {
  out=""
  for policy in "$CT_SYS"/devices/system/cpu/cpufreq/policy*; do
    khz=$(cat "$policy/scaling_cur_freq" 2>/dev/null) || continue
    case "$khz" in ''|*[!0-9]*) continue ;; esac
    out="$out${out:+,}p${policy##*policy}:$((khz / 1000))"
  done
  echo "${out:--}"
}

# Bytes moved on Wi-Fi and cellular interfaces: "wifi_bytes cell_bytes".
read_net_bytes() {
  wifi=0; cell=0
  for dev in "$CT_SYS"/class/net/*; do
    name=${dev##*/}
    rx=$(cat "$dev/statistics/rx_bytes" 2>/dev/null) || continue
    tx=$(cat "$dev/statistics/tx_bytes" 2>/dev/null) || continue
    case "$name" in
      wlan*) wifi=$((wifi + rx + tx)) ;;
      ccmni*|rmnet*|seth*|ccemni*|ccinet*) cell=$((cell + rx + tx)) ;;
    esac
  done
  echo "$wifi $cell"
}

# Process name for a pid: the first word of its command line, e.g. "com.instagram.android".
proc_name() {
  name=$(tr '\0' '\n' < "$CT_PROC/$1/cmdline" 2>/dev/null | head -n 1)
  name=${name##*/}; name=${name%%:*}
  [ -n "$name" ] || name=$2
  echo "$name" | sed 's/[^A-Za-z0-9_.+-]/_/g'
}
