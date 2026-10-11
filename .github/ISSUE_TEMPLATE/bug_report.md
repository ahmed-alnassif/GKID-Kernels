---
name: Kernel Bug Report
about: Report boot issues, crashes, or feature malfunctions
title: "[BUG]: "
labels: bug
assignees: ahmed-alnassif

---

**Describe the bug**
A clear and concise description of the issue (e.g., bootloop, WiFi not working, random reboot).

**Device & Environment**
- **Device:** [e.g., Poco X6 Pro (duchamp)]
- **ROM:** [e.g., HyperOS 3.0, AOSP 16]
- **Kernel variant:** [e.g., KernelSU, KernelSU Next, SukiSU Ultra, Vanilla, BakaSU]
- **Kernel version:** [e.g., `6.1.175-GKID/v26.07.26-r443/349b806bc`]

**To Reproduce**
Steps to reproduce the behavior:
1. Flash kernel via KernelSU app or Kernel Flasher or `fastboot`
2. Reboot device
3. [Describe what triggers the issue]

**Expected behavior**
What you expected to happen (e.g., "Device should boot normally with all features enabled").

**Logs (CRITICAL)**
Please provide **BOTH** logs as a **single ZIP file**:
1. Run `dmesg > /sdcard/dmesg.txt` in terminal
2. Copy pstore log: `cp /sys/fs/pstore/console-ramoops-0 /sdcard/`
3. **Zip both files** and attach here

**Screenshots**
If applicable, add screenshots of error messages or KernelSU manager.

**Additional context**
- Does the issue occur on specific variants only?
- Any recent changes before the bug appeared?
