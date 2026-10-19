# ============================================================================
#  GENERATE-EXE.PS1
#  Build completo de Screenshot Tool (Windows):
#    PyInstaller (exe único) + icono .ico ->
#    OUT/screenshot-tool-<VERSION>-win_amd64.exe
#
#  Equivalente Windows de generate-appimage.sh (misma convención de
#  nombre para que release.yml extraiga la version igual).
#
#  NOTA Smart App Control: si el exe final queda bloqueado por la política
#  del equipo (como paso con las DLLs de PyQt6), solo lo puede liberar el
#  usuario/admin — el build en sí no falla.
#
#  Uso:
#    powershell -ExecutionPolicy Bypass -File generate-exe.ps1 [version]
#    (por defecto 1.0.0; solo nombra el artefacto, no hay VERSION file)
# ============================================================================
$ErrorActionPreference = "Stop"

# El .ps1 esta en CI-CD-LOCAL/ pero los archivos del proyecto estan arriba:
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = Split-Path -Parent $SCRIPT_DIR
Set-Location $ROOT

$APP = "screenshot-tool"
$BUILD = "CI-CD-LOCAL/build"
$OUT_DIR = "OUT"

Write-Host ""
Write-Host "============================================================"
Write-Host "  Build Screenshot Tool (Windows)  ->  $OUT_DIR/"
Write-Host "============================================================"
Write-Host ""

# ----------------------------------------------------------------------------
# 1 - VERIFICAR PYTHON + ARCH:
# ----------------------------------------------------------------------------
Write-Host "[1/6] Verificando python..."
$PY = "$ROOT\.venv\Scripts\python.exe"
if (-not (Test-Path $PY)) {
    $PY = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PY) { Write-Host "ERROR: python no encontrado."; exit 1 }
}
Write-Host "      $(& $PY -V) OK"

$ARCH = ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture).ToString().ToLower()
$TAG = switch ($ARCH) { "x64" { "win_amd64" } "arm64" { "win_arm64" } default { "win_$ARCH" } }

# ----------------------------------------------------------------------------
# 2 - VERSION Y FECHA DEL BUILD:
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/6] Version y fecha del build..."
$VERSION = if ($args.Count -gt 0) { $args[0] } else { "1.0.0" }
$FECHA = Get-Date -Format "yyyy-MM-dd"
Write-Host "      Version: $VERSION  -  Fecha: $FECHA  -  Tag: $TAG"

# ----------------------------------------------------------------------------
# 3 - CERRAR INSTANCIAS QUE BLOQUEEN EL BUILD Y LIMPIAR BUILD ANTERIOR:
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Cerrando instancias previas y limpiando..."

# Solo instancias reales de la app (python .../N-SHOOT.py o el exe compilado).
Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'N-SHOOT\.py' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-Process $APP -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

Remove-Item -Recurse -Force "$BUILD/dist", "$BUILD/work" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $BUILD, $OUT_DIR | Out-Null
Write-Host "      Limpieza completada."

# ----------------------------------------------------------------------------
# 4 - ENTORNO DE BUILD + COMPILAR CON PYINSTALLER (exe único):
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/6] Compilando con PyInstaller..."

if (-not (Test-Path "$ROOT\.venv\Scripts\python.exe")) {
    Write-Host "      Creando .venv..."
    & $PY -m venv .venv
    $PY = "$ROOT\.venv\Scripts\python.exe"
}
& $PY -m pip install -q --upgrade pip
# requirements.txt ya filtra por plataforma: en win32 instala PySide6
# (PyQt6 puede quedar bloqueado por Smart App Control) + mss + pynput.
& $PY -m pip install -q -r requirements.txt
& $PY -m pip install -q pyinstaller pillow   # deps solo del build

# Icono: CI-CD-LOCAL/ICONS/icon.svg -> PNG 256 (Qt del venv) -> icon.ico (Pillow).
$ICO = "$BUILD/icon.ico"
try {
    @"
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, ".")
from UTILS.qt_compat.QtWidgets import QApplication
from UTILS.qt_compat.QtGui import QImage, QPainter
from UTILS.qt_compat.QtSvg import QSvgRenderer
from UTILS.qt_compat.QtCore import Qt
QApplication([])
img = QImage(256, 256, QImage.Format.Format_ARGB32)
img.fill(Qt.GlobalColor.transparent)
r = QSvgRenderer("CI-CD-LOCAL/ICONS/icon.svg")
p = QPainter(img); r.render(p); p.end()
img.save(r"$BUILD/icon.png")
from PIL import Image
Image.open(r"$BUILD/icon.png").save(r"$BUILD/icon.ico",
    sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print("icono generado")
"@ | & $PY -
    if ($LASTEXITCODE -ne 0) { throw "icon render fallo" }
} catch {
    Write-Host "      AVISO: no se pudo generar icon.ico; el exe saldra sin icono."
    $ICO = $null
}

$piArgs = @(
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", $APP,
    "--hidden-import=pynput",
    "--distpath", "$BUILD/dist",
    "--workpath", "$BUILD/work",
    "--specpath", "$BUILD"
)
if ($ICO) { $piArgs += @("--icon", $ICO) }
$piArgs += "N-SHOOT.py"

& $PY -m PyInstaller @piArgs
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: PyInstaller fallo."; exit 1 }
Write-Host ""
Write-Host "      Compilacion exitosa!"

# ----------------------------------------------------------------------------
# 5 - COPIAR A OUT/ CON EL NOMBRE DE RELEASE:
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Empaquetando..."

$SRC = "$BUILD/dist/$APP.exe"
$EXE = "$ROOT/$OUT_DIR/$APP-$VERSION-$TAG.exe"
if (-not (Test-Path $SRC)) { Write-Host "ERROR: no existe $SRC"; exit 1 }
Copy-Item $SRC $EXE -Force
Write-Host "      $OUT_DIR/$APP-$VERSION-$TAG.exe"

# ----------------------------------------------------------------------------
# 6 - VERIFICAR:
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Verificando..."
if (-not (Test-Path $EXE)) {
    Write-Host "============================================"
    Write-Host "  ERROR: no se genero el exe"
    Write-Host "============================================"
    exit 1
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  BUILD COMPLETADO - $OUT_DIR/"
Write-Host "============================================================"
Write-Host ""
Write-Host "  Version:  $VERSION"
Write-Host "  Fecha:    $FECHA"
Write-Host "  Tag:      $TAG"
Write-Host ""
Write-Host "  Para ejecutar:"
Write-Host "    $OUT_DIR/$APP-$VERSION-$TAG.exe"
Write-Host ""
Write-Host "  IMPORTANTE: el exe es autocontenido (onefile). Si Smart App"
Write-Host "  Control lo bloquea en otro equipo, es la politica de ese"
Write-Host "  equipo - no un problema del build."
Write-Host ""
