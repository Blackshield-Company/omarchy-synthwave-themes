#!/usr/bin/env bash
# Omarchy synthwave theme installer. Same layout and flow as the Blackshield installer.
# Usage:
#   ./install.sh list
#   ./install.sh theme <name> [--res WxH]   install into ~/.config/omarchy/themes/<name> and apply
#   ./install.sh extras <name>              copy legacy/standalone configs to ~/.config/omarchy-synthwave/<name>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
die() { echo "error: $*" >&2; exit 1; }

themes() { find "$ROOT/themes" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort; }

check_name() {
  [[ -n "${1:-}" ]] || die "missing theme name (try: ./install.sh list)"
  [[ "$1" =~ ^[a-z0-9-]+$ && -d "$ROOT/themes/$1" ]] || die "unknown theme: $1"
}

install_theme() {
  local name="$1" res="${2:-}"
  local dest="${OMARCHY_THEMES_DIR:-$HOME/.config/omarchy/themes}/$name"
  mkdir -p "$dest"
  cp -a "$ROOT/themes/$name/." "$dest/"
  if [[ -n "$res" ]]; then
    [[ -d "$ROOT/wallpapers/$name/$res" ]] || die "no wallpapers at $res (have: $(find "$ROOT/wallpapers/$name" -mindepth 1 -maxdepth 1 -printf '%f '))"
    rm -rf "$dest/backgrounds"
    mkdir -p "$dest/backgrounds"
    cp -a "$ROOT/wallpapers/$name/$res/." "$dest/backgrounds/"
  fi
  echo "theme -> $dest"
  if command -v omarchy-theme-set >/dev/null && [[ -z "${OMARCHY_THEMES_DIR:-}" ]]; then
    omarchy-theme-set "$name"
  else
    echo "omarchy-theme-set not run; apply with: omarchy-theme-set $name"
  fi
}

install_extras() {
  local dest="${SYNTHWAVE_EXTRAS_DIR:-$HOME/.config/omarchy-synthwave}/$1"
  mkdir -p "$dest"
  cp -a "$ROOT/extras/$1/." "$dest/"
  echo "extras -> $dest (include or copy them into each app's config yourself)"
}

cmd="${1:-}"
case "$cmd" in
  list) themes ;;
  theme)
    name="${2:-}"; check_name "$name"; res=""
    if [[ "${3:-}" == "--res" ]]; then res="${4:-}"; [[ -n "$res" ]] || die "--res needs WxH"; fi
    install_theme "$name" "$res" ;;
  extras) check_name "${2:-}"; install_extras "$2" ;;
  *) die "usage: ./install.sh list | theme <name> [--res WxH] | extras <name>" ;;
esac
