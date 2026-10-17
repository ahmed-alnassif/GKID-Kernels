#!/system/bin/sh
# Cogan Thermal Monitor: the manager's Action button shows the last hour and makes sure the sampler runs.
MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.   # started as "sh report.sh"
sh "$MODDIR/report.sh" start > /dev/null 2>&1
sh "$MODDIR/report.sh" text 3600
echo
echo "Grafik, rentang lain dan 💾 Simpan log ada di WebUI modul ini."
