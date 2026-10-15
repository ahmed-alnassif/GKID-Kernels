#!/usr/bin/env bash

# Reject the unsupported pairing before downloads, installers, or host changes.
# The source-only candidate lock does not grant build/runtime approval.
if [[ "${KSU:-}" == "KSUN" && "${KSU_SUSFS:-false}" == "true" ]]; then
  echo "KSUN+SUSFS is not enabled until compatibility is validated" >&2
  echo "See docs/root-manager-upstream-baseline.md for the pinned built-in candidate and remaining gates." >&2
  exit 1
fi

WORKDIR="$(pwd)"
RELEASE_DIR="$WORKDIR/artifacts"

# Only safe filename/version characters are accepted from workflow inputs.
KERNEL_NAME="${CUSTOM_VERSION_NAME:-Cogan}"
if [[ ! "$KERNEL_NAME" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Invalid CUSTOM_VERSION_NAME: use letters, digits, underscores or hyphens" >&2
  exit 1
fi
if [[ -n "${BUILD_REVISION:-}" ]]; then
  if [[ ! "$BUILD_REVISION" =~ ^r[0-9]+$ ]]; then
    echo "Invalid BUILD_REVISION: expected r followed by digits (e.g. r9)" >&2
    exit 1
  fi
  # Keep the requested revision visible while retaining a unique CI run suffix.
  RUN_NUM="-$BUILD_REVISION${RUN_NUM:-}"
fi
USER="ahmed-alnassif"
HOST="GKID"
TIMEZONE="Asia/Damascus"
ANYKERNEL_REPO="https://github.com/ahmed-alnassif/AK3-GKID"

KERNEL_DEFCONFIG="gki_defconfig"

KERNEL_VERSION="${KERNEL_VERSION:-6.1}"

sudo timedatectl set-timezone "$TIMEZONE" || export TZ="$TIMEZONE"

RELEASE="$(date +v%y.%m.%d)${RUN_NUM}"

mkdir -p $RELEASE_DIR

GKI_RELEASES_REPO="https://github.com/ahmed-alnassif/GKID-Kernels"
AK3_ZIP_NAME="$KERNEL_NAME-VARIANT-REL-KVER.zip"
OUTDIR="$WORKDIR/out"
KSRC="$WORKDIR/ksrc"
KERNEL_PATCHES="$WORKDIR/kernel-patches"
PATCHES_DIR="$WORKDIR/patches"

source $WORKDIR/functions.sh

if kernel_version_eq "$KERNEL_VERSION" "6.1"; then
  KERNEL_BRANCH="GKID-6.1"
else
  IFS='|' read -r KERNEL_REPO KERNEL_BRANCH KERNEL_KMI <<< "$(resolve_kernel_source "$KERNEL_VERSION")"
fi

# Verified upstream Makefile sublevels; historical commits are not build-tested.
if [ "$KERNEL_VERSION" = "6.1" ]; then
  case "${KERNEL_SUBLEVEL:-Auto}" in
    161) KERNEL_BRANCH="61fcbb6cd1dbc15d4af24bce8296367554f70b8b" ;;
    162) KERNEL_BRANCH="0182cb5b74ee79448adf4f33a137ca34e209eb30" ;;
    163) KERNEL_BRANCH="8ce36b2849ef65d98b77bcced8cf72333b2d5da0" ;;
    164) KERNEL_BRANCH="12ef02bd25146e1da089588c5f616a12ad5a4f32" ;;
    165) KERNEL_BRANCH="2f66dd9cff421f27dbe192f2035ce61b811561b1" ;;
    166) KERNEL_BRANCH="e094166185ce573ca9c33553c91945b06d2b3641" ;;
    167) KERNEL_BRANCH="188af7e32c7cbacb6b9fad6222c92645de5dde0d" ;;
    168) KERNEL_BRANCH="8e8fc038cad5988ede9f323677c28eb9a696026c" ;;
    169) KERNEL_BRANCH="bbb1b305ef9dcb2f94dbf0504408032a65b47073" ;;
    170) KERNEL_BRANCH="d7371afb22b1c6589a52e7cea3e2399ae2977412" ;;
    171) KERNEL_BRANCH="dd093409483f8cd5b495dfe6186cdee6713f8300" ;;
    172) KERNEL_BRANCH="fec170e6409ce49bc009a879fddb47f9a1ad9f01" ;;
    173) KERNEL_BRANCH="fca9c61b983f49374d193f67cdfeae3f68ec9af8" ;;
    174) KERNEL_BRANCH="ae51c26d207ea801c5346f6d2773878bf0d9036d" ;;
    175) KERNEL_BRANCH="bcff58130b54910112d233064b3b41b3c87d868f" ;;
    176) KERNEL_BRANCH="f26a1f4f9013533dd2b0de85e6813f948363a4ff" ;;
    Auto|177|"") ;;
    *) echo "Invalid 6.1 sublevel: $KERNEL_SUBLEVEL" >&2; exit 1 ;;
  esac
elif [ "${KERNEL_SUBLEVEL:-Auto}" != "Auto" ]; then
  echo "Specific sublevels require kernel 6.1" >&2; exit 1
fi

ANDROID_RELEASE="$(android_release_for_version "$KERNEL_VERSION")"
echo "KERNEL_VERSION=$KERNEL_VERSION" >> $GITHUB_ENV
echo "ANDROID_RELEASE=$ANDROID_RELEASE" >> $GITHUB_ENV
echo "KERNEL_SOURCE_REPO=$(simplify_gh_url "$KERNEL_REPO")" >> $GITHUB_ENV
echo "KERNEL_SOURCE_BRANCH=$KERNEL_BRANCH" >> $GITHUB_ENV

echo "RELEASE_REPO=$(simplify_gh_url "$GKI_RELEASES_REPO")" >> $GITHUB_ENV
echo "KERNEL_NAME=${KERNEL_NAME}${RUN_NUM}" >> $GITHUB_ENV
echo "RELEASE_NAME=$KERNEL_NAME $RELEASE" >> $GITHUB_ENV
echo "RELEASE=$RELEASE" >> $GITHUB_ENV

BUILD_LOGS="$RELEASE_DIR/build.log"
exec > >(tee -a "$BUILD_LOGS") 2>&1

trap 'echo "SCRIPT EXIT at $(date)" >> "$BUILD_LOGS"' EXIT
trap 'echo "[-] ERROR at line $LINENO: [[$BASH_COMMAND]]" >> "$BUILD_LOGS"' ERR
trap 'echo "[-] Received SIGTERM at $(date) - possible GitHub kill" >> "$BUILD_LOGS"' TERM
trap 'echo "[-] Received SIGINT at $(date)" >> "$BUILD_LOGS"' INT

log "Cloning kernel source from $(simplify_gh_url "$KERNEL_REPO")"
if kernel_version_eq "$KERNEL_VERSION" "6.1" && [[ "$KERNEL_BRANCH" =~ ^[0-9a-f]{40}$ ]]; then
  mkdir -p "$KSRC" || exit 1
  git -C "$KSRC" init -q || exit 1
  git -C "$KSRC" remote add origin "$KERNEL_REPO" || exit 1
  git -C "$KSRC" fetch -q --depth=1 origin "$KERNEL_BRANCH" || { echo "Historical source fetch failed" >&2; exit 1; }
  git -C "$KSRC" checkout -q --detach FETCH_HEAD || exit 1
  git -C "$KSRC" submodule update --init --recursive --depth=1 || exit 1
elif kernel_version_eq "$KERNEL_VERSION" "6.1"; then
  git clone -q --depth=1 --recurse-submodules "$KERNEL_REPO" -b "$KERNEL_BRANCH" "$KSRC" || exit 1
else
  git clone -q --depth=1 "$KERNEL_REPO" -b "$KERNEL_BRANCH" "$KSRC" || exit 1
fi

cd "$KSRC" || exit 1
LINUX_VERSION=$(make kernelversion) || exit 1
if [ "${KERNEL_SUBLEVEL:-Auto}" != "Auto" ] && [ "$LINUX_VERSION" != "6.1.$KERNEL_SUBLEVEL" ]; then
  echo "Kernel source version $LINUX_VERSION does not match requested 6.1.$KERNEL_SUBLEVEL" >&2
  exit 1
fi
LINUX_VERSION_CODE=${LINUX_VERSION//./}
DEFCONFIG_FILE=$(find ./arch/arm64/configs -name "$KERNEL_DEFCONFIG")
echo "LINUX_VERSION=$LINUX_VERSION" >> $GITHUB_ENV
cd $WORKDIR

log "Setting Kernel variant"
case "$KSU" in
  "SKSU") VARIANT="SukiSU-Ultra" ;;
  "BSU") VARIANT="BakaSU" ;;
  "KSU") VARIANT="KernelSU" ;;
  "KSUN") VARIANT="KernelSU-Next" ;;
  "no") VARIANT="Vanilla" ;;
  "vnlto") VARIANT="Vanilla+NoLTO" ;;
  *) VARIANT="Vanilla" ;;
esac

susfs_included && VARIANT+="+SuSFS"
SUSFS_URL="https://gitlab.com/simonpunk/susfs4ksu"
SUSFS_DIR="$WORKDIR/susfs"
SUSFS_PATCHES="${SUSFS_DIR}/kernel_patches"

if kernel_version_eq "$KERNEL_VERSION" "6.1"; then
  SUSFS_BRANCH="gki-android14-6.1"
  SUSFS_PATCH="gki-android14-6.1"
else
  SUSFS_BRANCH="$(resolve_susfs_branch "$KERNEL_VERSION")"
  SUSFS_PATCH="$SUSFS_BRANCH"
fi

log "Changelog of repos"
clone_susfs 5
cd "$SUSFS_DIR"
git log --pretty=format:"- [%h](https://${SUSFS_URL#https://}/commit/%H) %s" -5 "$SUSFS_BRANCH" \
> "$RELEASE_DIR/susfs_changelog-${KERNEL_VERSION}.txt"
cd ..

if kernel_version_eq "$KERNEL_VERSION" "6.1"; then
  generate_gh_changelog "ahmed-alnassif/GKI-Duchamp-6.1" "$KERNEL_BRANCH" 10 "$RELEASE_DIR/android_kernel-6.1_changelog.txt"
else
  echo "No changelog generator wired up yet for $KERNEL_VERSION" \
    > "$RELEASE_DIR/android_kernel-${KERNEL_VERSION}_changelog.txt"
fi
generate_gh_changelog "maxsteeel/nomount" "master" 5 "$RELEASE_DIR/nomount_changelog.txt"
generate_gh_changelog "tiann/KernelSU" "main" 5 "$RELEASE_DIR/ksu_changelog.txt"
generate_gh_changelog "Baka-SU/BakaSU" "main" 5 "$RELEASE_DIR/BakaSU_changelog.txt"

echo "::group::[*] Downloading Clang"
CLANG_BIN="$WORKDIR/neutron-clang/bin"
mkdir -p "$WORKDIR/neutron-clang"
cd "$WORKDIR/neutron-clang"
bash <(curl -s "https://raw.githubusercontent.com/Neutron-Toolchains/antman/main/antman") -S
cd $OLDPWD
if [ ! -d "$CLANG_BIN" ]; then
    error "Clang not found in ${CLANG_BIN}."
    exit 1
fi

export PATH="${CLANG_BIN}:$PATH"
echo "::endgroup::"

export CCACHE_DIR="$HOME/.ccache"
export CCACHE_BASEDIR="$WORKDIR"
export CCACHE_NOHARDLINK=true
export CCACHE_COMPILERCHECK=content
export CC="ccache clang"
export CXX="ccache clang++"

ccache --zero-stats
ccache --max-size=5G
ccache --set-config=sloppiness="pch_defines,time_macros,file_macro,include_file_mtime,include_file_ctime"
ccache --set-config=hash_dir=false
ccache --set-config=base_dir="$WORKDIR"
ccache --set-config=compiler_check=content

COMPILER_STRING=$(clang -v 2>&1 | head -n 1 | sed 's/(https..*//' | sed 's/ version//')
echo "COMPILER_STRING=$COMPILER_STRING" >> $GITHUB_ENV

cd $KSRC

echo "::group::[+] pahole installation"
build_and_install_pahole
echo "::endgroup::"

echo "::group::[+] Applied patches"

if ! kernel_version_eq "$KERNEL_VERSION" "6.1"; then
  apply_kernel_patches
  apply_force_load_module_patch
  apply_extract_cert_key_pass_patch
  cleanup_abi_gki_protected_exports
fi


if [ "${NETWORKING:-true}" = "true" ]; then
  log "Applying BBRv3 patch (Networking enabled)"
  apply_patch_file "$KERNEL_PATCHES/bbrv3/bbrv3.patch"
else
  log "Skipping optional BBRv3 patch (Networking disabled)"
fi


log "BBG included"
wget -qO- "https://github.com/vc-teahouse/Baseband-guard/raw/main/setup.sh" | bash
sed -i '/^config LSM$/,/^help$/{ /^[[:space:]]*default/ { /baseband_guard/! s/selinux/selinux,baseband_guard/ } }' "security/Kconfig"

if [ "$KSU" = "no" ] || [ "$KSU" = "vnlto" ] || [ "$No_DS" = "true" ]; then
  export DROIDSPACES="false"
  warning "DroidSpaces is not supported in this build"
  VARIANT+="+NoDS"
fi

if [ "$DROIDSPACES" = "true" ] && kernel_version_lt "$KERNEL_VERSION" "6.12"; then
  log "Applying DroidSpaces sysvipc patch"
  apply_patch_file "$KERNEL_PATCHES/droidspaces/001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch"
  if kernel_version_eq "$KERNEL_VERSION" "5.10"; then
    apply_patch_file "$KERNEL_PATCHES/droidspaces/002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch"
  fi
elif [ "$DROIDSPACES" = "true" ]; then
  log "Applying DroidSpaces sysvipc patch"
  apply_patch_file "$KERNEL_PATCHES/droidspaces/001.GKI-6.12-or-above-fix_sysvipc_kabi.patch"
fi

set -eo pipefail
if susfs_included && [ "$KSU" = "BSU" ]; then
  log "BakaSU included"
  install_ksu "Baka-SU/BakaSU" "main"

  clone_susfs
  apply_susfs_patches

fi

if [ "$KSU" = "KSUN" ]; then
  log "KernelSU Next included (experimental)"
  # Use the tag observed in the successful KSUN GKI 6.1 baseline, not the absent 'next' ref.
  KSUN_REF="v3.4.2"
  KSUN_EXPECTED_SHA="4c706b5938665866ebe16944a481a7b91e3396af"
  install_ksu "KernelSU-Next/KernelSU-Next" "$KSUN_REF"
  # Fail closed if upstream setup.sh silently falls back after a failed checkout.
  if [ -d "KernelSU-Next/.git" ]; then
    KSUN_INSTALLED_SHA="$(git -C KernelSU-Next rev-parse HEAD)" || exit 1
    log "KernelSU Next installed commit: $KSUN_INSTALLED_SHA (requested ref: $KSUN_REF)"
    KSUN_TAG_SHA="$(git -C KernelSU-Next rev-parse --verify "refs/tags/$KSUN_REF^{commit}")" || {
      error "KSUN requested tag $KSUN_REF is not present in checkout"
      exit 1
    }
    if [ "$KSUN_INSTALLED_SHA" != "$KSUN_EXPECTED_SHA" ] || [ "$KSUN_TAG_SHA" != "$KSUN_EXPECTED_SHA" ]; then
      error "KSUN checkout/tag mismatch: installed $KSUN_INSTALLED_SHA, tag $KSUN_TAG_SHA, expected immutable $KSUN_EXPECTED_SHA ($KSUN_REF)"
      exit 1
    fi
    log "KernelSU Next verified tag: $KSUN_REF ($KSUN_EXPECTED_SHA)"
    echo "KSUN_REF=$KSUN_REF" >> "$GITHUB_ENV"
    echo "KSUN_INSTALLED_SHA=$KSUN_INSTALLED_SHA" >> "$GITHUB_ENV"
  else
    error "KernelSU Next checkout missing after installer"
    exit 1
  fi
fi

if [ "$KSU" = "KSU" ]; then
  log "KernelSU included"
  if ! susfs_included; then
    install_ksu "tiann/KernelSU" "main"
  fi

  if susfs_included; then
    VARIANT+="+Multiple-Managers"
    git clone "https://github.com/tiann/KernelSU" && echo "[+] Repository cloned."
    clone_susfs

    cd KernelSU
    #git reset --hard "61c6313"
    git reset --soft HEAD~1
    apply_patch_file "$PATCHES_DIR/0001-feat-avc-log-spoofing.patch"
    #apply_patch_file "$PATCHES_DIR/0001-feat-add-multiple-managers.patch"
    #apply_patch_file "$PATCHES_DIR/0001-feat-throne_tracker-offload-to-kthread.patch"
    apply_patch_file "$SUSFS_PATCHES/KernelSU/10_enable_susfs_for_ksu.patch"
    apply_patch_file "$PATCHES_DIR/0001-feat-escape-persistent_allow_list-to-kthread.patch"
    apply_patch_file "$PATCHES_DIR/0001-feat-supercalls-allow-userspace-to-pull-list-entries.patch"
    sed -i "/    git pull && echo \"\[+\] Repository updated.\"/d" "kernel/setup.sh"
    git config --global user.email "mr.ahmed.nassif@gmail.com"
    git config --global user.name "Ahmed Al-Nassif"
    git add .
    git commit -m "susfs patch"
    cd ..
    bash "KernelSU/kernel/setup.sh" "main"

    apply_susfs_patches

  fi

fi

if [ "$KSU_COMPAT" = "true" ]; then
  if [ "$C_LTO" = "true" ]; then
    VARIANT="Compat+${VARIANT}"
  else
    VARIANT="Compat+NoLTO+${VARIANT}"
  fi
fi

echo "VARIANT=$VARIANT" >> $GITHUB_ENV

if [ "$NM" = "true" ]; then
  log "Applying NoMount"
  NOMOUNT_SETUP="$(mktemp)" || { error "Unable to allocate NoMount setup file"; exit 1; }
  if ! curl -fsSL "https://raw.githubusercontent.com/maxsteeel/nomount/refs/heads/dev/kernel/setup.sh" -o "$NOMOUNT_SETUP"; then
    rm -f "$NOMOUNT_SETUP"
    error "NoMount setup download failed"
    exit 1
  fi
  if ! bash "$NOMOUNT_SETUP" master; then
    rm -f "$NOMOUNT_SETUP"
    error "NoMount setup failed"
    exit 1
  fi
  rm -f "$NOMOUNT_SETUP"
fi
echo "::endgroup::"
set +eo pipefail

AK3_ZIP_NAME=${AK3_ZIP_NAME//KVER/$LINUX_VERSION}
AK3_ZIP_NAME=${AK3_ZIP_NAME//VARIANT/$VARIANT}

log "Applying configs..."
source "$WORKDIR/configs/gki_defconfig.sh"

if [ "${TODO:-kernel}" = "kernel" ]; then
  LATEST_COMMIT_HASH=$(git rev-parse --short HEAD)
  SUFFIX="${RUN_NUM}-${LATEST_COMMIT_HASH}"
  config --set-str CONFIG_LOCALVERSION "-${KERNEL_NAME}${SUFFIX}"
  config --disable CONFIG_LOCALVERSION_AUTO
  sed -i 's/echo "+"/# echo "+"/g' scripts/setlocalversion
fi

export KBUILD_BUILD_USER="$USER"
export KBUILD_BUILD_HOST="$HOST"
if [ "${BUILD_TIME:-N}" = "N" ]; then
  export KBUILD_BUILD_TIMESTAMP="$(LC_ALL=C date -u '+%a %b %d %H:%M:%S UTC %Y')"
else
  if [[ ! "$BUILD_TIME" =~ ^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[[:space:]](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[[:space:]][0-9]{1,2}[[:space:]][0-9]{2}:[0-9]{2}:[0-9]{2}[[:space:]]UTC[[:space:]][0-9]{4}$ ]]; then
    echo "Invalid BUILD_TIME format" >&2; exit 1
  fi
  date -u -d "$BUILD_TIME" >/dev/null || { echo "Invalid BUILD_TIME date" >&2; exit 1; }
  actual_day="$(LC_ALL=C date -u -d "$BUILD_TIME" +%a)"
  [ "${BUILD_TIME%% *}" = "$actual_day" ] || { echo "BUILD_TIME weekday mismatch" >&2; exit 1; }
  export KBUILD_BUILD_TIMESTAMP="$(LC_ALL=C date -u -d "$BUILD_TIME" '+%a %b %d %H:%M:%S UTC %Y')"
fi
export KCFLAGS="-w"

LINK_CACHE_PATH="/dev/shm/thinlto-cache"
LINKER_SHIM="/tmp/clang-lto-linker"
MAKE_ARGS=(
  LLVM=1
  LLVM_IAS=1
  ARCH=arm64
  CROSS_COMPILE=aarch64-linux-gnu-
  CROSS_COMPILE_COMPAT=arm-linux-gnueabi-
  -j$(nproc --all)
  O="$OUTDIR"
)

if [ "${LTO:-}" = "thinLTO" ] && [ "$CLEAN_LTO_CACHE" = "true" ]; then
  rm -rf "$LINK_CACHE_PATH"
  success "ThinLTO cache removed"
fi

if [ "${LTO:-}" = "thinLTO" ]; then
    log "ThinLTO cache enabled"
    mkdir -p "$LINK_CACHE_PATH"
    cat > "$LINKER_SHIM" << SHIM
#!/usr/bin/env bash
JOBCOUNT=\$(( \$(nproc --all) / 2 ))
exec ld.lld "\$@" --thinlto-cache-dir="$LINK_CACHE_PATH" --thinlto-jobs=\$JOBCOUNT
SHIM
    chmod +x "$LINKER_SHIM"
    MAKE_ARGS+=(LD="$LINKER_SHIM" HOSTLD="$LINKER_SHIM")
fi

KERNEL_IMAGE="$OUTDIR/arch/arm64/boot/Image"
MODULE_SYMVERS="$OUTDIR/Module.symvers"
KMI_CHECK="$WORKDIR/py/kmi-check-6.x.py"

echo "::group::[*] Generating config"
make ${MAKE_ARGS[@]} "$KERNEL_DEFCONFIG"
echo "::endgroup::"

# Report the resolved kernel configuration, not merely the requested fragments.
# Diagnostics only: avoid failing established builds on kernel-version differences.
log "Resolved Networking config (NETWORKING=${NETWORKING:-true})"
for symbol in CONFIG_TCP_CONG_BBR CONFIG_DEFAULT_BBR CONFIG_NET_SCH_FQ CONFIG_NET_SCH_FQ_CODEL CONFIG_IP_SET CONFIG_NETFILTER_XT_SET; do
  if grep -q "^${symbol}=y$" "$OUTDIR/.config"; then
    log "  ${symbol}=y"
  elif grep -q "^# ${symbol} is not set$" "$OUTDIR/.config"; then
    log "  ${symbol}=n"
  else
    log "  ${symbol}=unavailable or not built-in"
  fi
done

if susfs_included; then

  log "DEBUG: Checking defconfig for SUSFS"
  grep -i susfs ./arch/arm64/configs/gki_defconfig || error "SUSFS NOT FOUND in defconfig!"
  echo ""

  log "DEBUG: Checking .config for SUSFS"
  if ! grep -qx 'CONFIG_KSU_SUSFS=y' "$OUTDIR/.config"; then
    error "SUSFS NOT ENABLED in .config!"
    exit 1
  fi
  if ! grep -qx 'CONFIG_KSU_SUSFS_SUS_MAP=y' "$OUTDIR/.config"; then
    error "SUSFS_SUS_MAP not enabled!"
    exit 1
  fi
  echo ""

fi

if [ "$TEST" = "yes" ]; then
  success "Pipeline test done"
  mkdir -p "$RELEASE_DIR"
  echo "test-${VARIANT}" > "$RELEASE_DIR/test-${VARIANT}.zip"
  exit 0
fi

if [[ $TODO == "defconfig" ]]; then
  log "Copying defconfig"
  mkdir -p "$RELEASE_DIR"
  cp "$OUTDIR/.config" "$RELEASE_DIR/config-${VARIANT}.txt"
  exit 0
fi

echo "::group::[*] Aggressive Resource Optimization for FullLTO"

info "Initial storage: $(df -h / | awk 'NR==2 {print $4}') available"
info "Initial memory: $(free -h | awk '/^Mem:/ {print $7}') available"

sudo apt-get clean -qq
sudo apt-get autoremove -y -qq
sudo apt-get autoclean -qq
sudo rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /var/cache/apt/*

for dir in \
    /usr/share/dotnet \
    /usr/local/lib/android \
    /usr/local/share/powershell \
    /usr/local/share/chromium \
    /usr/local/lib/node_modules \
    /opt/ghc \
    /usr/local/.ghcup \
    /opt/hostedtoolcache \
    /usr/local/share/boost \
    /usr/local/share/gradle-* \
    /usr/local/share/kotlin \
    /usr/local/share/sbt \
    /usr/share/swift \
    /usr/local/share/php \
    /usr/local/share/rust \
    /usr/local/share/go \
    /usr/local/julia* \
    /usr/share/az_* \
    /usr/share/miniconda \
    /opt/microsoft \
    /opt/google \
    /opt/az \
    /usr/lib/jvm \
    /usr/local/lib/heroku \
    /var/lib/containers \
    /var/lib/docker \
    /var/lib/gems \
    /var/lib/mysql \
    /var/lib/postgresql \
    /var/lib/snapd \
    /var/cache/* \
    /tmp/* \
    /home/runner/.cargo \
    /home/runner/.rustup \
    /home/runner/.npm \
    /home/runner/.cache \
    /home/runner/go \
    /home/runner/.local/share \
    /home/runner/.dotnet \
    /home/runner/.gradle \
    /home/runner/.m2 \
    /etc/skel \
    /home/packer \
    /opt/pipx; do
    if [ -e "$dir" ]; then
        SIZE=$(du -sh "$dir" 2>/dev/null | cut -f1 || echo "?")
        sudo rm -rf "$dir" 2>/dev/null || true
        success "Removed $dir ($SIZE)"
    fi
done

sudo docker system prune -af --volumes 2>/dev/null || true
sudo docker builder prune -af 2>/dev/null || true
sudo docker image prune -af 2>/dev/null || true

sudo journalctl --vacuum-size=1M 2>/dev/null || true
sudo find /var/log -type f \( -name "*.log" -o -name "*.gz" -o -name "*.1" -o -name "*.old" \) -delete 2>/dev/null || true
sudo rm -rf /var/log/journal/* 2>/dev/null || true

if [ -f /swapfile ]; then
    sudo swapoff /swapfile 2>/dev/null || true
    sudo rm -f /swapfile
fi
if [ -f /mnt/swapfile ]; then
    sudo swapoff /mnt/swapfile 2>/dev/null || true
    sudo rm -f /mnt/swapfile
fi

warning "Creating 32GB swap"
sudo fallocate -l 32G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=32768 status=none
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
success "32GB swap created and activated"

sudo sysctl -w vm.swappiness=90
sudo sysctl -w vm.vfs_cache_pressure=200
sudo sysctl -w vm.dirty_ratio=5
sudo sysctl -w vm.dirty_background_ratio=2
sudo sysctl -w vm.drop_caches=3
sudo sysctl -w vm.overcommit_memory=1

success "Final storage: $(df -h / | awk 'NR==2 {print $4}') available"
success "Final memory:  $(free -h | awk '/^Mem:/ {print $7}') available | Swap: $(free -h | awk '/^Swap:/ {print $2}')"
echo "::endgroup::"

set -eo pipefail
echo "::group::[*] Building kernel"
make ${MAKE_ARGS[@]} CC="ccache clang" CXX="ccache clang++"
echo "::endgroup::"
set -eo pipefail

cd "$WORKDIR"

log "Cloning anykernel from $(simplify_gh_url "$ANYKERNEL_REPO")"
git clone -q --depth=1 $ANYKERNEL_REPO anykernel

AK3_ZIP_NAME=${AK3_ZIP_NAME//REL/$RELEASE}
sed -i \
  -e "s/kernel.string=.*/kernel.string=${KERNEL_NAME} ${RELEASE} ${LINUX_VERSION} ${VARIANT} by Ahmed Al-Nassif (ahmed-alnassif)/g" \
  -e "s/supported_kernel=\".*\"/supported_kernel=\"${KERNEL_VERSION}\"/g" \
  $WORKDIR/anykernel/anykernel.sh

cd anykernel
log "Zipping anykernel"
if [ ! -f "$KERNEL_IMAGE" ];then
  error "$KERNEL_IMAGE not found."
  exit 1
fi
cp "$KERNEL_IMAGE" .
# Package only the AnyKernel payload; reject embedded archives and missing flash entrypoint.
python3 - "$WORKDIR/$AK3_ZIP_NAME" <<'PY'
import pathlib, sys, zipfile
root = pathlib.Path.cwd()
output = pathlib.Path(sys.argv[1])
files = sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)
if not (root / "anykernel.sh").is_file() or not (root / "Image").is_file():
    raise SystemExit("Packaging failed: AnyKernel entrypoint or kernel Image missing")
nested = [str(p.relative_to(root)) for p in files if p.suffix.lower() in {".zip", ".7z", ".rar"}]
if nested:
    raise SystemExit("Packaging failed: nested archives found: " + ", ".join(nested))
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for file in files:
        archive.write(file, file.relative_to(root).as_posix())
with zipfile.ZipFile(output) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit("Packaging failed: corrupt ZIP member " + bad)
    names = set(archive.namelist())
    if "anykernel.sh" not in names or "Image" not in names:
        raise SystemExit("Packaging failed: invalid ZIP root layout")
print("Validated flash ZIP:", output.name)
PY
cd "$OLDPWD"

echo "BASE_NAME=$KERNEL_NAME-$VARIANT" >> $GITHUB_ENV
mkdir -p "$RELEASE_DIR"
mv -- "$WORKDIR/$AK3_ZIP_NAME" "$RELEASE_DIR/"
