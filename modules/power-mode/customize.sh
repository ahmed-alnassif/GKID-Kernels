# Cogan Power Mode: installer step (sourced by KernelSU / Magisk with MODPATH set).
SKIPUNZIP=0
ui_print "- Cogan Power Mode"
set_perm_recursive "$MODPATH" 0 0 0755 0644
for f in service.sh controller.sh report.sh action.sh uninstall.sh; do set_perm "$MODPATH/$f" 0 0 0755; done
mkdir -p /data/adb/cogan_power
ui_print "- Mode bawaan: Seimbang (suhu dijaga ≤ 42 °C)"
ui_print "- Auto cut charging: berhenti 80%, lanjut 75%"
ui_print "- Paling pas dipasang bersama Cogan Thermal Monitor"
ui_print "- Atur lewat WebUI modul; tombol Action = ganti mode"
