@echo off
setlocal EnableExtensions
rem ============================================================================
rem  GENERATE-EXE.BAT
rem  Build completo de Screenshot Tool (Windows):
rem    PyInstaller (exe unico) + icono .ico ->
rem    OUT/screenshot-tool-<VERSION>-win_amd64.exe
rem
rem  Equivalente Windows de generate-appimage.sh (misma convencion de
rem  nombre para que release.yml extraiga la version igual).
rem
rem  NOTA Smart App Control: si el exe final queda bloqueado por la politica
rem  del equipo (como paso con las DLLs de PyQt6), solo lo puede liberar el
rem  usuario/admin - el build en si no falla.
rem
rem  Uso:
rem    generate-exe.bat [version]
rem    (por defecto 1.0.0; solo nombra el artefacto, no hay VERSION file)
rem ============================================================================

rem El .bat esta en CI-CD-LOCAL/ pero los archivos del proyecto estan arriba:
set "SCRIPT_DIR=%~dp0"
for %%i in ("%SCRIPT_DIR%..") do set "ROOT=%%~fi"
pushd "%ROOT%" || exit /b 1

set "APP=screenshot-tool"
set "BUILD=CI-CD-LOCAL/build"
set "OUT_DIR=OUT"

echo.
echo ============================================================
echo   Build Screenshot Tool (Windows)  -^>  %OUT_DIR%/
echo ============================================================
echo.

rem ----------------------------------------------------------------------------
rem 1 - VERIFICAR PYTHON + ARCH:
rem ----------------------------------------------------------------------------
echo [1/6] Verificando python...
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    set "PY="
    for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
    if not defined PY (
        echo ERROR: python no encontrado.
        exit /b 1
    )
)
for /f "delims=" %%i in ('"%PY%" -V') do echo       %%i OK

set "ARCH=%PROCESSOR_ARCHITEW6432%"
if not defined ARCH set "ARCH=%PROCESSOR_ARCHITECTURE%"
if /i "%ARCH%"=="AMD64" (set "TAG=win_amd64") else if /i "%ARCH%"=="ARM64" (set "TAG=win_arm64") else (set "TAG=win_%ARCH%")

rem ----------------------------------------------------------------------------
rem 2 - VERSION Y FECHA DEL BUILD:
rem ----------------------------------------------------------------------------
echo.
echo [2/6] Version y fecha del build...
set "VERSION=%~1"
if not defined VERSION set "VERSION=1.0.0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "FECHA=%%i"
echo       Version: %VERSION%  -  Fecha: %FECHA%  -  Tag: %TAG%

rem ----------------------------------------------------------------------------
rem 3 - CERRAR INSTANCIAS QUE BLOQUEEN EL BUILD Y LIMPIAR BUILD ANTERIOR:
rem ----------------------------------------------------------------------------
echo.
echo [3/6] Cerrando instancias previas y limpiando...

rem Solo instancias reales de la app (python .../N-SHOOT.py o el exe compilado).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'Name like ''python%%''' | Where-Object { $_.CommandLine -match 'N-SHOOT\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
taskkill /f /im "%APP%.exe" >nul 2>&1
rem timeout falla cuando stdin no es una consola (cmd /c); ping siempre funciona:
ping -n 2 127.0.0.1 >nul

if exist "%BUILD%\dist" rd /s /q "%BUILD%\dist"
if exist "%BUILD%\work" rd /s /q "%BUILD%\work"
if not exist "%BUILD%" mkdir "%BUILD%"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
echo       Limpieza completada.

rem ----------------------------------------------------------------------------
rem 4 - ENTORNO DE BUILD + COMPILAR CON PYINSTALLER (exe unico):
rem ----------------------------------------------------------------------------
echo.
echo [4/6] Compilando con PyInstaller...

if not exist "%ROOT%\.venv\Scripts\python.exe" (
    echo       Creando .venv...
    "%PY%" -m venv .venv || exit /b 1
    set "PY=%ROOT%\.venv\Scripts\python.exe"
)
"%PY%" -m pip install -q --upgrade pip || exit /b 1
rem requirements.txt ya filtra por plataforma: en win32 instala PySide6
rem (PyQt6 puede quedar bloqueado por Smart App Control) + mss + pynput.
"%PY%" -m pip install -q -r requirements.txt || exit /b 1
"%PY%" -m pip install -q pyinstaller pillow || exit /b 1

rem Icono: CI-CD-LOCAL/ICONS/icon.svg -> PNG 256 (Qt del venv) -> icon.ico (Pillow).
rem Ruta ABSOLUTA: PyInstaller resuelve --icon relativo al specpath, no al cwd.
set "ICO=%ROOT%\%BUILD%\icon.ico"
set "ICONPY=%BUILD%\_icon_build.py"
> "%ICONPY%" echo import os, sys
>> "%ICONPY%" echo os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
>> "%ICONPY%" echo sys.path.insert(0, ".")
>> "%ICONPY%" echo from UTILS.qt_compat.QtWidgets import QApplication
>> "%ICONPY%" echo from UTILS.qt_compat.QtGui import QImage, QPainter
>> "%ICONPY%" echo from UTILS.qt_compat.QtSvg import QSvgRenderer
>> "%ICONPY%" echo from UTILS.qt_compat.QtCore import Qt
>> "%ICONPY%" echo QApplication([])
>> "%ICONPY%" echo img = QImage(256, 256, QImage.Format.Format_ARGB32)
>> "%ICONPY%" echo img.fill(Qt.GlobalColor.transparent)
>> "%ICONPY%" echo r = QSvgRenderer("CI-CD-LOCAL/ICONS/icon.svg")
>> "%ICONPY%" echo p = QPainter(img)
>> "%ICONPY%" echo r.render(p)
>> "%ICONPY%" echo p.end()
>> "%ICONPY%" echo img.save(r"CI-CD-LOCAL/build/icon.png")
>> "%ICONPY%" echo from PIL import Image
>> "%ICONPY%" echo Image.open(r"CI-CD-LOCAL/build/icon.png").save(r"CI-CD-LOCAL/build/icon.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
>> "%ICONPY%" echo print("icono generado")
"%PY%" "%ICONPY%"
if errorlevel 1 (
    echo       AVISO: no se pudo generar icon.ico; el exe saldra sin icono.
    set "ICO="
)

rem qt_compat importa PyQt6 y PySide6 estaticamente: si ambos estan en el venv,
rem PyInstaller corre los dos hooks y aborta. En win32 el binding es PySide6
rem (requirements.txt), asi que se excluyen los demas bindings del bundle.
set "PIARGS=--noconfirm --clean --onefile --windowed --name %APP% --hidden-import=pynput --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module PySide2 --distpath %BUILD%/dist --workpath %BUILD%/work --specpath %BUILD%"
if defined ICO set "PIARGS=%PIARGS% --icon %ICO%"

"%PY%" -m PyInstaller %PIARGS% N-SHOOT.py
if errorlevel 1 (
    echo ERROR: PyInstaller fallo.
    exit /b 1
)
echo.
echo       Compilacion exitosa!

rem ----------------------------------------------------------------------------
rem 5 - COPIAR A OUT/ CON EL NOMBRE DE RELEASE:
rem ----------------------------------------------------------------------------
echo.
echo [5/6] Empaquetando...

set "SRC=%BUILD%\dist\%APP%.exe"
set "EXE=%ROOT%\%OUT_DIR%\%APP%-%VERSION%-%TAG%.exe"
if not exist "%SRC%" (
    echo ERROR: no existe %SRC%
    exit /b 1
)
copy /y "%SRC%" "%EXE%" >nul
echo       %OUT_DIR%/%APP%-%VERSION%-%TAG%.exe

rem ----------------------------------------------------------------------------
rem 6 - VERIFICAR:
rem ----------------------------------------------------------------------------
echo.
echo [6/6] Verificando...
if not exist "%EXE%" (
    echo ============================================
    echo   ERROR: no se genero el exe
    echo ============================================
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD COMPLETADO - %OUT_DIR%/
echo ============================================================
echo.
echo   Version:  %VERSION%
echo   Fecha:    %FECHA%
echo   Tag:      %TAG%
echo.
echo   Para ejecutar:
echo     %OUT_DIR%/%APP%-%VERSION%-%TAG%.exe
echo.
echo   IMPORTANTE: el exe es autocontenido (onefile). Si Smart App
echo   Control lo bloquea en otro equipo, es la politica de ese
echo   equipo - no un problema del build.
echo.
endlocal
