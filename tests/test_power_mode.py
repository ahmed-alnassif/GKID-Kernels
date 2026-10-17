#!/usr/bin/env python3
"""Offline tests for the Cogan Power Mode module against a fake /sys.

Like tests/test_thermal_monitor.py it prefers mksh and one-true-awk (Android's shell and awk) when
installed; THERMAL_SH / THERMAL_AWK pick others. A small thread plays the charger: while the switch
under test is off the battery reports "Not charging". A fake `sleep` does the same at once, which
keeps the tests fast where `sleep` is not a shell builtin.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules/power-mode"
SHELL = os.environ.get("THERMAL_SH") or shutil.which("mksh") or shutil.which("dash") or "/bin/sh"
AWK = os.environ.get("THERMAL_AWK") or shutil.which("original-awk") or shutil.which("awk")
POLICIES = {   # name: (min, max, available steps)
    "policy0": (500000, 2000000, "500000 1000000 1500000 2000000"),
    "policy4": (1000000, 3000000, "1000000 1500000 2000000 2400000 2700000 3000000"),
    "policy7": (1200000, 3250000, "1200000 2000000 2500000 2900000 3250000"),
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class FakePhone:
    def __init__(self, base, charger_switch=None):
        self.base = base
        self.sys = base / "sys"
        self.data = base / "power"
        self.monitor = base / "thermal"
        self.cpuctl = base / "cpuctl"
        self.bin = base / "bin"
        self.mod = base / "module"
        shutil.copytree(MODULE, self.mod)
        self.bin.mkdir()
        self.set_temp(40.0)
        battery = self.sys / "class/power_supply/battery"
        self.battery = battery
        self.set_battery(50, "Charging", 30.0, -1000000)
        write(battery / "input_suspend", "0\n")
        write(battery / "battery_charging_enabled", "1\n")
        for name, (low, high, steps) in POLICIES.items():
            policy = self.sys / f"devices/system/cpu/cpufreq/{name}"
            write(policy / "cpuinfo_min_freq", f"{low}\n")
            write(policy / "cpuinfo_max_freq", f"{high}\n")
            write(policy / "scaling_max_freq", f"{high}\n")
            write(policy / "scaling_cur_freq", f"{low}\n")
            write(policy / "scaling_available_frequencies", steps + "\n")
        write(self.cpuctl / "top-app/cpu.uclamp.min", "0.00\n")
        (self.monitor / "run").mkdir(parents=True)
        # The charger: while the switch under test is off, the battery stops charging.
        tools = {"getprop": "echo 1"}
        self.charger = None
        if charger_switch:
            node, off = charger_switch
            status = battery / "status"
            tools["sleep"] = (f"if [ \"$(cat {battery / node})\" = {off} ]; then s='Not charging'; else s=Charging; fi\n"
                              f"echo \"$s\" > {status}.sleep && mv {status}.sleep {status}\nexec /bin/sleep 0")
            self.charger = threading.Event()

            def plugged_in():
                while not self.charger.is_set():
                    want = "Not charging" if (battery / node).read_text().strip() == off else "Charging"
                    if status.read_text().strip() not in (want, ""):
                        (battery / "status.thread").write_text(want + "\n")
                        os.replace(battery / "status.thread", status)
                    time.sleep(0.02)
            threading.Thread(target=plugged_in, daemon=True).start()
        for name, body in tools.items():
            write(self.bin / name, "#!/bin/sh\n" + body + "\n")
            (self.bin / name).chmod(0o755)
        os.symlink(SHELL, self.bin / "sh")
        os.symlink(AWK, self.bin / "awk")
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", CP_DATA=str(self.data), CP_SYS=str(self.sys),
                        CP_PROC=str(base / "proc"), CP_CPUCTL=str(self.cpuctl), CT_DATA=str(self.monitor),
                        CT_MOD=str(base / "modules/cogan_thermal"))

    def set_temp(self, celsius):
        for index, (kind, value) in enumerate((("soc_max", celsius), ("gpu1", celsius - 3), ("battery", 30.0))):
            write(self.sys / f"class/thermal/thermal_zone{index}/type", kind + "\n")
            write(self.sys / f"class/thermal/thermal_zone{index}/temp", f"{int(value * 1000)}\n")

    def unplug(self):
        if self.charger:
            self.charger.set()
            time.sleep(0.1)

    def set_battery(self, level, status, celsius, current_ua=-1000000):
        write(self.battery / "capacity", f"{level}\n")
        (self.battery / "status.new").write_text(status + "\n")
        os.replace(self.battery / "status.new", self.battery / "status")
        write(self.battery / "temp", f"{int(celsius * 10)}\n")
        write(self.battery / "current_now", f"{current_ua}\n")

    def monitor_report(self, cause, app="Mobile Legends", age=0):
        write(self.monitor / "run/latest", f"{int(time.time()) - age}\t450\t300\t1\t{app}\t{cause}\n")

    def caps(self):
        return {name: int((self.sys / f"devices/system/cpu/cpufreq/{name}/scaling_max_freq").read_text())
                for name in POLICIES}

    def node(self, name):
        return (self.battery / name).read_text().strip()

    def run(self, script, *args):
        result = subprocess.run([str(self.bin / "sh"), str(self.mod / script), *args], env=self.env,
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(f"{script} {args}: {result.returncode}\n{result.stdout}\n{result.stderr}")
        return result.stdout

    def step(self):
        self.run("controller.sh", "--once")
        return json.loads((self.data / "run/state.json").read_text())

    def report(self, *args):
        return json.loads(self.run("report.sh", *args))

    def events(self):
        return [event["text"] for event in self.report("events", "50")]


class PowerModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.phone = FakePhone(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def save_switch(self):
        write(self.phone.data / "switch", "class/power_supply/battery/input_suspend|0|1\n")

    def test_balanced_steps_the_cpu_down_and_back_up(self):
        self.phone.set_temp(45.0)
        state = self.phone.step()
        self.assertEqual((state["mode"], state["limit"], state["level"], state["big"]), ("seimbang", 42, 1, 90))
        self.assertEqual(self.phone.caps(), {"policy0": 2000000, "policy4": 2700000, "policy7": 2900000})
        self.assertEqual(self.phone.step()["big"], 80)                    # still hot: one more step
        self.assertEqual(self.phone.caps()["policy4"], 2400000)
        self.phone.set_temp(44.0)                                         # cooling already: hold
        self.assertEqual(self.phone.step()["level"], 2)
        self.phone.set_temp(41.0)                                         # under the limit, not 2 °C under
        self.assertEqual(self.phone.step()["level"], 2)
        self.phone.set_temp(39.0)
        self.assertEqual(self.phone.step()["level"], 2)                   # first cool check
        self.assertEqual(self.phone.step()["level"], 1)                   # second: one step back up
        self.assertEqual(self.phone.caps()["policy4"], 2700000)
        events = self.phone.events()
        self.assertIn("Suhu turun ke 39.0 °C: CPU 90%", events[0])
        self.assertTrue(any("Suhu 45.0 °C ≥ 42 °C: CPU dibatasi 90%" in event for event in events))

    def test_saver_and_game(self):
        self.assertEqual(self.phone.report("mode", "hemat"), {"ok": 1})
        self.phone.set_temp(35.0)
        state = self.phone.step()
        self.assertEqual((state["limit"], state["big"], state["little"]), (39, 60, 80))
        self.assertEqual(self.phone.caps(), {"policy0": 1500000, "policy4": 1500000, "policy7": 1200000})
        self.phone.set_temp(40.0)                                         # Hemat steps down from its own cap
        self.assertEqual(self.phone.step()["big"], 50)
        self.phone.report("mode", "game")
        self.phone.set_temp(45.0)
        state = self.phone.step()
        self.assertEqual((state["limit"], state["big"], state["boost"]), (48, 100, 1))
        self.assertEqual(self.phone.caps(), {"policy0": 2000000, "policy4": 3000000, "policy7": 3250000})
        self.assertEqual((self.phone.cpuctl / "top-app/cpu.uclamp.min").read_text().strip(), "20")
        self.phone.set_temp(49.0)                                         # Game's emergency brake
        self.assertEqual(self.phone.step()["big"], 90)
        self.phone.report("mode", "seimbang")
        self.assertEqual(self.phone.step()["boost"], 0)
        self.assertEqual((self.phone.cpuctl / "top-app/cpu.uclamp.min").read_text().strip(), "0.00")
        self.assertEqual((self.phone.monitor / "modes.tsv").read_text().split()[1::2], ["hemat", "game", "seimbang"])
        self.assertIn("Mode: Seimbang", self.phone.events()[:2])

    def test_charge_limit(self):
        self.save_switch()
        self.phone.set_battery(81, "Charging", 33.0)
        self.assertEqual(self.phone.step()["charge_off"], "batas")
        self.assertEqual(self.phone.node("input_suspend"), "1")
        self.assertIn("Baterai 81%: cas dihentikan, lanjut di 75%", self.phone.events()[0])
        self.phone.set_battery(76, "Discharging", 33.0)
        self.assertEqual(self.phone.step()["charge_off"], "batas")
        self.phone.set_battery(76, "Charging", 33.0)                      # turned back on by a replug
        write(self.phone.battery / "input_suspend", "0\n")
        self.phone.step()
        self.assertEqual(self.phone.node("input_suspend"), "1")
        self.phone.set_battery(75, "Discharging", 33.0)
        self.assertEqual(self.phone.step()["charge_off"], "")
        self.assertEqual(self.phone.node("input_suspend"), "0")
        self.assertIn("Cas dilanjutkan (baterai 75%", self.phone.events()[0])

    def test_battery_heat_and_monitor_cause(self):
        self.save_switch()
        self.phone.set_battery(50, "Charging", 42.5)
        self.assertEqual(self.phone.step()["charge_off"], "baterai")
        self.phone.set_battery(50, "Discharging", 39.5)
        self.assertEqual(self.phone.step()["charge_off"], "baterai")     # resumes only at 39 °C
        self.phone.set_battery(50, "Discharging", 39.0)
        self.assertEqual(self.phone.step()["charge_off"], "")
        # Cogan Thermal Monitor says charging heats the phone: Seimbang pauses charging.
        self.phone.set_battery(50, "Charging", 35.0)
        self.phone.set_temp(43.0)
        self.phone.monitor_report("Cas cepat")
        state = self.phone.step()
        self.assertEqual((state["charge_off"], state["source"], state["cause"]), ("panas", "monitor", "Cas cepat"))
        self.assertEqual(state["level"], 0)                               # pausing the charger comes first
        self.assertIn("karena cas: cas dijeda sampai 39 °C", self.phone.events()[0])
        self.assertEqual(self.phone.step()["level"], 0)                   # not rising: CPU stays free
        self.phone.set_temp(43.5)
        self.assertEqual(self.phone.step()["level"], 1)                   # still rising: CPU steps in
        self.phone.set_temp(38.5)
        self.assertEqual(self.phone.step()["charge_off"], "")
        # Another cause (a game) is handled by the CPU, not by stopping the charger.
        self.phone.set_temp(43.0)
        self.phone.monitor_report("Grafis berat: Mobile Legends")
        state = self.phone.step()
        self.assertEqual((state["charge_off"], state["level"] > 0), ("", True))
        # A stale report is ignored.
        self.phone.monitor_report("Cas cepat", age=600)
        self.assertEqual(self.phone.step()["source"], "sensor")

    def test_failsafe_and_switch_off(self):
        self.save_switch()
        self.phone.set_battery(90, "Charging", 44.0)
        self.assertEqual(self.phone.step()["charge_off"], "batas baterai")
        self.phone.set_battery(12, "Discharging", 44.0)                   # nearly empty: always charge
        self.assertEqual(self.phone.step()["charge_off"], "")
        self.phone.set_battery(90, "Charging", 30.0)
        self.assertEqual(self.phone.report("set", "CHARGE_CTRL", "0"), {"ok": 1})
        self.assertEqual(self.phone.step()["charge_off"], "")
        self.assertEqual(self.phone.node("input_suspend"), "0")

    def test_settings_are_validated(self):
        self.assertEqual(self.phone.report("set", "CHARGE_STOP", "85", "CHARGE_RESUME", "80", "TARGET_TEMP", "40"), {"ok": 1})
        config = self.phone.report("status")["config"]
        self.assertEqual((config["CHARGE_STOP"], config["CHARGE_RESUME"], config["TARGET_TEMP"], config["mode"]), (85, 80, 40, "seimbang"))
        for args in (("CHARGE_RESUME", "90"), ("MODE", "turbo"), ("TARGET_TEMP", "99"), ("INTERVAL", "1;reboot"), ("FOO", "1")):
            self.assertEqual(self.phone.report("set", *args)["ok"], 0, args)
        self.assertEqual(self.phone.report("status")["config"]["CHARGE_RESUME"], 80)
        text = (self.phone.data / "config").read_text()
        self.assertNotIn("reboot", text)
        self.assertNotIn("turbo", text)

    def test_status(self):
        self.phone.monitor_report("Aplikasi berat: Instagram", app="Instagram")
        status = self.phone.report("status")
        self.assertEqual((status["running"], status["main"], status["switch"], status["state"]), (0, 400, "", None))
        self.assertEqual(status["battery"], {"level": 50, "status": "charging", "temp": 300, "current": 1000})
        self.assertEqual(status["monitor"], {"installed": 0, "fresh": 1, "cause": "Aplikasi berat: Instagram", "app": "Instagram"})
        self.assertEqual([p["name"] for p in status["policies"]], ["policy0", "policy4", "policy7"])
        write(self.phone.base / "modules/cogan_thermal/module.prop", "id=cogan_thermal\n")
        self.assertEqual(self.phone.report("status")["monitor"]["installed"], 1)

    def test_start_and_stop_put_everything_back(self):
        self.save_switch()
        self.phone.report("set", "INTERVAL", "5")
        self.phone.set_temp(46.0)
        self.phone.set_battery(85, "Charging", 33.0)
        status = self.phone.report("start")
        try:
            self.assertEqual(status["running"], 1)
            deadline = time.time() + 10
            while time.time() < deadline and self.phone.node("input_suspend") != "1":
                time.sleep(0.1)
            self.assertEqual(self.phone.node("input_suspend"), "1")
            self.assertLess(self.phone.caps()["policy4"], 3000000)
            self.assertEqual(self.phone.report("start")["running"], 1)
        finally:
            started = time.time()
            stopped = self.phone.report("stop")
        self.assertLess(time.time() - started, 4)                         # the controller wakes up for TERM
        self.assertEqual(stopped["running"], 0)
        self.assertEqual(self.phone.caps(), {"policy0": 2000000, "policy4": 3000000, "policy7": 3250000})
        self.assertEqual(self.phone.node("input_suspend"), "0")
        self.assertEqual((self.phone.monitor / "modes.tsv").read_text().split()[-1], "none")
        self.assertIn("Cogan Power Mode berhenti", self.phone.events()[0])


class SwitchDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # input_suspend exists but does nothing here; battery_charging_enabled really stops charging.
        self.phone = FakePhone(Path(self.tmp.name), charger_switch=("battery_charging_enabled", "0"))

    def tearDown(self):
        self.phone.unplug()
        self.tmp.cleanup()

    def test_detect_from_webui(self):
        result = self.phone.report("detect")
        self.assertEqual((result["ok"], result["switch"]), (1, "class/power_supply/battery/battery_charging_enabled"))
        self.assertEqual(result["tried"], [
            {"node": "class/power_supply/battery/input_suspend", "result": "tidak_berpengaruh"},
            {"node": "class/power_supply/battery/battery_charging_enabled", "result": "ok"},
        ])
        self.assertEqual((self.phone.node("input_suspend"), self.phone.node("battery_charging_enabled")), ("0", "1"))

    def test_detected_on_first_need(self):
        self.phone.set_battery(85, "Charging", 33.0)
        state = self.phone.step()
        self.assertEqual(state["charge_off"], "batas")
        self.assertEqual(self.phone.node("battery_charging_enabled"), "0")
        self.assertEqual(self.phone.report("status")["switch"], "class/power_supply/battery/battery_charging_enabled")
        self.assertTrue(any("Saklar cas ditemukan" in event for event in self.phone.events()))

    def test_not_charging(self):
        self.phone.unplug()
        self.phone.set_battery(50, "Discharging", 30.0)
        result = self.phone.report("detect")
        self.assertEqual(result["ok"], 0)
        self.assertIn("Colokkan charger", result["error"])


class PackageTests(unittest.TestCase):
    def test_zip(self):
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/package_module.py"), str(MODULE), out],
                                    capture_output=True, text=True, check=True)
            with zipfile.ZipFile(result.stdout.strip()) as archive:
                modes = {info.filename: (info.external_attr >> 16) & 0o777 for info in archive.infolist()}
        self.assertEqual(modes["controller.sh"], 0o755)
        self.assertEqual(modes["power.awk"], 0o644)
        self.assertIn("webroot/index.html", modes)
        html = (MODULE / "webroot/index.html").read_text()
        self.assertIn("/data/adb/modules/cogan_power/report.sh", html)


if __name__ == "__main__":
    unittest.main()
