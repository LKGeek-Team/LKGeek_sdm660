#!/system/bin/sh
# Compile only interactive system apps that have not reached the speed filter.
# The ART command is idempotent and runs at background priority without -f.
set -eu
mode=${1:-apply}
case "$mode" in apply|status) ;; *) exit 2 ;; esac
for package in com.android.launcher com.android.settings; do
    if ! pm path "$package" >/dev/null 2>&1; then continue; fi
    state=$(pm art dump "$package")
    if [ "$mode" = status ]; then
        printf '%s\n' "$state"
    else
        primary=$(printf '%s\n' "$state" | awk '/\[status=/{print; exit}')
        if ! printf '%s\n' "$primary" | grep -q '\[status=speed\]'; then
            cmd package compile -m speed -p PRIORITY_BACKGROUND --primary-dex "$package"
        fi
    fi
done
