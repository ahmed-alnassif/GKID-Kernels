#!/usr/bin/env bash

declare -A ANDROID_RELEASE_FOR_KVER=(
  ["5.10"]="13"
  ["5.15"]="14"
  ["6.1"]="14"
  ["6.6"]="15"
  ["6.12"]="16"
)

declare -A GKI_AOSP_BRANCH=(
  ["5.10"]="android12-5.10"
  ["5.15"]="android13-5.15"
  ["6.6"]="android15-6.6"
  ["6.12"]="android16-6.12"
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

  if [ -z "$branch" ]; then
    error "No AOSP GKI branch mapped for KERNEL_VERSION='$ver' (see GKI_AOSP_BRANCH in functions.sh)"
    exit 1
  fi

  echo "https://android.googlesource.com/kernel/common|$branch"
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

apply_susfs_patches() {
    log "Applying SUSFS patches"
    
    cp -R $SUSFS_PATCHES/fs/* ./fs
    cp -R $SUSFS_PATCHES/include/linux/* ./include/linux/
    
    if [ "$SUSFS_PATCH" = "gki-android14-6.1" ]; then
      cd $SUSFS_DIR
      patch -p1 --fuzz=3 < "$KERNEL_PATCHES/susfs/susfs_fs_namespace_fix.patch"
      cd $OLDPWD
    fi
    
    patch -p1 --fuzz=3 < $SUSFS_PATCHES/50_add_susfs_in_${SUSFS_PATCH}.patch
    
    SUSFS_VERSION=$(grep -E '^#define SUSFS_VERSION' ./include/linux/susfs.h | cut -d' ' -f3 | sed 's/"//g')
    echo "SUSFS_VERSION=$SUSFS_VERSION" >> $GITHUB_ENV
}

clone_susfs() {
	DEPTH=${1:-1}
    if [ ! -d "$SUSFS_DIR" ]; then
        git clone --depth=$DEPTH -q "$SUSFS_URL" -b "$SUSFS_BRANCH" "$SUSFS_DIR"
    fi
}

generate_gh_changelog() {
    local repo="$1"
    local branch="$2"
    local count="${3:-5}"
    local output="$4"

    gh api "repos/${repo}/commits?sha=${branch}&per_page=${count}" \
        --jq '.[] | "- [" + .sha[0:7] + "](" + .html_url + ") " + (.commit.message | split("\n")[0])' \
        > "$output"
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
        info "Applying: $(basename "$patch")"

        if ! git apply --check "$patch" 2>/dev/null; then
            warning "Skipping: $(basename "$patch") - does not apply"
            ((failed++))
            continue
        fi

        if git apply "$patch" 2>/dev/null; then
            success "Applied: $(basename "$patch")"
        else
            error "Failed: $(basename "$patch")"
            ((failed++))
        fi
    done

    [[ $failed -eq 0 ]] && success "All patches applied successfully" || warning "Applied $((${#patches[@]} - failed))/${#patches[@]} patches, $failed failed"
    return $failed
}