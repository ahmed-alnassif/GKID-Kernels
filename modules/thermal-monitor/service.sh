#!/system/bin/sh
# Cogan Thermal Monitor: start the sampler once Android has finished booting.
MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.   # started as "sh report.sh"
until [ "$(getprop sys.boot_completed)" = 1 ]; do sleep 5; done
sleep 15
sh "$MODDIR/report.sh" start > /dev/null 2>&1
