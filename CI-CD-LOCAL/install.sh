#!/usr/bin/env bash
# 📷 Instalador de Screenshot Tool — Linux Mint (X11/Cinnamon)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Necesitás python3.  sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

echo "📦 Creando entorno virtual..."
python3 -m venv .venv 2>/dev/null || {
    echo "❌ Falta el módulo venv:  sudo apt install python3-venv"
    exit 1
}

echo "⬇️  Instalando dependencias (PyQt6, mss, pynput, python-xlib)..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "🚀 Activando autoarranque..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/screenshot-tool.desktop" <<EOF
[Desktop Entry]
Type=Application
Exec=$(pwd)/.venv/bin/python $(pwd)/screenshot_tray_linux.py
Hidden=false
NoDisplay=false
Name=Screenshot Tool
Comment=Capturas de pantalla rápidas (F10) con guardado y portapapeles
Categories=Utility;Graphics;
EOF

echo ""
echo "✅ ¡Instalado!"
echo "   • Arrancar ahora:      ./run.sh   (o reiniciá la sesión)"
echo "   • Atajo por defecto:   F10"
echo "   • Preferencias:        clic en el icono del tray"
