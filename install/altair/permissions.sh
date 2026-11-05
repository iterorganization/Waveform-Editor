# Functions to share files with colleagues, sourced by the other scripts. Colleagues
# are in the same group "users" as the owner, so the group bits apply to them, and
# both the group and the other bits are set and checked.

# Make a path readable by colleagues, with the directories above it that are ours
# traversable (only traversable: they cannot list them)
share_path() {
    chmod -R go+rX "$1"
    local d=$1
    while [ "$d" != / ]; do
        d=$(dirname "$d")
        if [ -O "$d" ]; then
            chmod go+x "$d"
        fi
    done
}

# Print what keeps colleagues from reading a path; return 1 if anything does
check_shared() {
    local p=$1 status=0 d=$1 mode
    while [ "$d" != / ]; do
        d=$(dirname "$d")
        mode=$(stat -c %a "$d")
        if (( (8#$mode & 8#011) != 8#011 )); then
            echo "  not traversable by colleagues: $d" >&2
            status=1
        fi
    done
    local blocked
    blocked=$(find "$p" \( -type d ! -perm -055 \) -o \( ! -type d ! -perm -044 \) 2> /dev/null | head -5)
    if [ -n "$blocked" ]; then
        echo "  not readable by colleagues (first ones): $blocked" >&2
        status=1
    fi
    return $status
}
