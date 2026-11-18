#!/usr/bin/env bash
# terminal-default.sh — make aisha the shell new terminal windows open (or undo that).
#   packaging/terminal-default.sh ask     ask, if new windows don't open aisha yet (install.sh runs this)
#   packaging/terminal-default.sh report  one line: do new windows open aisha (./update.sh shows this)
#   packaging/terminal-default.sh set     set it now, no question
#   packaging/terminal-default.sh unset   back to your normal shell
#   packaging/terminal-default.sh status  what each terminal app opens
# Works on GNOME Terminal (also Linux Mint, Ubuntu), Konsole and Xfce Terminal. Logins, ssh and
# scripts keep using your login shell; only new windows of these apps change.
set -uo pipefail

ACTION="${1:-status}"
CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
ASKED="$CFG_DIR/aisha/.terminal-default-asked"   # left by older versions, which asked only once
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
# Xfce Terminal is one process for all its windows: a running one keeps its settings in memory
# and writes them back on exit, so changing its "custom command" setting from outside does not
# stick. A few lines in ~/.bashrc work in any terminal app instead (see "the bash way" below).
xfce_old_setting() {  # the custom-command setting an earlier version of this script made
    if command -v xfconf-query >/dev/null &&
            [ "$(xfconf-query -c xfce4-terminal -p /run-custom-command 2>/dev/null)" = true ] &&
            xfconf-query -c xfce4-terminal -p /custom-command 2>/dev/null | grep -q aisha; then return 0; fi
    [ -f "$XFCE_RC" ] && grep -qx 'RunCustomCommand=TRUE' "$XFCE_RC" && grep -q '^CustomCommand=.*aisha' "$XFCE_RC"
}
xfce_is_set() { bashrc_is_set; }
xfce_set()    { bashrc_set; }
xfce_unset() {
    if xfce_old_setting; then
        command -v xfconf-query >/dev/null && xfconf-query -c xfce4-terminal -p /run-custom-command -s false 2>/dev/null
        [ -f "$XFCE_RC" ] && sed -i 's/^RunCustomCommand=TRUE$/RunCustomCommand=FALSE/' "$XFCE_RC"
    fi
    bashrc_unset
}

# --- the bash way: any terminal app ---------------------------------------------------
# New interactive bash in a graphical session runs `exec aisha`. Not inside aisha itself
# (it sets $AISHA for what it runs), not over ssh, not on a text console, not in scripts.
BASHRC="$HOME/.bashrc"
BEGIN_MARK="# >>> aisha: open ai\$ha in terminal windows (undo: packaging/terminal-default.sh unset) >>>"
END_MARK="# <<< aisha <<<"
bashrc_is_set() { [ -f "$BASHRC" ] && grep -qF "$BEGIN_MARK" "$BASHRC"; }
bashrc_set() {
    bashrc_is_set && return 0
    {
        printf '\n%s\n' "$BEGIN_MARK"
        printf '%s\n' 'if [[ $- == *i* && -z "${AISHA:-}" && -z "${AISHA_SKIP:-}" && -z "${SSH_CONNECTION:-}" &&'
        printf '%s\n' '      -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v aisha >/dev/null; then'
        printf '%s\n' '    exec aisha'
        printf '%s\n' 'fi'
        printf '%s\n' "$END_MARK"
    } >> "$BASHRC"
}
bashrc_unset() {
    bashrc_is_set || return 0
    local tmp; tmp="$(mktemp)"
    awk -v b="$BEGIN_MARK" -v e="$END_MARK" '$0 == b {skip = 1; next} skip && $0 == e {skip = 0; next} !skip' \
        "$BASHRC" > "$tmp" && cat "$tmp" > "$BASHRC"
    rm -f "$tmp"
}

# ------------------------------------------------------------------------------------
APPS=()
gnome_ok   && APPS+=(gnome)
konsole_ok && APPS+=(konsole)
xfce_ok    && APPS+=(xfce)
[ ${#APPS[@]} -eq 0 ] && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && APPS+=(bashrc)   # some other terminal app
label() { case "$1" in gnome) echo "GNOME Terminal" ;; konsole) echo Konsole ;; xfce) echo "Xfce Terminal" ;;
                       bashrc) echo "your terminal (through ~/.bashrc)" ;; esac; }

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
    set|ask|report)
        [ -n "$AISHA" ] || { yellow "aisha is not installed yet"; exit 1; }
        if [ ${#APPS[@]} -eq 0 ]; then
            if [ "$ACTION" = report ]; then echo "Terminal: no graphical session here; to open aisha in your terminal app, see: packaging/terminal-default.sh set"
            else manual; fi
            exit 0
        fi
        todo=()
        for a in "${APPS[@]}"; do "${a}_is_set" || todo+=("$a"); done
        if [ ${#todo[@]} -eq 0 ]; then
            green "Terminal: new windows open aisha. (Back to bash: packaging/terminal-default.sh unset)"
            exit 0
        fi
        names="$(for a in "${todo[@]}"; do label "$a"; done | paste -sd, - | sed 's/,/, /g')"
        if [ "$ACTION" = report ] || { [ "$ACTION" = ask ] && [ ! -t 0 ]; }; then
            echo "Terminal: new windows ($names) open bash. To open aisha there: packaging/terminal-default.sh set"
            exit 0
        fi
        if [ "$ACTION" = ask ]; then
            read -r -p "Open aisha in new terminal windows ($names)? Logins, ssh and scripts keep bash. [y/N] " yn
            case "${yn,,}" in
                y|yes) ;;
                *) dim "  kept your terminal as it is (later: packaging/terminal-default.sh set)"; exit 0 ;;
            esac
        fi
        for a in "${todo[@]}"; do
            if "${a}_set"; then green "  $(label "$a"): new windows open aisha"; else yellow "  $(label "$a"): could not change it"; fi
        done
        if bashrc_is_set; then
            dim "  (added to ~/.bashrc; for plain bash in one window: AISHA_SKIP=1 bash, or type bash inside aisha)"
        fi
        dim "  open a new terminal window to see it. Undo with: packaging/terminal-default.sh unset" ;;
    unset)
        for a in "${APPS[@]}"; do
            if "${a}_is_set"; then "${a}_unset" && green "  $(label "$a"): back to your login shell"; fi
        done
        rm -f "$ASKED"
        green "new terminal windows open your login shell again" ;;
    *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
