#!/usr/bin/env bash
# terminal-default.sh — make aisha the shell new terminal windows open (or undo that).
#   packaging/terminal-default.sh ask     ask once (install.sh runs this; silent if already set or declined)
#   packaging/terminal-default.sh set     set it now, no question
#   packaging/terminal-default.sh unset   back to your normal shell
#   packaging/terminal-default.sh status  what each terminal app opens
# Works on GNOME Terminal (also Linux Mint, Ubuntu), Konsole and Xfce Terminal. Logins, ssh and
# scripts keep using your login shell; only new windows of these apps change.
set -uo pipefail

ACTION="${1:-status}"
CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
ASKED="$CFG_DIR/aisha/.terminal-default-asked"
AISHA="$(command -v aisha || true)"
KONSOLE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/konsole"

green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    yellow "run this as yourself, not with sudo: terminal settings belong to your user"
    exit 1
fi

# --- GNOME Terminal ---------------------------------------------------------------
gnome_ok() {
    command -v gnome-terminal >/dev/null && command -v gsettings >/dev/null &&
        gsettings list-schemas 2>/dev/null | grep -qx org.gnome.Terminal.ProfilesList
}
gnome_path() {
    local p
    p="$(gsettings get org.gnome.Terminal.ProfilesList default 2>/dev/null | tr -d "'")"
    [ -n "$p" ] && echo "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:$p/"
}
gnome_is_set() {
    local s; s="$(gnome_path)" || return 1
    [ "$(gsettings get "$s" use-custom-command 2>/dev/null)" = true ] &&
        gsettings get "$s" custom-command 2>/dev/null | grep -q aisha
}
gnome_set() {
    local s; s="$(gnome_path)" || return 1
    gsettings set "$s" custom-command "$AISHA" && gsettings set "$s" use-custom-command true
}
gnome_unset() {
    local s; s="$(gnome_path)" || return 0
    gnome_is_set && gsettings set "$s" use-custom-command false
}

# --- Konsole ------------------------------------------------------------------------
kwrite() { command -v kwriteconfig6 >/dev/null && echo kwriteconfig6 || { command -v kwriteconfig5 >/dev/null && echo kwriteconfig5; }; }
kread()  { command -v kreadconfig6 >/dev/null && echo kreadconfig6 || { command -v kreadconfig5 >/dev/null && echo kreadconfig5; }; }
konsole_ok() { command -v konsole >/dev/null && [ -n "$(kwrite)" ]; }
konsole_is_set() {
    [ -n "$(kread)" ] && [ "$($(kread) --file konsolerc --group 'Desktop Entry' --key DefaultProfile 2>/dev/null)" = aisha.profile ]
}
konsole_set() {
    mkdir -p "$KONSOLE_DIR"
    printf '[General]\nCommand=%s\nName=aisha\nParent=FALLBACK/\n' "$AISHA" > "$KONSOLE_DIR/aisha.profile"
    $(kwrite) --file konsolerc --group 'Desktop Entry' --key DefaultProfile aisha.profile
}
konsole_unset() {
    konsole_is_set && $(kwrite) --file konsolerc --group 'Desktop Entry' --key DefaultProfile --delete
    rm -f "$KONSOLE_DIR/aisha.profile"
}

# --- Xfce Terminal --------------------------------------------------------------------
XFCE_RC="$CFG_DIR/xfce4/terminal/terminalrc"
xfce_ok() { command -v xfce4-terminal >/dev/null; }
xfce_is_set() {
    if command -v xfconf-query >/dev/null && xfconf-query -c xfce4-terminal -p /run-custom-command >/dev/null 2>&1; then
        [ "$(xfconf-query -c xfce4-terminal -p /run-custom-command 2>/dev/null)" = true ] &&
            xfconf-query -c xfce4-terminal -p /custom-command 2>/dev/null | grep -q aisha && return 0
    fi
    [ -f "$XFCE_RC" ] && grep -qx 'RunCustomCommand=TRUE' "$XFCE_RC" && grep -q '^CustomCommand=.*aisha' "$XFCE_RC"
}
xfce_rc_put() {  # key value
    mkdir -p "$(dirname "$XFCE_RC")"
    [ -f "$XFCE_RC" ] || printf '[Configuration]\n' > "$XFCE_RC"
    if grep -q "^$1=" "$XFCE_RC"; then sed -i "s|^$1=.*|$1=$2|" "$XFCE_RC"; else printf '%s=%s\n' "$1" "$2" >> "$XFCE_RC"; fi
}
xfce_set() {
    if command -v xfconf-query >/dev/null; then
        xfconf-query -c xfce4-terminal -p /run-custom-command -n -t bool -s true 2>/dev/null
        xfconf-query -c xfce4-terminal -p /custom-command -n -t string -s "$AISHA" 2>/dev/null
    fi
    xfce_rc_put RunCustomCommand TRUE        # older Xfce Terminal reads this file
    xfce_rc_put CustomCommand "$AISHA"
}
xfce_unset() {
    xfce_is_set || return 0
    command -v xfconf-query >/dev/null && xfconf-query -c xfce4-terminal -p /run-custom-command -s false 2>/dev/null
    [ -f "$XFCE_RC" ] && xfce_rc_put RunCustomCommand FALSE
}

# ------------------------------------------------------------------------------------
APPS=()
gnome_ok   && APPS+=(gnome)
konsole_ok && APPS+=(konsole)
xfce_ok    && APPS+=(xfce)
label() { case "$1" in gnome) echo "GNOME Terminal" ;; konsole) echo Konsole ;; xfce) echo "Xfce Terminal" ;; esac; }

manual() {
    dim "  No supported terminal app found here. In your terminal's preferences, set the profile's"
    dim "  command (\"run a custom command instead of my shell\") to: ${AISHA:-/usr/bin/aisha}"
}

case "$ACTION" in
    status)
        [ ${#APPS[@]} -eq 0 ] && { manual; exit 0; }
        for a in "${APPS[@]}"; do
            if "${a}_is_set"; then echo "$(label "$a"): opens aisha"; else echo "$(label "$a"): opens your login shell"; fi
        done ;;
    set|ask)
        [ -n "$AISHA" ] || { yellow "aisha is not installed yet"; exit 1; }
        if [ ${#APPS[@]} -eq 0 ]; then
            [ "$ACTION" = set ] && manual
            exit 0
        fi
        todo=()
        for a in "${APPS[@]}"; do "${a}_is_set" || todo+=("$a"); done
        [ ${#todo[@]} -eq 0 ] && { [ "$ACTION" = set ] && green "new terminal windows already open aisha"; exit 0; }
        if [ "$ACTION" = ask ]; then
            [ -t 0 ] && [ ! -e "$ASKED" ] || exit 0            # only once, and only when someone is there to answer
            names="$(for a in "${todo[@]}"; do label "$a"; done | paste -sd, - | sed 's/,/, /g')"
            echo
            read -r -p "Open aisha in new terminal windows ($names)? Logins and scripts keep bash. [y/N] " yn
            mkdir -p "$(dirname "$ASKED")" && : > "$ASKED"
            case "${yn,,}" in y|yes) ;; *) dim "  kept your terminal as it is (later: packaging/terminal-default.sh set)"; exit 0 ;; esac
        fi
        for a in "${todo[@]}"; do
            if "${a}_set"; then green "  $(label "$a"): new windows open aisha"; else yellow "  $(label "$a"): could not change it"; fi
        done
        dim "  undo with: packaging/terminal-default.sh unset" ;;
    unset)
        for a in "${APPS[@]}"; do
            if "${a}_is_set"; then "${a}_unset" && green "  $(label "$a"): back to your login shell"; fi
        done
        rm -f "$ASKED" ;;
    *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
