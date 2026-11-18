#!/usr/bin/env bash
# Build a NoMount metamodule from the exact commit the kernel was built with.
#
# NoMount's userspace module and its kernel driver should be the same version.
# The official release ZIP also ships LKMs, but those are picked by matching
# "androidXX" in `uname -r`, which our kernel string does not contain, so they
# never load on GKID. With NM enabled the driver is built into the kernel
# instead, and this module (no LKMs) detects it as built-in.
#
# Usage: build_nomount_module.sh <40-char commit sha> <output dir>
# Requires: git, zip, and `zig` (or python -m ziglang) on PATH.

set -euo pipefail

COMMIT="${1:?NoMount commit sha required}"
OUT_DIR="${2:?output directory required}"

if ! [[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "NoMount commit must be a full 40-character SHA, got '$COMMIT'" >&2
  exit 2
fi

if command -v zig >/dev/null 2>&1; then
  ZIG=(zig)
else
  ZIG=(python3 -m ziglang)
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SRC="$WORK/src"
MOD="$WORK/module"

git init -q "$SRC"
git -C "$SRC" fetch -q --depth=1 https://github.com/maxsteeel/nomount.git "$COMMIT"
git -C "$SRC" checkout -q --detach FETCH_HEAD
actual="$(git -C "$SRC" rev-parse HEAD)"
if [ "$actual" != "$COMMIT" ]; then
  echo "NoMount source mismatch: expected $COMMIT, got $actual" >&2
  exit 1
fi

# Same flags as upstream's own CI (.github/workflows/build.yml in nomount).
mkdir -p "$SRC/bin"
(
  cd "$SRC/userspace/src"
  "${ZIG[@]}" cc -target aarch64-linux -Oz -Xclang -Oz -mcmodel=tiny -static -ffreestanding -flto \
    -fno-ident -fno-unwind-tables -fno-asynchronous-unwind-tables -Wl,--gc-sections,-z,norelro \
    -mllvm -enable-machine-outliner=always nm.c -o ../../bin/nm-arm64
  "${ZIG[@]}" cc -target arm-linux -Oz -Xclang -Oz -static -ffreestanding -flto -ffunction-sections \
    -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -fno-ident \
    -Wl,--gc-sections,-z,norelro nm.c -o ../../bin/nm-arm
)

cp -a "$SRC/module" "$MOD"
mkdir -p "$MOD/bin"
install -m 0755 "$SRC/bin/nm-arm64" "$MOD/bin/nm-arm64"
install -m 0755 "$SRC/bin/nm-arm" "$MOD/bin/nm-arm"

short="${COMMIT:0:7}"
sed -i "s/^version=\(.*\)/version=\1 (${short}-GKID)/" "$MOD/module.prop"
sed -i "s/^versionCode=.*/versionCode=1/" "$MOD/module.prop"
# Pinned build: don't let the manager offer upstream's (possibly mismatched) update.
sed -i '/^updateJson=/d' "$MOD/module.prop"
printf '%s\n' "$COMMIT" > "$MOD/NOMOUNT_SOURCE_COMMIT"

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
ZIP="$OUT_DIR/NoMount-Metamodule-${short}.zip"
(cd "$MOD" && zip -qr9 "$ZIP" .)

listing="$(unzip -Z1 "$ZIP")"
for f in module.prop customize.sh bin/nm-arm64 bin/nm-arm NOMOUNT_SOURCE_COMMIT; do
  grep -qxF "$f" <<< "$listing" || { echo "$f missing from $ZIP" >&2; exit 1; }
done
echo "Built $ZIP"
grep -E '^(version|versionCode)=' "$MOD/module.prop"
