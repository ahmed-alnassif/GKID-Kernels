# Cogan Thermal Monitor: helpers shared by report.awk and the sampler's alert check.
# Plain POSIX awk (Android's one-true-awk): no gawk extensions, no strftime.

# Sensor group of a thermal zone type. Order matters: specific names before the generic CPU match.
function group(type,   t) {
    t = tolower(type)
    if (t ~ /gpu|mali/) return "gpu"
    if (t ~ /batt|^bat_|_bat|bms/) return "bat"
    if (t ~ /charg|chg|usb|wlc|vbus/) return "chg"
    if (t ~ /skin|shell|back|board|ap_ntc|case|frame|xo_therm|quiet|ltepa_ntc/) return "skin"
    if (t ~ /apu|npu|^ai|vpu|mdla/) return "apu"
    if (t ~ /modem|^md|mdpa|^pa_|_pa_|^pa$|nrpa|^nr|lte|rfic|^rf_|5g|sdr/) return "modem"
    if (t ~ /pmic|vcore|buck/) return "pmic"
    if (t ~ /wifi|wlan|conn/) return "wifi"
    if (t ~ /cpu|soc|mcu|cluster|tsens|cpuss|core|tzts|^ap/) return "cpu"
    return "other"
}

function group_name(g) {
    return g == "cpu" ? "Prosesor" : g == "gpu" ? "GPU" : g == "bat" ? "Baterai" : g == "skin" ? "Badan HP" : \
           g == "modem" ? "Modem" : g == "chg" ? "Charger" : g == "pmic" ? "PMIC" : g == "apu" ? "AI (APU)" : \
           g == "wifi" ? "Wi-Fi" : "Lainnya"
}

# Friendly names for common packages; anything else keeps its package name.
function label(pkg) {
    if (pkg == "" || pkg == "-") return "Tidak diketahui"
    if (pkg == "screen_off") return "Layar mati"
    if (pkg == "com.instagram.android") return "Instagram"
    if (pkg == "com.mobile.legends" || pkg ~ /^com\.mobile\.legends/) return "Mobile Legends"
    if (pkg == "com.whatsapp" || pkg == "com.whatsapp.w4b") return "WhatsApp"
    if (pkg == "com.google.android.youtube") return "YouTube"
    if (pkg == "com.zhiliaoapp.musically" || pkg == "com.ss.android.ugc.trill") return "TikTok"
    if (pkg == "com.facebook.katana") return "Facebook"
    if (pkg == "com.facebook.orca") return "Messenger"
    if (pkg == "org.telegram.messenger" || pkg == "org.telegram.messenger.web") return "Telegram"
    if (pkg == "com.android.chrome") return "Chrome"
    if (pkg == "com.tencent.ig") return "PUBG Mobile"
    if (pkg == "com.dts.freefireth" || pkg == "com.dts.freefiremax") return "Free Fire"
    if (pkg == "com.miHoYo.GenshinImpact") return "Genshin Impact"
    if (pkg == "com.HoYoverse.hkrpgoversea") return "Honkai: Star Rail"
    if (pkg == "com.levelinfinite.sgameGlobal") return "Honor of Kings"
    if (pkg == "com.roblox.client") return "Roblox"
    if (pkg == "com.spotify.music") return "Spotify"
    if (pkg == "com.netflix.mediaclient") return "Netflix"
    if (pkg == "com.shopee.id") return "Shopee"
    if (pkg == "com.tokopedia.tkpd") return "Tokopedia"
    if (pkg == "com.gojek.app") return "Gojek"
    if (pkg == "com.grabtaxi.passenger") return "Grab"
    if (pkg == "com.google.android.apps.maps") return "Google Maps"
    if (pkg == "com.android.camera" || pkg == "com.android.camera2") return "Kamera"
    if (pkg == "com.miui.home" || pkg == "com.mi.android.globallauncher") return "Layar utama (launcher)"
    if (pkg == "com.android.systemui") return "System UI"
    if (pkg == "system_server") return "Sistem Android"
    if (pkg == "surfaceflinger") return "SurfaceFlinger (tampilan)"
    if (pkg == "com.termux") return "Termux"
    return pkg
}

# Local wall clock from epoch seconds, using TZOFF (seconds east of UTC).
function days_to_date(z,   era, doe, yoe, y, doy, mp, d, m) {   # Howard Hinnant's civil_from_days
    z += 719468
    era = int((z >= 0 ? z : z - 146096) / 146097)
    doe = z - era * 146097
    yoe = int((doe - int(doe / 1460) + int(doe / 36524) - int(doe / 146096)) / 365)
    y = yoe + era * 400
    doy = doe - (365 * yoe + int(yoe / 4) - int(yoe / 100))
    mp = int((5 * doy + 2) / 153)
    d = doy - int((153 * mp + 2) / 5) + 1
    m = mp < 10 ? mp + 3 : mp - 9
    return sprintf("%04d-%02d-%02d", y + (m <= 2), m, d)
}
function local_date(ts) { return days_to_date(int((ts + TZOFF) / 86400)) }
function local_clock(ts,   s) { s = (ts + TZOFF) % 86400; if (s < 0) s += 86400; return sprintf("%02d:%02d", int(s / 3600), int((s % 3600) / 60)) }

function deg(tenths) { return sprintf("%.1f", tenths / 10) }
function jesc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); return s }

# Hottest CPU/GPU zone of a sample's zone list ("type=tenths,..."), or the hottest of all.
function main_temp(zones,   n, z, i, kv, g, best, any) {
    best = -9999; any = -9999
    n = split(zones, z, ",")
    for (i = 1; i <= n; i++) {
        if (split(z[i], kv, "=") != 2) continue
        kv[2] += 0
        if (kv[2] > any) any = kv[2]
        g = group(kv[1])
        if ((g == "cpu" || g == "gpu") && kv[2] > best) best = kv[2]
    }
    return best > -9999 ? best : any
}
