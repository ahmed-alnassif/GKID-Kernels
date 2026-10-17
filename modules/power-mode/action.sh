#!/system/bin/sh
# Cogan Power Mode: the manager's Action button switches to the next mode (Hemat → Seimbang → Game).
MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.
. "$MODDIR/common.sh"
load_config
case "$MODE" in hemat) next=seimbang ;; seimbang) next=game ;; *) next=hemat ;; esac
sh "$MODDIR/report.sh" start > /dev/null 2>&1
sh "$MODDIR/report.sh" mode "$next" > /dev/null
case "$next" in
  hemat) echo "🌿 Mode Hemat: CPU besar maks $SAVER_CAP%, suhu dijaga ≤ $((TARGET_TEMP - 3)) °C" ;;
  seimbang) echo "⚖️ Mode Seimbang: suhu dijaga ≤ $TARGET_TEMP °C" ;;
  game) echo "🎮 Mode Game: performa penuh, rem darurat di $GAME_LIMIT °C" ;;
esac
if [ "$CHARGE_CTRL" = 1 ]; then
  echo "🔌 Auto cut charging: berhenti $CHARGE_STOP%, lanjut $CHARGE_RESUME%, jeda bila baterai ≥ $BATT_TEMP_STOP °C"
else
  echo "🔌 Auto cut charging: mati"
fi
echo
echo "Tekan Action lagi untuk mode berikutnya. Setelan lengkap ada di WebUI modul ini."
