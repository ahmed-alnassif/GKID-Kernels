# Cogan Thermal Monitor

[Bahasa Indonesia](README.md)

A KernelSU / KernelSU Next / BakaSU module (Magisk works too, without the WebUI) that records **every temperature** on the phone together with **what caused it**, and makes summaries. It only reads sensors: it changes no settings and sends no data anywhere. The interface is in Indonesian.

## What it records

Every 20 seconds (configurable):

- every `thermal_zone` sensor (CPU, GPU, battery, skin, modem, charger, AI/APU, PMIC, Wi-Fi), grouped automatically;
- the app in the foreground, screen on/off;
- CPU use, kernel threads, the 5 busiest processes (background ones included), GPU load;
- charging state and current, Wi-Fi/cellular speed, CPU frequencies;
- the running kernel version (to compare, e.g. Cogan with the stock kernel).

History lives in `/data/adb/cogan_thermal`, 7 days at most (configurable).

## Heat causes

Every hot moment (default ≥ 42 °C) gets one cause, strongest first:

1. **Fast charging**: charging at ≥ 1500 mA.
2. **Heavy graphics: _app_**: GPU ≥ 60 % (games such as Mobile Legends).
3. **Background: _process_**: another process (not the foreground app) uses ≥ 10 % CPU.
4. **Kernel threads**: ≥ 10 % CPU.
5. **Heavy cellular data (modem)**: ≥ 1.5 MB/s.
6. **Screen off** (background work) or **charging** with the screen off.
7. **Heavy app: _app_**: CPU ≥ 25 % (Instagram, camera, …).
8. **Charging**, or **light use** (leftover heat / ambient temperature).

CPU percentages are of all cores together (8 cores: one full core ≈ 12.5 %).

## WebUI

Open the module in the manager → WebUI icon:

- **Sekarang (now)**: the hottest temperature, each part of the phone and every sensor (refreshed every 5 s).
- **Ringkasan (summary)**: 15 minutes to 7 days with a chart, the peak, heat causes, per app and per kernel. **📋 Salin** copies the summary as text.
- **💾 Simpan log (save log)**: pick a range (15 minutes to 7 days, or any number of minutes). A `.txt` (summary + every sample) and a `.csv` go to `Download/CoganThermal`.
- **⚙️ Setelan (settings)**: check interval, hot threshold, history length, heat notification (off by default; 45 °C), start/stop and clear history.

The manager's **Action** button shows the last hour.

## Working with Cogan Power Mode

- Every sample also writes a short `run/latest` report (temperature, app, cause). **[Cogan Power Mode](../power-mode/README.en.md)** uses it for its balanced mode, e.g. to pause charging when charging is what heats the phone.
- With Power Mode installed, the summary gets a **⚡ per mode** section (Hemat / Seimbang / Game / without Power Mode): average, peak and hot time for each mode.

## Install / remove

- Install the ZIP from the Modules screen, then reboot.
- Removing the module deletes `/data/adb/cogan_thermal`; logs in `Download/CoganThermal` stay.

## For developers

- Draft release: every module change on `dev` becomes a draft in Releases through the **Draft modul** workflow (tag `<folder>-vX.Y`); the owner publishes it.
- Build the ZIP: `python3 scripts/package_module.py modules/thermal-monitor out/`
- Offline tests (fake sysfs/proc): `python3 -m unittest tests/test_thermal_monitor.py`
- Scripts: `sampler.sh` (recorder), `report.sh` (reports for the WebUI/Action), `report.awk` + `thermal.awk` + `cpu.awk` (POSIX awk, matches Android's awk).
