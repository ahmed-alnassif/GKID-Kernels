#!/usr/bin/env python3
"""KMI compatibility gate of a built kernel against a device's vendor modules (offline).

On a GKI phone the boot partition holds only the generic kernel; the SoC and phone
drivers are vendor_dlkm / system_dlkm modules built against the frozen KMI. They
load on another kernel only if:
  1. the KMI generation matches (rothko stock: 6.1.138-android14-11 -> 11);
  2. every symbol of the ACK symbol lists those modules were built with is
     exported (missing exports cannot be forced) - by the kernel, or by a GKI
     module (modules.bzl, e.g. bluetooth.ko) that the phone loads from its stock
     system_dlkm: such symbols are accepted when a GKI module of the exporting
     source's directory exists, and listed in the report;
  3. the Google-signed GKI modules may still export protected symbols: our kernel
     does not trust Google's key, so android/abi_gki_protected_exports_* must be
     gone from the source (GKID removes it; gkid_parity.py for older sublevels);
  4. symbol CRC differences do not refuse the module: the GKID force-load change
     in kernel/module/version.c turns them into a warning. Differences against the
     frozen ABI (android/abi_gki_aarch64.stg) are still reported: each one is a
     changed KMI type worth a look before testing on a phone.

With --reference BSP_SRC (the phone maker's own kernel source, for rothko the Xiaomi
BSP in cogan17/Xiomi-14t-pro) the GKI build is also held against it:
  5. the BSP's KMI generation is the phone's;
  6. every symbol of the BSP's own symbol lists is exported (as in 2);
  7. every CONFIG_*=y of the BSP's gki_defconfig is =y in the built .config, except
     the reviewed exceptions listed per device;
  8. every vendor hook the BSP declares (include/trace/hooks) that the GKI source
     lacks is unused by the vendor modules (its __tracepoint_ symbol is in no symbol
     list); unused ones are only reported. Xiaomi/MediaTek features themselves live
     in the phone's vendor modules, which these checks keep loadable.

Usage: kmi_compat.py --device rothko KERNEL_SRC OUT_DIR [--reference BSP_SRC]
                     [--github-env FILE] [--json FILE]
Exit 1 when 1-3, 5-7 or the force-load change fail; CRC differences only warn.
"""
import argparse
import json
import re
import sys
from pathlib import Path

DEVICES = {
    # Xiaomi 14T Pro: MediaTek MT6989; stock kernel 6.1.138-android14-11.
    "rothko": {"name": "Xiaomi 14T Pro (rothko)", "generation": "11",
               "lists": ["abi_gki_aarch64", "abi_gki_aarch64_mtk", "abi_gki_aarch64_xiaomi"],
               # Xiaomi BSP (6.1.57) gki_defconfig =y options that are not =y in GKID 6.1, reviewed
               # 2026-10-16: none provides anything the phone's vendor modules use.
               "bsp_config_exceptions": {
                   "CONFIG_DEBUG_STACK_USAGE": "debug statistics only",
                   "CONFIG_MEDIA_CEC_RC": "HDMI-CEC remote control keys; no HDMI-CEC on the phone",
                   "CONFIG_UAPI_HEADER_TEST": "build-time header test, not in the kernel",
               }},
}
FORCE_LOAD = re.compile(r"disagrees about version of symbol.*but ignore")
HOOK = re.compile(r"DECLARE_(?:RESTRICTED_)?HOOK\(\s*(\w+)")


def vendor_hooks(src):
    hooks = set()
    for header in sorted((src / "include/trace/hooks").glob("*.h")):
        hooks.update(HOOK.findall(header.read_text(encoding="utf-8", errors="replace")))
    return hooks
GKI_MODULE = re.compile(r'"([A-Za-z0-9_./-]+\.ko)"')


def gki_module_exports(src, symbols):
    """symbol -> GKI module (modules.bzl) whose directory's sources export it."""
    modules = GKI_MODULE.findall((src / "modules.bzl").read_text(encoding="utf-8")) \
        if (src / "modules.bzl").is_file() else []
    by_dir = {}
    for module in modules:
        by_dir.setdefault(str(Path(module).parent), []).append(module)
    found = {}
    for directory, owners in sorted(by_dir.items()):
        for source in sorted((src / directory).glob("*.c")):
            text = source.read_text(encoding="utf-8", errors="replace")
            for symbol in symbols - found.keys():
                if re.search(r"EXPORT_SYMBOL\w*\(\s*" + re.escape(symbol) + r"\s*[,)]", text):
                    found[symbol] = owners[0] if len(owners) == 1 else " / ".join(owners)
    return found


def read_list(path):
    symbols = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "[")):
            symbols.add(line)
    return symbols


def read_symvers(path):
    exported = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            exported[fields[1]] = int(fields[0], 16)
    return exported


def read_stg(path):
    """name -> crc of the frozen ABI's elf_symbol blocks that carry a crc."""
    crcs, block = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line == "elf_symbol {":
            block = {}
        elif line == "}" and block is not None:
            if "name" in block and "crc" in block:
                crcs[block["name"]] = int(block["crc"], 16)
            block = None
        elif block is not None and ":" in line:
            key, value = (part.strip() for part in line.split(":", 1))
            block[key] = value.strip('"')
    return crcs


def generation(src):
    match = re.search(r"^KMI_GENERATION=(\d+)$", (src / "build.config.common").read_text(), re.MULTILINE)
    return match.group(1) if match else None


def check(src, out, device, reference=None):
    spec = DEVICES[device]
    report = {"device": spec["name"], "kmi_generation": generation(src), "lists": {}, "errors": []}
    if report["kmi_generation"] != spec["generation"]:
        report["errors"].append(f"KMI generation {report['kmi_generation']}, the phone needs {spec['generation']}")
    symvers = out / "vmlinux.symvers"
    if not symvers.is_file():
        symvers = out / "Module.symvers"
    exported = read_symvers(symvers)
    wanted = set()
    for name in spec["lists"]:
        wanted |= read_list(src / "android" / name)
    from_modules = gki_module_exports(src, wanted - exported.keys())
    report["from_gki_modules"] = dict(sorted(from_modules.items()))
    for name in spec["lists"]:
        symbols = read_list(src / "android" / name)
        missing = sorted(symbols - exported.keys() - from_modules.keys())
        report["lists"][name] = {"symbols": len(symbols), "missing": missing}
        if missing:
            report["errors"].append(f"{name}: {len(missing)} symbol(s) not exported, e.g. {', '.join(missing[:5])}")
    frozen = read_stg(src / "android/abi_gki_aarch64.stg")
    report["crc_differences"] = sorted(name for name in wanted & frozen.keys() & exported.keys()
                                       if frozen[name] != exported[name])
    report["force_load"] = bool(FORCE_LOAD.search((src / "kernel/module/version.c").read_text(errors="replace")))
    if not report["force_load"]:
        report["errors"].append("module force-load change missing (CRC differences would refuse vendor modules)")
    report["protected_exports"] = sorted(p.name for p in (src / "android").glob("*protected_exports*"))
    if report["protected_exports"]:
        report["errors"].append("protected exports still present: " + ", ".join(report["protected_exports"]))
    if reference:
        check_reference(report, reference, src, out, spec, exported)
    return report


def read_config(path):
    values = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def check_reference(report, reference, src, out, spec, exported):
    """Hold the GKI build against the phone maker's own kernel source (BSP)."""
    ref = {"kmi_generation": generation(reference), "lists": {}}
    if ref["kmi_generation"] != spec["generation"]:
        report["errors"].append(f"BSP KMI generation {ref['kmi_generation']}, the phone needs {spec['generation']}")
    wanted = set()
    for name in spec["lists"]:
        wanted |= read_list(reference / "android" / name)
    from_modules = gki_module_exports(src, wanted - exported.keys())
    for name in spec["lists"]:
        symbols = read_list(reference / "android" / name)
        missing = sorted(symbols - exported.keys() - from_modules.keys())
        ref["lists"][name] = {"symbols": len(symbols), "missing": missing}
        if missing:
            report["errors"].append(f"BSP {name}: {len(missing)} symbol(s) not exported, e.g. {', '.join(missing[:5])}")
    bsp = read_config(reference / "arch/arm64/configs/gki_defconfig")
    built = read_config(out / ".config")
    off = sorted(key for key, value in bsp.items() if value == "y" and built.get(key) != "y")
    exceptions = spec.get("bsp_config_exceptions", {})
    ref["config_not_enabled"] = {key: exceptions.get(key, "NOT REVIEWED") for key in off}
    unreviewed = [key for key in off if key not in exceptions]
    if unreviewed:
        report["errors"].append("BSP gki_defconfig options not enabled: " + ", ".join(unreviewed[:10]))
    every_list = set()
    for path in sorted((reference / "android").glob("abi_gki_aarch64*")):
        if path.suffix != ".stg" and "." not in path.name:
            every_list |= read_list(path)
    absent = sorted(vendor_hooks(reference) - vendor_hooks(src))
    used = [hook for hook in absent if f"__tracepoint_{hook}" in every_list]
    ref["bsp_hooks_absent"] = {hook: ("USED by vendor modules" if hook in used else "unused by vendor modules")
                               for hook in absent}
    if used:
        report["errors"].append("BSP vendor hooks missing but used by vendor modules: " + ", ".join(used))
    report["reference"] = ref


def summary(report):
    lists = ", ".join(f"{name.replace('abi_gki_aarch64', 'GKI').replace('GKI_', '')} "
                      f"{info['symbols'] - len(info['missing'])}/{info['symbols']}"
                      for name, info in report["lists"].items())
    verdict = "OK" if not report["errors"] else "GAGAL / FAILED"
    line = (f"KMI {report['device']}: {verdict}; generation {report['kmi_generation']}; exported {lists} "
            f"({len(report['from_gki_modules'])} via GKI modules); "
            f"CRC differs {len(report['crc_differences'])} (force-load {'on' if report['force_load'] else 'OFF'})")
    ref = report.get("reference")
    if ref:
        bsp = ", ".join(f"{name.replace('abi_gki_aarch64', 'GKI').replace('GKI_', '')} "
                        f"{info['symbols'] - len(info['missing'])}/{info['symbols']}"
                        for name, info in ref["lists"].items())
        line += (f"; BSP: generation {ref['kmi_generation']}, exported {bsp}, "
                 f"config =y not enabled {len(ref['config_not_enabled'])} (reviewed), "
                 f"BSP-only vendor hooks {len(ref['bsp_hooks_absent'])} (unused)")
    return line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True, choices=sorted(DEVICES))
    parser.add_argument("src", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--reference", type=Path, help="phone maker's kernel source (BSP) to hold the build against")
    parser.add_argument("--github-env")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = check(args.src, args.out, args.device, args.reference)
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: KMI check could not run: {exc}", file=sys.stderr)
        return 1
    line = summary(report)
    print(line)
    for error in report["errors"]:
        print("BLOCKED: " + error, file=sys.stderr)
    if report["crc_differences"]:
        print(f"WARNING: CRC differs from the frozen ABI for: {', '.join(report['crc_differences'][:20])}"
              + (" ..." if len(report["crc_differences"]) > 20 else ""))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.github_env:
        with open(args.github_env, "a", encoding="utf-8") as handle:
            handle.write(f"KMI_COMPAT={line}\n")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
