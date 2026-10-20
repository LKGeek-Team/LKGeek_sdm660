#!/system/bin/sh
# Synchronize the port's launcher properties with the actual default display.
set -eu

density=$(wm density | awk '/Physical density:/ {d=$3} /Override density:/ {d=$3} END {print d}')
size=$(wm size | awk '/Physical size:/ {s=$3} /Override size:/ {s=$3} END {print s}')
case "$density" in ''|*[!0-9]*) exit 1 ;; esac
case "$size" in ''|*[!0-9x]*) exit 1 ;; esac
if [ "$density" -lt 160 ] || [ "$density" -gt 960 ]; then exit 1; fi
width=${size%x*}
height=${size#*x}
[ "$width" != "$size" ] || exit 1
case "$width:$height" in *x*|:*|*:) exit 1 ;; esac
previous=$(getprop persist.sys.display.density)
setprop persist.sys.display.density "$density"
setprop persist.sys.miui_resolution "$width,$height,$density"
if [ "$previous" != "$density" ]; then
    # Invalidate the launcher's cached resolution profile, retaining its data.
    am force-stop com.android.launcher
fi
