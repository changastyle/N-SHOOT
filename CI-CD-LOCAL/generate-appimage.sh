#!/usr/bin/env bash
# ============================================================================
#  GENERATE-APPIMAGE.SH
#  Build completo de Screenshot Tool (Linux):
#    PyInstaller (binario único) + AppDir + appimagetool ->
#    OUT/screenshot-tool-<VERSION>-<ARCH>.AppImage
#
#  Reemplaza a GENERATE-EXE.BAT: los .bat son de Windows y los AppImage
#  solo se construyen en Linux (y esta app es Python/PyQt6, no Java/Maven).
#
#  VERSION:
#    Uso: ./generate-appimage.sh [version]   (por defecto 1.0.0)
#    La version solo nombra el artefacto final; el proyecto no tiene
#    pom.xml ni VERSION file donde persistirla.
# ============================================================================
set -euo pipefail

# El .sh esta en CI-CD-LOCAL/ pero los archivos del proyecto estan arriba:
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

APP="screenshot-tool"
BUILD="CI-CD-LOCAL/build"
TOOLS="CI-CD-LOCAL/tools"
APPDIR="$BUILD/$APP.AppDir"
OUT_DIR="OUT"
ARCH="$(uname -m)"

echo
echo "============================================================"
echo "  Build Screenshot Tool  ->  $OUT_DIR/"
echo "============================================================"
echo

# ----------------------------------------------------------------------------
# 1 - VERIFICAR PYTHON3 Y WGET/CURL:
# ----------------------------------------------------------------------------
echo "[1/6] Verificando python3 y herramientas de descarga..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 no encontrado (sudo apt install python3 python3-venv)."
    exit 1
fi
if ! command -v wget >/dev/null 2>&1 && ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: se necesita wget o curl para descargar appimagetool."
    exit 1
fi
echo "      python3 $(python3 -V 2>&1 | awk '{print $2}') OK"

# python3-venv: sin ensurepip el 'python3 -m venv' del paso 4 falla.
if ! python3 -c "import ensurepip" 2>/dev/null; then
    echo "      AVISO: falta python3-venv (ensurepip no disponible)."
    if [ -t 0 ] && command -v apt-get >/dev/null 2>&1; then
        echo "      Instalando python3-venv (apt pedira sudo)..."
        sudo apt-get install -y python3-venv || {
            echo "ERROR: instala manualmente: sudo apt install python3-venv"
            exit 1
        }
    else
        echo "ERROR: falta python3-venv (sudo apt install python3-venv)."
        exit 1
    fi
fi

# ----------------------------------------------------------------------------
# 2 - VERSION Y FECHA DEL BUILD:
# ----------------------------------------------------------------------------
echo
echo "[2/6] Version y fecha del build..."
VERSION="${1:-1.0.0}"
FECHA="$(date +%F)"
echo "      Version: $VERSION  -  Fecha: $FECHA  -  Arch: $ARCH"

case "$ARCH" in
    x86_64|aarch64) ;;
    *) echo "ERROR: arquitectura no soportada por appimagetool: $ARCH"; exit 1 ;;
esac

# ----------------------------------------------------------------------------
# 3 - CERRAR INSTANCIAS QUE BLOQUEEN EL BUILD Y LIMPIAR BUILD ANTERIOR:
# ----------------------------------------------------------------------------
echo
echo "[3/6] Cerrando instancias previas y limpiando..."

# Solo matar instancias reales de la app (python .../screenshot_tray_linux.py);
# un pkill -f generico tambien matchearia este mismo script/pyinstaller.
pkill -f "python.*screenshot_(tool|tray_linux)\.py" 2>/dev/null && sleep 1 || true
pkill -f "$APP\.AppDir/usr/bin/$APP" 2>/dev/null || true

rm -rf "$APPDIR" "$BUILD/dist" "$BUILD/work"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$TOOLS" "$OUT_DIR"

echo "      Limpieza completada."

# ----------------------------------------------------------------------------
# 4 - ENTORNO DE BUILD + COMPILAR CON PYINSTALLER (binario único):
# ----------------------------------------------------------------------------
echo
echo "[4/6] Compilando con PyInstaller..."

if [ ! -x ".venv/bin/python" ]; then
    echo "      Creando .venv..."
    python3 -m venv .venv || { echo "ERROR: falta python3-venv (sudo apt install python3-venv)"; exit 1; }
fi
.venv/bin/pip install -q --upgrade pip
# pynput va con --no-deps: en Linux declara evdev, que no tiene wheel y
# compilarlo requiere python3-dev. La app usa pynput solo como fallback
# del backend Xlib, asi que evdev es prescindible.
.venv/bin/pip install -q $(grep -v 'pynput' requirements.txt | tr '\n' ' ')
.venv/bin/pip install -q --no-deps pynput
.venv/bin/pip install -q pyinstaller cairosvg   # deps solo del build

.venv/bin/pyinstaller --noconfirm --clean --onefile --windowed \
    --name "$APP" \
    --hidden-import=Xlib --hidden-import=pynput \
    --distpath "$BUILD/dist" --workpath "$BUILD/work" --specpath "$BUILD" \
    screenshot_tray_linux.py

echo
echo "      Compilacion exitosa!"

# ----------------------------------------------------------------------------
# 5 - ARMAR AppDir: binario + .desktop + icono + libxcb-cursor + AppRun
#     (equivalente a la carpeta OUT\ del .bat, pero en formato AppImage):
# ----------------------------------------------------------------------------
echo
echo "[5/6] Armando AppDir..."

cp "$BUILD/dist/$APP" "$APPDIR/usr/bin/$APP"

# libxcb-cursor: el plugin xcb de Qt 6.5+ la carga dinamicamente; la bundeamos
# para que el AppImage funcione en distros que no la traen instalada.
# La buscamos en ldconfig y en ~/.local/lib/screenshot-tool (donde la propia
# app la instala en este equipo).
XCB_CURSOR="$(ldconfig -p 2>/dev/null | awk '/libxcb-cursor\.so\.0/{print $NF; exit}')"
if [ -z "$XCB_CURSOR" ] && [ -f "$HOME/.local/lib/screenshot-tool/libxcb-cursor.so.0" ]; then
    XCB_CURSOR="$HOME/.local/lib/screenshot-tool/libxcb-cursor.so.0"
fi
# Ultimo recurso: bajar el .deb con 'apt download' (no requiere root) y
# extraer el .so, asi el AppImage queda autocontenido aunque el host de
# build no tenga el paquete instalado.
if [ -z "$XCB_CURSOR" ] && command -v apt >/dev/null 2>&1; then
    echo "      libxcb-cursor no instalada; extrayendo .deb (sin sudo)..."
    DEBDIR="$BUILD/debs"
    rm -rf "$DEBDIR" && mkdir -p "$DEBDIR"
    if (cd "$DEBDIR" && apt download libxcb-cursor0 >/dev/null 2>&1); then
        DEB="$(find "$DEBDIR" -maxdepth 1 -name 'libxcb-cursor0_*.deb' | head -1)"
        dpkg-deb -x "$DEB" "$DEBDIR/extract" 2>/dev/null || true
        XCB_CURSOR="$(find "$DEBDIR/extract" -name 'libxcb-cursor.so.0*' | head -1)"
    fi
fi
if [ -n "$XCB_CURSOR" ]; then
    cp -L "$XCB_CURSOR" "$APPDIR/usr/lib/libxcb-cursor.so.0"
else
    echo "      AVISO: libxcb-cursor.so.0 no encontrada; podria requerirse en el host"
    echo "             (sudo apt install libxcb-cursor0)."
fi

# Icono: CI-CD-LOCAL/ICONS/icon.svg -> PNG 256x256 (cairosvg en el venv de build).
.venv/bin/python - <<PYEOF
import cairosvg
cairosvg.svg2png(url="CI-CD-LOCAL/ICONS/icon.svg", write_to="$APPDIR/$APP.png",
                 output_width=256, output_height=256)
PYEOF

# Desktop entry (Icon= debe coincidir con el nombre del PNG):
cat > "$APPDIR/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Screenshot Tool
Comment=Capturas de pantalla rapidas (F10) con guardado y portapapeles
Exec=$APP
Icon=$APP
Categories=Utility;Graphics;
Terminal=false
EOF

# AppRun: LD_LIBRARY_PATH apunta a las libs bundeadas (libxcb-cursor).
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$HERE/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/usr/bin/screenshot-tool" "$@"
EOF
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/$APP"

echo "      AppDir: $APPDIR"

# ----------------------------------------------------------------------------
# 6 - APPIMAGETOOL + EMPAQUETAR + VERIFICAR:
# ----------------------------------------------------------------------------
echo
echo "[6/6] Empaquetando AppImage..."

AIT="$TOOLS/appimagetool-$ARCH.AppImage"
if [ ! -x "$AIT" ]; then
    echo "      Descargando appimagetool..."
    URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$ARCH.AppImage"
    if command -v wget >/dev/null 2>&1; then
        wget -q "$URL" -O "$AIT" || { echo "ERROR: no se pudo descargar appimagetool."; exit 1; }
    else
        curl -fL -s "$URL" -o "$AIT" || { echo "ERROR: no se pudo descargar appimagetool."; exit 1; }
    fi
    chmod +x "$AIT"
fi

APPIMAGE="$ROOT/$OUT_DIR/$APP-$VERSION-$ARCH.AppImage"
# --appimage-extract-and-run evita la dependencia de FUSE en el host de build.
ARCH="$ARCH" "$AIT" --appimage-extract-and-run "$APPDIR" "$APPIMAGE" >/dev/null
chmod +x "$APPIMAGE"

if [ ! -f "$APPIMAGE" ]; then
    echo
    echo "============================================"
    echo "  ERROR: no se genero el AppImage"
    echo "============================================"
    exit 1
fi

echo
echo "============================================================"
echo "  BUILD COMPLETADO - $OUT_DIR/"
echo "============================================================"
echo
echo "  Version:  $VERSION"
echo "  Fecha:    $FECHA"
echo "  Arch:     $ARCH"
echo
echo "  Para ejecutar:"
echo "    $OUT_DIR/$APP-$VERSION-$ARCH.AppImage"
echo
echo "  IMPORTANTE: el AppImage es autocontenido; en distros sin FUSE 2"
echo "  ejecutalo con: $OUT_DIR/$APP-$VERSION-$ARCH.AppImage --appimage-extract-and-run"
echo
