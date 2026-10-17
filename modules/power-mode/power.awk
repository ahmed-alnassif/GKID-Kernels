# Cogan Power Mode: hottest CPU/GPU sensor from "type temp" lines (millidegrees or degrees), in tenths
# of °C. Same reading as Cogan Thermal Monitor's main_temp(), so both modules show the same number.
BEGIN { best = -9999; any = -9999 }
{
    t = $NF + 0
    v = (t >= 1000 || t <= -1000) ? int(t / 100) : t * 10
    if (v == 0 || v < -400 || v > 1500) next
    if (v > any) any = v
    if (cpu_or_gpu($1) && v > best) best = v
}
END { print (best > -9999 ? best : any) }

# The monitor's groups in its order: GPU first, then everything that is not the processor, then CPU.
function cpu_or_gpu(type,   t) {
    t = tolower(type)
    if (t ~ /gpu|mali/) return 1
    if (t ~ /batt|^bat_|_bat|bms|charg|chg|usb|wlc|vbus|skin|shell|back|board|ap_ntc|case|frame|xo_therm|quiet|ltepa_ntc/) return 0
    if (t ~ /apu|npu|^ai|vpu|mdla|modem|^md|mdpa|^pa_|_pa_|^pa$|nrpa|^nr|lte|rfic|^rf_|5g|sdr|pmic|vcore|buck|wifi|wlan|conn/) return 0
    return t ~ /cpu|soc|mcu|cluster|tsens|cpuss|core|tzts|^ap/
}
