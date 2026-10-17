# Cogan Power Mode

[Bahasa Indonesia](README.md)

A KernelSU / KernelSU Next / BakaSU module (Magisk works too, without the WebUI) with three modes and automatic charge cut-off. It complements **[Cogan Thermal Monitor](../thermal-monitor/README.en.md)**: the monitor records temperatures and their causes; Power Mode uses that report to keep the phone cool. The interface is in Indonesian.

## Modes

| Mode | What it does |
|---|---|
| 🌿 **Hemat** (saver) | Big cores at most 60 % (configurable), temperature kept ≤ 39 °C (balanced target − 3) |
| ⚖️ **Seimbang** (balanced, default) | Processor kept ≤ 42 °C (configurable) |
| 🎮 **Game** | Full performance + a boost for the app on screen (uclamp); the emergency brake only acts at 48 °C |

How the temperature is kept (every 10 seconds):

- Too hot → the CPU top speed goes down 10 % per step, to 40 % at most.
- At least 2 °C under the limit → the speed comes back step by step.
- The little cores are always capped more lightly (+20 %), so the phone stays smooth.

## Working with Cogan Thermal Monitor

- The monitor writes a short report for every sample: temperature, app and **heat cause**.
- **Seimbang** uses that cause:
  - When **charging** heats the phone, charging is paused first until the temperature drops 3 °C, and the CPU is left alone.
  - The CPU is only capped as well if the temperature keeps rising.
  - Other causes (games, heavy apps, background work) are handled by capping the CPU.
- Power Mode tells the monitor which mode is active, so the monitor's summary gets a **⚡ per mode** section (average, peak and hot time for each mode).
- Without the monitor, Power Mode still works from its own sensor readings. It then guesses "charging" as the cause from a charging current of ≥ 1500 mA.

## Automatic charge cut-off

- **Stop** at 80 %, **resume** at 75 % (configurable; stop at 100 % = never).
- **Pause while the battery is hot**: ≥ 42 °C, resume once it is 3 °C cooler.
- **Seimbang**: also pauses when the monitor reports charging as the heat cause (can be turned off).
- **Safety**:
  - a battery at ≤ 15 % always charges;
  - stopping, disabling or removing the module, or booting the phone, always turns charging back on.
- **Charging switch**: found automatically the first time it is needed, or with 🔍 **Cari saklar cas** in the WebUI (charger plugged in). The module tries the switches common on Xiaomi/Qualcomm/MediaTek/Samsung/OnePlus/Motorola phones. A switch is only used if charging really stops and then starts again.

## WebUI and Action

- **WebUI**:
  - pick a mode;
  - see the temperature, the CPU limit per cluster, the heat cause, the battery and the charging state;
  - change every number;
  - find the charging switch;
  - an activity log ("CPU dibatasi 80 %", "cas dijeda", …).
- **Action**: switch to the next mode (Hemat → Seimbang → Game).
- **Stopping / disabling the module**: CPU, boost and charging go back to normal.

## Notes

- It only changes the CPU top speed (`scaling_max_freq`), the `top-app` boost (`cpu.uclamp.min`) and the charging switch, and puts them all back when it stops. Governors, the GPU and other settings are left alone.
- Don't combine it with another module that also controls the CPU or charging (e.g. ACC or performance modules): they would overwrite each other.

## For developers

- Build the ZIP: `python3 scripts/package_module.py modules/power-mode out/`
- Offline tests (fake sysfs): `python3 -m unittest tests/test_power_mode.py`
- Scripts:
  - `controller.sh`: the controller;
  - `report.sh`: used by the WebUI/Action;
  - `common.sh`: settings, sensors, CPU, charging switch;
  - `power.awk`: processor temperature, read the same way as the monitor.
