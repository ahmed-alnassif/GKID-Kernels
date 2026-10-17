#!/usr/bin/env python3
"""Offline tests for the Cogan Thermal Monitor module against a fake /sys and /proc.

The module runs on Android with mksh and one-true-awk; these tests use them when installed
(mksh, original-awk) and otherwise the runner's POSIX sh and awk. THERMAL_SH / THERMAL_AWK pick others.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules/thermal-monitor"
SHELL = os.environ.get("THERMAL_SH") or shutil.which("mksh") or shutil.which("dash") or "/bin/sh"
AWK = os.environ.get("THERMAL_AWK") or shutil.which("original-awk") or shutil.which("awk")

ZONES = {
    "soc_max": "55000", "cpu-big-core0": "52300", "gpu1": "48000", "battery": "36000", "shell_back": "39000",
    "md_pa": "41000", "apu": "40000", "board_ntc": "38000", "unused_sensor": "0", "broken": "-274000",
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def proc_stat(pid, comm, ppid, utime, stime):
    return f"{pid} ({comm}) S {ppid} {pid} 0 0 -1 4194560 100 0 0 0 {utime} {stime} 0 0 20 0 1 0 100 0 0\n"


class FakePhone:
    def __init__(self, base):
        self.base = base
        self.sys = base / "sys"
        self.proc = base / "proc"
        self.data = base / "data"
        self.out = base / "sdcard/Download/CoganThermal"
        self.bin = base / "bin"
        self.mod = base / "module"
        shutil.copytree(MODULE, self.mod)
        for index, (kind, temp) in enumerate(ZONES.items()):
            write(self.sys / f"class/thermal/thermal_zone{index}/type", kind + "\n")
            write(self.sys / f"class/thermal/thermal_zone{index}/temp", temp + "\n")
        battery = self.sys / "class/power_supply/battery"
        write(battery / "status", "Charging\n")
        write(battery / "current_now", "-2100000\n")
        write(battery / "temp", "361\n")
        write(self.sys / "kernel/ged/hal/gpu_utilization", "65 0 0\n")
        write(self.sys / "class/backlight/panel0-backlight/brightness", "1200\n")
        for policy, khz in (("0", "1800000"), ("4", "2850000"), ("7", "3250000")):
            write(self.sys / f"devices/system/cpu/cpufreq/policy{policy}/scaling_cur_freq", khz + "\n")
        self.set_net(0, 0)
        self.set_cpu(0)
        self.bin.mkdir()
        tools = {
            "dumpsys": "case \"$2\" in displays) echo '  mCurrentFocus=Window{1a2b u0 com.mobile.legends/com.moba.Unity}' ;; esac",
            "uname": "echo 6.1.177-Cogan-r3",
            "getprop": "case \"$1\" in sys.boot_completed) echo 1 ;; ro.product.model) echo TestPhone ;; "
                       "ro.build.version.release) echo 15 ;; esac",
            "am": "exit 0",
            "cmd": f"echo \"$*\" >> {base}/notifications",
        }
        for name, body in tools.items():
            write(self.bin / name, "#!/bin/sh\n" + body + "\n")
            (self.bin / name).chmod(0o755)
        os.symlink(SHELL, self.bin / "sh")
        os.symlink(AWK, self.bin / "awk")
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", TZ="WIB-7",
                        CT_DATA=str(self.data), CT_SYS=str(self.sys), CT_PROC=str(self.proc), CT_OUT=str(self.out))

    def set_net(self, wifi, cell):
        for name, total in (("wlan0", wifi), ("ccmni0", cell)):
            write(self.sys / f"class/net/{name}/statistics/rx_bytes", f"{total}\n")
            write(self.sys / f"class/net/{name}/statistics/tx_bytes", "0\n")

    def set_cpu(self, step):
        # 8 cores; each step adds 1000 ticks of which 400 busy. The game uses 250, a kworker 80.
        busy, idle = 1000 + 400 * step, 8000 + 600 * step
        write(self.proc / "stat", f"cpu  {busy} 0 0 {idle} 0 0 0 0 0 0\ncpu0 1 0 0 1 0 0 0 0 0 0\n")
        procs = ((1, "init", 0, 10, 10, "/system/bin/init"), (2, "kthreadd", 0, 0, 0, ""),
                 (4321, "kworker/u16:2", 2, 50 + 80 * step, 0, ""),
                 (5000, "UnityMain", 600, 100 + 200 * step, 50 + 50 * step, "com.mobile.legends"),
                 (6000, "Binder:900_1", 600, 20 + 30 * step, 0, "com.google.android.gms:persistent"))
        for pid, comm, ppid, utime, stime, cmdline in procs:
            write(self.proc / f"{pid}/stat", proc_stat(pid, comm, ppid, utime, stime))
            write(self.proc / f"{pid}/cmdline", cmdline + ("\0" if cmdline else ""))

    def run(self, script, *args, check=True):
        result = subprocess.run([str(self.bin / "sh"), str(self.mod / script), *args], env=self.env,
                                capture_output=True, text=True, timeout=60)
        if check and result.returncode:
            raise AssertionError(f"{script} {args}: {result.returncode}\n{result.stdout}\n{result.stderr}")
        return result.stdout

    def report(self, *args):
        return self.run("report.sh", *args)


def sample(ts, app, zones, charging=0, current=300, cpu=150, kernel=20, gpu=10, top="-", net="wifi:5,cell:0"):
    zone_text = ",".join(f"{name}={value}" for name, value in zones.items())
    return "\t".join(map(str, (ts, app, 0 if app == "screen_off" else 1, charging, current, 350, cpu, kernel, gpu,
                               top, net, "p0:1800", zone_text))) + "\n"


class SamplerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.phone = FakePhone(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def lines(self):
        files = sorted((self.phone.data / "data").glob("*.tsv"))
        self.assertEqual(len(files), 1)
        return [line.split("\t") for line in files[0].read_text().splitlines()]

    def test_sample_records_every_sensor_and_what_the_phone_does(self):
        self.phone.run("sampler.sh", "--once")
        self.phone.set_cpu(1)
        self.phone.set_net(20 * 1024 * 300, 0)
        net_prev = self.phone.data / "run/net.prev"
        net_prev.write_text(f"{int(time.time()) - 20} 0 0\n")
        self.phone.run("sampler.sh", "--once")
        first, second = self.lines()
        self.assertEqual(len(second), 13)
        ts, app, screen, charging, current, battery, cpu, kernel, gpu, top, net, freqs, zones = second
        self.assertEqual(first[6:8], ["-1", "-1"])           # no previous CPU reading yet
        self.assertEqual((app, screen, charging, current, battery, gpu), ("com.mobile.legends", "1", "1", "2100", "361", "65"))
        self.assertEqual(cpu, "400")                          # 400 of 1000 ticks busy = 40.0 %
        self.assertEqual(kernel, "80")                        # kworker (child of kthreadd) = 8.0 %
        self.assertEqual(top.split(";")[0], "com.mobile.legends:250")
        self.assertIn("com.google.android.gms:30", top)       # ":persistent" is dropped from the name
        self.assertEqual(net, "wifi:300,cell:0")
        self.assertEqual(freqs, "p0:1800,p4:2850,p7:3250")
        self.assertIn("soc_max=550", zones)
        self.assertIn("battery=360", zones)
        self.assertNotIn("unused_sensor", zones)
        self.assertNotIn("broken", zones)

    def test_heat_notification_only_when_enabled_and_hot(self):
        self.phone.run("sampler.sh", "--once")
        self.assertFalse((self.phone.base / "notifications").exists())
        self.assertEqual(json.loads(self.phone.report("set", "NOTIFY", "1", "NOTIFY_TEMP", "50")), {"ok": 1})
        self.phone.run("sampler.sh", "--once")
        notes = (self.phone.base / "notifications").read_text()
        self.assertIn("Prosesor 55 °C", notes)
        self.assertIn("Mobile Legends", notes)
        self.phone.run("sampler.sh", "--once")               # at most once every 10 minutes
        self.assertEqual(len((self.phone.base / "notifications").read_text().splitlines()), 1)

    def test_start_and_stop(self):
        self.phone.report("set", "INTERVAL", "10")
        status = json.loads(self.phone.report("start"))
        try:
            self.assertEqual(status["running"], 1)
            self.assertGreater(status["pid"], 0)
            self.assertEqual(json.loads(self.phone.report("start"))["pid"], status["pid"])   # no second copy
            deadline = time.time() + 10
            while time.time() < deadline and not list((self.phone.data / "data").glob("*.tsv")):
                time.sleep(0.2)
            self.assertTrue(list((self.phone.data / "data").glob("*.tsv")))
            self.assertIn("6.1.177-Cogan-r3", (self.phone.data / "kernels.tsv").read_text())
        finally:
            stopped = json.loads(self.phone.report("stop"))
        self.assertEqual(stopped["running"], 0)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.phone = FakePhone(Path(self.tmp.name))
        now = int(time.time())
        start = now - 140 * 20
        (self.phone.data / "data").mkdir(parents=True)
        write(self.phone.data / "kernels.tsv", f"{start - 100}\t6.1.138-android14-11\n{start + 70 * 20}\t6.1.177-Cogan-r3\n")
        lines = []
        for i in range(140):
            ts = start + i * 20
            if i < 60:     # Mobile Legends: GPU heavy and hot
                lines.append(sample(ts, "com.mobile.legends", {"soc_max": 470 + i % 30, "gpu1": 460, "battery": 370},
                                    cpu=280, gpu=70, top="com.mobile.legends:250"))
            elif i < 90:   # Instagram while Play services work in the background
                lines.append(sample(ts, "com.instagram.android", {"soc_max": 430, "battery": 360},
                                    cpu=200, top="com.google.android.gms:150;com.instagram.android:40"))
            elif i < 120:  # screen off, cool
                lines.append(sample(ts, "screen_off", {"soc_max": 350, "battery": 330}, cpu=30))
            else:          # fast charging on the home screen (the newest 20 samples)
                lines.append(sample(ts, "com.miui.home", {"soc_max": 440, "battery": 400}, charging=1, current=2500))
        # Older samples and a sample from the future are ignored.
        lines.insert(0, sample(start - 9 * 86400, "com.mobile.legends", {"soc_max": 990}))
        lines.insert(1, sample(now + 3600, "com.mobile.legends", {"soc_max": 990}))
        day = time.strftime("%Y-%m-%d", time.gmtime(now + 7 * 3600))
        write(self.phone.data / "data" / f"{day}.tsv", "".join(lines))
        self.now = now

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_names_the_causes(self):
        summary = json.loads(self.phone.report("summary", "86400"))
        self.assertEqual(summary["samples"], 140)
        self.assertEqual(summary["peak"]["t"], 499)
        self.assertEqual(summary["peak"]["app"], "Mobile Legends")
        causes = {cause["name"]: cause["pct"] for cause in summary["causes"]}
        self.assertEqual(summary["causes"][0]["name"], "Grafis berat: Mobile Legends")
        self.assertIn("Latar belakang: com.google.android.gms", causes)
        self.assertIn("Cas cepat", causes)
        self.assertEqual(sum(causes.values()), 100)
        apps = {app["pkg"]: app for app in summary["apps"]}
        self.assertEqual(apps["com.mobile.legends"]["name"], "Mobile Legends")
        self.assertEqual(apps["screen_off"]["name"], "Layar mati")
        kernels = {kernel["name"]: kernel["pct"] for kernel in summary["kernels"]}
        self.assertEqual(kernels, {"6.1.138-android14-11": 50, "6.1.177-Cogan-r3": 50})
        self.assertLessEqual(len(summary["series"]), 120)
        self.assertIn("Kesimpulan: paling sering panas karena Grafis berat: Mobile Legends", summary["text"])
        groups = {group["name"]: group for group in summary["groups"]}
        self.assertLessEqual({"Prosesor", "GPU", "Baterai"}, set(groups))
        self.assertEqual((groups["GPU"]["avg"], groups["GPU"]["peak"]), (460, 460))   # only samples with a GPU zone

    def test_short_range_only_sees_recent_samples(self):
        summary = json.loads(self.phone.report("summary", "300"))
        self.assertLessEqual(summary["samples"], 16)
        self.assertEqual([cause["name"] for cause in summary["causes"]], ["Cas cepat"])

    def test_text_csv_and_now(self):
        text = self.phone.report("text", "86400")
        self.assertIn("ringkasan 1 hari", text)
        self.assertIn("Suhu tertinggi: 49.9 °C (Prosesor)", text)
        self.assertIn("Per kernel", text)
        rows = self.phone.report("csv", "86400").splitlines()
        self.assertEqual(len(rows), 141)
        self.assertTrue(rows[0].startswith("waktu,aplikasi,layar,cas"))
        self.assertIn(",Mobile Legends,nyala,tidak,", rows[1])
        table = list(csv.reader(rows))
        self.assertEqual({len(row) for row in table}, {len(table[0])})
        first = dict(zip(table[0], table[1]))
        self.assertEqual((first["proses_teratas"], first["wifi_kBps"], first["seluler_kBps"]), ("Mobile Legends 25.0%", "5", "0"))
        now = json.loads(self.phone.report("now"))
        self.assertEqual(now["main"], 550)                     # read from the sensors just now
        self.assertEqual((now["app"], now["charging"], now["release"]), ("Layar utama (launcher)", 1, "6.1.177-Cogan-r3"))
        self.assertEqual(now["running"], 0)
        self.assertIn({"name": "soc_max", "group": "Prosesor", "t": 550}, now["zones"])

    def test_save_writes_txt_and_csv(self):
        saved = json.loads(self.phone.report("save", "3600"))
        self.assertEqual(saved["ok"], 1)
        self.assertEqual(saved["dir"], str(self.phone.out))
        self.assertTrue(saved["txt"].endswith("_1jam.txt"))
        txt = Path(saved["txt"]).read_text()
        self.assertIn("Cogan Thermal Monitor — ringkasan 1 jam", txt)
        self.assertIn("Detail per sampel:", txt)
        self.assertIn("teratas: com.google.android.gms 15.0%; Instagram 4.0%", txt)
        self.assertIn("kernel 6.1.177-Cogan-r3", txt)
        csv_rows = Path(saved["csv"]).read_text().splitlines()
        self.assertEqual(len(csv_rows) - 1, saved["samples"])
        self.assertGreater(saved["samples"], 100)
        self.assertTrue(json.loads(self.phone.report("save", "90"))["txt"].endswith("_1menit.txt"))

    def test_empty_history(self):
        self.assertEqual(json.loads(self.phone.report("clear")), {"ok": 1})
        summary = json.loads(self.phone.report("summary", "3600"))
        self.assertEqual(summary["samples"], 0)
        self.assertIn("Belum ada data", summary["text"])
        self.assertEqual(json.loads(self.phone.report("now"))["age"], -1)
        self.assertEqual(json.loads(self.phone.report("status"))["days"], 0)

    def test_settings_are_validated(self):
        self.assertEqual(json.loads(self.phone.report("set", "HOT_TEMP", "40", "INTERVAL", "30")), {"ok": 1})
        status = json.loads(self.phone.report("status"))
        self.assertEqual((status["hot"], status["interval"], status["retention"], status["notify"]), (40, 30, 7, 0))
        for args in (("INTERVAL", "5"), ("HOT_TEMP", "1;reboot"), ("FOO", "1"), ("NOTIFY", "2")):
            result = json.loads(self.phone.report("set", *args))
            self.assertEqual(result["ok"], 0, args)
        self.assertEqual(json.loads(self.phone.report("status"))["interval"], 30)
        config = (self.phone.data / "config").read_text()
        self.assertNotIn("reboot", config)
        self.assertNotIn("FOO", config)


class PackageTests(unittest.TestCase):
    def test_module_files(self):
        prop = dict(line.split("=", 1) for line in (MODULE / "module.prop").read_text().splitlines() if "=" in line)
        self.assertEqual(prop["id"], "cogan_thermal")
        self.assertRegex(prop["versionCode"], r"^\d+$")
        for name in ("service.sh", "sampler.sh", "report.sh", "action.sh", "uninstall.sh", "customize.sh",
                     "common.sh", "cpu.awk", "thermal.awk", "report.awk", "webroot/index.html",
                     "META-INF/com/google/android/update-binary", "META-INF/com/google/android/updater-script"):
            self.assertTrue((MODULE / name).is_file(), name)
        html = (MODULE / "webroot/index.html").read_text()
        self.assertIn("/data/adb/modules/cogan_thermal/report.sh", html)

    def test_zip(self):
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/package_module.py"), str(MODULE), out],
                                    capture_output=True, text=True, check=True)
            target = Path(result.stdout.strip())
            self.assertEqual(target.name, "Cogan-Thermal-Monitor-v1.0.zip")
            with zipfile.ZipFile(target) as archive:
                modes = {info.filename: (info.external_attr >> 16) & 0o777 for info in archive.infolist()}
        self.assertEqual(modes["module.prop"], 0o644)
        self.assertEqual(modes["service.sh"], 0o755)
        self.assertEqual(modes["META-INF/com/google/android/update-binary"], 0o755)
        self.assertIn("webroot/index.html", modes)
        self.assertNotIn("README.md", modes)


if __name__ == "__main__":
    unittest.main()
