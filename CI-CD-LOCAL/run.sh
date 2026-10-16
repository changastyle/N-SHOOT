#!/usr/bin/env bash
# 📷 Lanza Screenshot Tool. Si no está instalado, se auto-instala primero.
cd "$(dirname "$0")/.."

# Primera vez: prepara el entorno automáticamente
if [ ! -x ".venv/bin/python" ]; then
    echo "🔧 Primera vez: preparando entorno virtual..."
    python3 -m venv .venv || { echo "❌ Falta python3-venv: sudo apt install python3-venv"; exit 1; }
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q -r requirements.txt
    echo "✅ Entorno listo."
fi

mkdir -p "$HOME/.cache"
nohup .venv/bin/python screenshot_tray_linux.py > "$HOME/.cache/screenshot-tool.log" 2>&1 &
echo "📷 Screenshot Tool corriendo (PID $!)  ·  log: ~/.cache/screenshot-tool.log"
