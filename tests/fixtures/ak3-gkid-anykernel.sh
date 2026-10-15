### AnyKernel3 Ramdisk Mod Script
## osm0sis @ xda-developers

properties() { '
kernel.string=GKID by Ahmed Al-Nassif (ahmed-alnassif)
do.devicecheck=0
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=
device.name2=
device.name3=
device.name4=
device.name5=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; }


block=boot
is_slot_device=auto
ramdisk_compression=auto
patch_vbmeta_flag=auto
no_magisk_check=1

. tools/ak3-core.sh

kernel_supported=false
supported_kernel="6.1"
kernel_version=$(uname -r | awk -F '.' '{print $1"."$2}')
[[ "$kernel_version" == "$supported_kernel" ]] && kernel_supported=true

ui_print " " "  -> GKID Supported: $kernel_supported"
ui_print "Thank you for using GKID ❤️"
ui_print "Please join our community if you need help with anything:"
ui_print "Telegram: https://t.me/ahmed_alnassif_tg"
$kernel_supported || abort "  -> Unsupported device, abort."

split_boot
if [ -f "split_img/ramdisk.cpio" ]; then
    unpack_ramdisk
    write_boot
else
    flash_boot
fi
