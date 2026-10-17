# Cogan Thermal Monitor: installer step (sourced by KernelSU / Magisk with MODPATH set).
SKIPUNZIP=0
ui_print "- Cogan Thermal Monitor"
set_perm_recursive "$MODPATH" 0 0 0755 0644
for f in service.sh sampler.sh report.sh action.sh uninstall.sh; do set_perm "$MODPATH/$f" 0 0 0755; done
mkdir -p /data/adb/cogan_thermal/data
ui_print "- Mencatat suhu tiap 20 detik setelah reboot, riwayat disimpan 7 hari"
ui_print "- Buka WebUI modul untuk ringkasan dan 💾 Simpan log"
ui_print "- Log tersimpan di /sdcard/Download/CoganThermal"
