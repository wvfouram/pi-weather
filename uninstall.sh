#!/bin/bash
# Removes Weather.
SRC="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" = "0" ]; then
  echo "Run this as your normal user (not with sudo)."
  exit 1
fi

sudo rm -rf /opt/pi-weather /usr/local/bin/pi-weather /usr/share/applications/pi-weather.desktop \
  /usr/share/icons/hicolor/scalable/apps/pi-weather.svg
sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true
echo "Weather removed. Your settings are still in ~/.config/pi-weather (delete that folder to remove them)."
