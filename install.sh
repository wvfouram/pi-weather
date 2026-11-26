#!/bin/bash
# Installer for Weather (Windows 11 style) on Raspberry Pi
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" = "0" ]; then
  echo "Run this as your normal user (not with sudo). It will ask for sudo when needed."
  exit 1
fi

echo "==> Installing packages"
sudo apt-get update || echo "   (apt update had errors, continuing)"
if ! sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 xdg-utils; then
  for p in python3-gi python3-gi-cairo gir1.2-gtk-3.0 xdg-utils; do
    sudo apt-get install -y "$p" || echo "   (could not install $p)"
  done
fi
sudo apt-get install -y fonts-open-sans || echo "   (Open Sans font not available, using system font)"
for p in ; do
  sudo apt-get install -y "$p" || echo "   ($p not available, skipping)"
done

echo "==> Installing app"
sudo install -d /opt/pi-weather
sudo install -m 644 "$SRC/pi_weather.py" /opt/pi-weather/pi_weather.py
printf '#!/bin/sh\nexec /usr/bin/python3 /opt/pi-weather/pi_weather.py "$@"\n' | sudo tee /usr/local/bin/pi-weather >/dev/null
sudo chmod 755 /usr/local/bin/pi-weather

echo "==> Adding menu entry and icon"
sudo install -D -m 644 "$SRC/pi-weather.svg" /usr/share/icons/hicolor/scalable/apps/pi-weather.svg
sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
sudo tee /usr/share/applications/pi-weather.desktop >/dev/null <<'DESK'
[Desktop Entry]
Type=Application
Name=Weather
GenericName=Weather
Comment=Forecasts, hourly and 10-day weather
Exec=pi-weather 
Icon=pi-weather
Terminal=false
Categories=Utility;GTK;
StartupWMClass=pi-weather
StartupNotify=true
DESK
sudo update-desktop-database -q /usr/share/applications 2>/dev/null || true

echo
echo "Done. Open Weather from the menu or run: pi-weather"
