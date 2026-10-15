# Bootloop Guide

[🇮🇩 Bahasa Indonesia](bootloop.md) · **🇬🇧 English** · [← README](../README.en.md)

> [!IMPORTANT]
> Do **section 1 before flashing any kernel**. Without your stock `boot.img`, recovery is much harder.

---

## Signs of a bootloop

- The phone is stuck on the logo, keeps restarting, or drops into fastboot by itself.
- The first boot after flashing a kernel is usually no slower than a normal boot. If you haven't reached the lock screen after about 5 minutes, treat it as a bootloop.

---

## 1. Keep your stock `boot.img` (before flashing)

AnyKernel3 writes the kernel to the **`boot`** partition of the active slot. To recover you need the `boot.img` from **exactly the same** ROM version.

**Option A: copy it from the phone (rooted)**

- [Kernel Flasher](https://github.com/capntrips/KernelFlasher): select the active slot, then *Backup*.
- Or with ADB:

```sh
adb shell
su
dd if=/dev/block/by-name/boot$(getprop ro.boot.slot_suffix) of=/sdcard/boot-stock.img
exit
exit
adb pull /sdcard/boot-stock.img
```

**Option B: take it from the official ROM**

- Download the official ROM with exactly the same version (see *Settings → About phone*).
- Fastboot ROM: take `images/boot.img`.
- Recovery/OTA ROM (contains `payload.bin`): extract `boot.img` with [payload-dumper-go](https://github.com/ssut/payload-dumper-go).

Keep the `boot.img` on your PC. Also install [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) (`adb` and `fastboot`), plus a USB driver on Windows.

If you patched `init_boot` before (Magisk or KernelSU LKM mode), keep the stock `init_boot.img` as well.

---

## 2. Recover from a bootloop

1. Enter **fastboot** mode. The key combination depends on the phone; for Xiaomi see section 3.
2. Connect to the PC and check with `fastboot devices`.
3. Flash the stock `boot.img` back to the active slot:

```sh
fastboot getvar current-slot
fastboot flash boot boot-stock.img
fastboot reboot
```

`fastboot flash boot` writes to the active slot automatically. Your data is **not** wiped.

4. If you also changed `init_boot`, also run `fastboot flash init_boot init_boot-stock.img`.

A kernel bootloop does **not** need `fastboot -w`, `fastboot erase` or a factory reset.

---

## 3. Xiaomi 14T Pro (rothko)

| | |
|---|---|
| Codename | `rothko` |
| SoC | MediaTek Dimensity 9300+ (MT6989) |
| Partitions | A/B (slots `_a` / `_b`) |
| Stock kernel | GKI `android14-6.1` (e.g. `6.1.138-android14-11`) |
| ROM | HyperOS (e.g. `OS3.0.301.0.WNNIDXM`) |

**Enter fastboot:** hold **Volume Down + Power** until **FASTBOOT** appears. During a bootloop, keep holding both keys until the fastboot screen shows.

**Steps:**

1. Make sure the `boot.img` comes from **exactly the same** HyperOS version that is installed.
2. Run the commands in section 2.
3. The phone boots with the stock kernel and your data stays intact.

**Never:**

- Run `flash_all_lock` from a fastboot ROM. It locks the bootloader; with modified partitions the phone can hard brick.
- Flash a ROM **older** than the installed version. Xiaomi uses anti-rollback, and a downgrade can hard brick the phone.
- Use SP Flash Tool or MediaTek BROM mode. It usually needs an authorized Xiaomi account and can wipe the modem/IMEI calibration.
- Flash `boot.img` to any other partition (`init_boot`, `vendor_boot`, and so on).

The stock Xiaomi recovery (**Volume Up + Power**) cannot flash `boot.img`, so use fastboot.

**Still bootlooping after flashing the stock `boot.img`?**

1. Flash the official fastboot ROM of the same version with `flash_all_except_storage` (keeps your data).
2. If that still fails, take the phone to an official Xiaomi service center.

---

## 4. After a successful boot: collect logs

The panic log of the failed boot is kept in memory for a while (pstore) and is **overwritten after the next restart**. So as soon as the phone is back up:

1. Take a bug report via *Developer options → Bug report → Full report*, or run `adb bugreport` from a PC.
2. Open an [Issue](https://github.com/cogan17/Cogan/issues) and attach:
   - the bug report file (`.zip`),
   - the name of the kernel ZIP you flashed (variant and release or run number),
   - the phone model and ROM version.

A bug report like this is what found the cause of the KernelSU Next + SUSFS test build bootloop ([record](validation/ksun-susfs-6.1-bootloop-fix.json)).

---

## 5. Trying again safely

- Pick the **same or a newer** sublevel than your stock kernel.
- `Compat` variants (built through **All variants (advanced)**) are built without LTO for phones that do not boot the standard variants.
- Variants marked **(uji)** are test builds only. Always keep your stock `boot.img` before trying one.
