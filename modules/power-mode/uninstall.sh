#!/system/bin/sh
# Cogan Power Mode: put CPU speed and charging back to normal, then remove the settings.
MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.
. "$MODDIR/common.sh"
restore
log_mode none
rm -rf "$CP_DATA"
