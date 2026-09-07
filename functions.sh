#!/usr/bin/env bash

declare -A ANDROID_RELEASE_FOR_KVER=(
  ["5.10"]="12"
  ["5.15"]="13"
  ["6.1"]="14"
  ["6.6"]="15"
  ["6.12"]="16"
)

declare -A GKI_BRANCH=(
  ["5.10"]="android12-5.10"
  ["5.15"]="android13-5.15"
  ["6.6"]="android15-6.6"
  ["6.12"]="android16-6.12"
)

declare -A GKI_AOSP_BRANCH=(
  ["5.10"]="android12-5.10-lts"
  ["5.15"]="android13-5.15-lts"
  ["6.6"]="android15-6.6-lts"
  ["6.12"]="android16-6.12-lts"
)

declare -A GKI_SUSFS_BRANCH=(
  ["5.10"]="gki-android12-5.10"
  ["5.15"]="gki-android13-5.15"
  ["6.1"]="gki-android14-6.1"
  ["6.6"]="gki-android15-6.6"
  ["6.12"]="gki-android16-6.12"
)

android_release_for_version() {
  echo "${ANDROID_RELEASE_FOR_KVER[$1]:-unknown}"
}

resolve_kernel_source() {
  local ver="$1"
  local branch="${GKI_AOSP_BRANCH[$ver]:-}"
  local kmi="${GKI_BRANCH[$ver]:-}"

  if [ -z "$branch" ]; then
    error "No AOSP GKI branch mapped for KERNEL_VERSION='$ver' (see GKI_AOSP_BRANCH in functions.sh)"
    exit 1
  fi

  echo "https://android.googlesource.com/kernel/common|$branch|$kmi"
}

resolve_susfs_branch() {
  local ver="$1"
  local branch="${GKI_SUSFS_BRANCH[$ver]:-}"

  if [ -z "$branch" ]; then
    error "No susfs4ksu branch mapped for KERNEL_VERSION='$ver'"
    exit 1
  fi

  echo "$branch"
}

kernel_version_lt() {
  [ "$1" = "$2" ] && return 1
  local IFS=.
  local -a a=($1) b=($2)
  local i max=${#a[@]}
  [ ${#b[@]} -gt "$max" ] && max=${#b[@]}
  for ((i=0; i<max; i++)); do
    local ai="${a[i]:-0}"
    local bi="${b[i]:-0}"
    if ((10#$ai < 10#$bi)); then return 0; fi
    if ((10#$ai > 10#$bi)); then return 1; fi
  done
  return 1
}

apply_ntsync_compat_patch() {
  local branch="$1"
  local url="https://github.com/WildKernels/kernel_patches/raw/main/common/ntsync/ntsync_compat_${branch}.patch"

  if command curl -LSsf -o /dev/null "$url" 2>/dev/null; then
    curl -LSs "$url" | patch -p1 --fuzz=3
    success "NTSync compat patch applied for $branch"
  else
    warning "No NTSync compat patch found for $branch"
  fi
}

install_ksu() {
  local REPO="$1"
  local REF="$2"
  local URL

  if [ -z "$REPO" ] || [ -z "$REF" ]; then
    echo "Usage: install_ksu <user/repo> <ref>"
    exit 1
  fi

  URL="https://raw.githubusercontent.com/$REPO/$REF/kernel/setup.sh"
  log "Installing KernelSU from $REPO | $REF"
  curl -LSs "$URL" | bash -s "$REF"
}

ksu_included() {
  [ "$KSU" == "yes" ]
  return $?
}

susfs_included() {
  [ "$KSU_SUSFS" == "true" ]
  return $?
}

simplify_gh_url() {
  local URL="$1"
  echo "$URL" | sed "s|https://github.com/||g" | sed "s|.git||g"
}

config() {
  $KSRC/scripts/config --file $DEFCONFIG_FILE $@
}

log() {
  echo -e "[*] $*"
}
info() { log "$@"; }

success() {
  echo -e "[+] $*"
}

warning() {
  echo -e "[!] $*"
}

error() {
  echo -e "[-] $*"
}

retry() {
    local max_attempts=5
    local delay=2
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if "$@"; then
            return 0
        fi

        error "Command failed (attempt $attempt/$max_attempts): $*"
        log "Retrying in ${delay}s..."
        sleep $delay
        delay=$((delay + 1))
        attempt=$((attempt + 1))
    done

    error "Command failed after $max_attempts attempts: $*" >&2
    return 1
}

curl() { retry command curl "$@"; }
wget() { retry command wget "$@"; }

bash() {
    case "$*" in

        *curl*|*wget*|*git*clone*|*git*fetch*|*git*pull*|*git*push*|*git*ls-remote*|*git*submodule*)
            retry command bash "$@"
            ;;
        *)
            command bash "$@"
            ;;
    esac
}

git() {
    local cmd="$1"
    shift

    case "$cmd" in
        clone|fetch|pull|push|ls-remote|submodule)
            retry command git "$cmd" "$@"
            ;;
        *)
            command git "$cmd" "$@"
            ;;
    esac
}

export -f retry curl git wget bash

generate_gh_changelog() {
    local repo="$1"
    local branch="$2"
    local count="${3:-5}"
    local output="$4"

    gh api "repos/${repo}/commits?sha=${branch}&per_page=${count}" \
        --jq '.[] | "- [" + .sha[0:7] + "](" + .html_url + ") " + (.commit.message | split("\n")[0])' \
        > "$output"
}

apply_patch_file() {
    local patch="$1"
    local patch_data=""

    if [[ -n "$patch" && -f "$patch" ]]; then
        patch_data=$(cat "$patch")
        info "Applying: $(basename "$patch")"
    elif [[ -n "$patch" ]]; then
        patch_data="$patch"
        info "Applying patch from data"
    else
        patch_data=$(cat)
        info "Applying patch from stdin"
    fi

    [[ -z "$patch_data" ]] && { error "No patch data"; return 1; }

    if echo "$patch_data" | git apply --check - 2>/dev/null; then
        if echo "$patch_data" | git apply - 2>/dev/null; then
            success "Applied patch successfully"
            return 0
        fi
    fi

    warning "git apply failed, trying patch with fuzz"

    if ! echo "$patch_data" | patch -p1 --fuzz=3 --dry-run 2>/dev/null; then
        warning "Skipping: patch does not apply"
        return 1
    fi

    if echo "$patch_data" | patch -p1 --fuzz=3 2>/dev/null; then
        success "Applied patch with fuzz"
        return 0
    else
        error "Failed to apply patch"
        return 1
    fi
}

apply_kernel_patches() {
    local patch_dir="${1:-$KERNEL_PATCHES/common}"
    local failed=0

    [[ ! -d "$patch_dir" ]] && { error "$patch_dir not found"; return 1; }

    local patches=()
    while IFS= read -r -d '' patch; do
        patches+=("$patch")
    done < <(find "$patch_dir" -type f \( -name "*.patch" -o -name "*.diff" \) -print0 | sort -z -V)

    [[ ${#patches[@]} -eq 0 ]] && { warning "No patches found in $patch_dir"; return 0; }

    info "Found ${#patches[@]} patches in $patch_dir"

    for patch in "${patches[@]}"; do
        if ! apply_patch_file "$patch"; then
            ((failed++))
        fi
    done

    [[ $failed -eq 0 ]] && success "All patches applied successfully" || warning "Applied $((${#patches[@]} - failed))/${#patches[@]} patches, $failed failed"
    return $failed
}

apply_force_load_module_patch() {
    local file=""

    if [[ -f "kernel/module/version.c" ]]; then
        file="kernel/module/version.c"
    elif [[ -f "kernel/module.c" ]]; then
        file="kernel/module.c"
    else
        warning "Module file not found - skipping force load patch"
        return 0
    fi

    if grep -q "disagrees about version of symbol.*but ignore" "$file"; then
        success "Force load module patch already applied"
        return 0
    fi

    sed -i 's/pr_warn("%s: disagrees about version of symbol %s\\n", info->name, symname);/pr_warn("%s: disagrees about version of symbol %s, but ignore...\\n", info->name, symname);/' "$file"
    sed -i 's/return 0;/return 1;/' "$file"

    success "Force load module patch applied via sed"
}

apply_extract_cert_key_pass_patch() {
    local file="certs/extract-cert.c"

    if [[ ! -f "$file" ]]; then
        warning "extract-cert.c not found - skipping key_pass patch"
        return 0
    fi

    if grep -q "ifdef USE_PKCS11_ENGINE" "$file" && grep -qB2 "static const char \*key_pass;" "$file" | grep -q "ifdef USE_PKCS11_ENGINE"; then
        success "extract-cert key_pass patch already applied"
        return 0
    fi

    sed -i '/^static const char \*key_pass;/i #ifdef USE_PKCS11_ENGINE' "$file"
    sed -i '/^static const char \*key_pass;/a #endif' "$file"

    sed -i 's/^\([[:space:]]*\)if (key_pass)$/\1#ifdef USE_PKCS11_ENGINE\n\1if (key_pass)/' "$file"
    sed -i '/ERR(!ENGINE_ctrl_cmd_string(e, "PIN", key_pass, 0), "Set PKCS#11 PIN");/a #endif' "$file"

    success "extract-cert key_pass patch applied via sed"
}

fix_task_mmu_corruption() {
    local file="fs/proc/task_mmu.c"

    if [[ ! -f "$file" ]]; then
        warning "task_mmu.c not found - skipping fix"
        return 0
    fi

    if grep -q "if (vma->vm_file) {" "$file"; then
        sed -i '/if (vma->vm_file) {/d' "$file"
        success "task_mmu.c corruption fixed via sed"
    else
        success "task_mmu.c already fixed"
    fi
}

fix_namespace_susfs_mount() {
    local file="fs/namespace.c"

    if [[ ! -f "$file" ]]; then
        warning "namespace.c not found - skipping fix"
        return 0
    fi

    if grep -q "#define CL_COPY_MNT_NS" "$file" && grep -q "extern struct static_key_true susfs_is_sdcard_android_data_not_decrypted" "$file"; then
        success "namespace.c SuSFS mount definitions already applied"
        return 0
    fi

    sed -i '/#include <linux\/mnt_idmapping.h>/a #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n#include <linux/susfs_def.h>\n#endif' "$file"

    sed -i '/#include "internal.h"/a \\n#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\nextern bool susfs_is_current_ksu_domain(void);\nextern struct static_key_true susfs_is_sdcard_android_data_not_decrypted;\n\n#define CL_COPY_MNT_NS BIT(25)\n\n#endif' "$file"

    success "namespace.c SuSFS mount definitions added via sed"
}

apply_susfs_patches() {
    log "Applying SUSFS patches"

    cp -R $SUSFS_PATCHES/fs/* ./fs
    cp -R $SUSFS_PATCHES/include/linux/* ./include/linux/

    if [ "$SUSFS_PATCH" = "gki-android14-6.1" ]; then
      cd $SUSFS_DIR
      patch -p1 --fuzz=3 < "$KERNEL_PATCHES/susfs/susfs_fs_namespace_fix.patch"
      cd $OLDPWD
    fi

    if ! patch -p1 --fuzz=3 < "$SUSFS_PATCHES/50_add_susfs_in_${SUSFS_PATCH}.patch"; then
        if [ "$KERNEL_KMI" = "android13-5.15" ]; then
            fix_namespace_susfs_mount
        fi
    fi

    SUSFS_VERSION=$(grep -E '^#define SUSFS_VERSION' ./include/linux/susfs.h | cut -d' ' -f3 | sed 's/"//g')
    echo "SUSFS_VERSION=$SUSFS_VERSION" >> $GITHUB_ENV
}

clone_susfs() {
    DEPTH=${1:-1}
    if [ ! -d "$SUSFS_DIR" ]; then
        git clone --depth=$DEPTH -q "$SUSFS_URL" -b "$SUSFS_BRANCH" "$SUSFS_DIR"
    fi
}
