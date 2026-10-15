#!/usr/bin/env bash

# Define target defconfig location
DEFCONFIG="arch/arm64/configs/gki_defconfig"

function apply_config(){
  cat "$1" >> "$2"
}

if [ "$KSU" != "no" ]; then
  # Base KSU Config & Dependencies
  echo "⚙️ Added KSU configuration"
  cat >> $DEFCONFIG <<EOF
CONFIG_KSU=y
CONFIG_KPM=y
EOF
fi

echo "🧩 Adding Built-in Features"
apply_config "$WORKDIR/configs/features.config" "$DEFCONFIG"

if [ "$KSU_SUSFS" = "true" ]; then
  echo "🔧 Mode: SuSFS Hook Enabled"
  apply_config "$WORKDIR/configs/susfs.config" "$DEFCONFIG"
fi

echo "⚙️ Adding Compatibility GKI Networking and Filesystem configs"
apply_config "$WORKDIR/configs/compat.config" "$DEFCONFIG"

echo "⚙️ Adding Universal Performance Tuning"
# Fail closed on unexpected values instead of silently changing networking behavior.
case "${NETWORKING:-true}" in
  true|false) ;;
  *) echo "ERROR: NETWORKING must be true or false" >&2; exit 1 ;;
esac
if [ "${NETWORKING:-true}" = "false" ]; then
  # Keep Android/GKI compatibility networking from compat.config intact.
  # Only omit the optional networking extras section in custom.config.
  echo "ℹ️ Networking extras disabled; preserving base Android networking"
  sed '/^# Networking extras$/,$d' "$WORKDIR/configs/custom.config" >> "$DEFCONFIG"
else
  apply_config "$WORKDIR/configs/custom.config" "$DEFCONFIG"
fi

if [ "$C_LTO" != "true" ]; then
  if [ "$KSU_COMPAT" = "true" ] || [ "$KSU" = "vnlto" ]; then
    LTO="noneLTO"
  fi
fi

case "$LTO" in
  thinLTO)
    echo "🔥 ThinLTO optimizations enabled"
    cat >> "$DEFCONFIG" <<EOF
CONFIG_LTO_NONE=n
CONFIG_LTO_CLANG_THIN=y
EOF
    ;;
  fullLTO)
    echo "🔥 Full LTO optimizations enabled"
    cat >> "$DEFCONFIG" <<EOF
CONFIG_LTO_NONE=n
CONFIG_LTO_CLANG_FULL=y
EOF
    ;;
  *)
    echo "ℹ️ LTO disabled or not specified"
    ;;
esac

if [ "$No_DS" = "true" ]; then
  export DROIDSPACES="false"
  export NH="false"
fi

if [ "$DROIDSPACES" = "true" ]; then
  echo "🐳 DroidSpaces support enabled"
  apply_config "$WORKDIR/configs/droidspaces.config" "$DEFCONFIG"
fi

if [ "$NH" = "true" ]; then
  echo "🐉 NetHunter support enabled"
  apply_config "$WORKDIR/configs/nethunter.config" "$DEFCONFIG"
fi

if [ "$KSU_COMPAT" != "true" ]; then
  echo "🔧 Disable useless debugging configs for performance and resources"
  cat >> $DEFCONFIG <<EOF
# Disable useless debugging configs for performance and resources
CONFIG_RCU_TRACE=n
EOF
fi
