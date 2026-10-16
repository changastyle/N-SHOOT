@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================================
REM  GENERAR-EXECUTABLE.BAT
REM  Build completo de ClockerTray (Windows):
REM    Maven package (jar-with-dependencies) + launch4j -> target\ClockerTray.exe
REM    y arma OUT\ listo para distribuir: exe + jar + config + resources.
REM
REM  VERSIONES Y FECHA:
REM    - La version se lee de pom.xml (<version>): nombra el jar en OUT\
REM      (clocker-<VERSION>-jar-with-dependencies.jar) y la muestra el resumen.
REM    - La fecha del build se muestra en el resumen (YYYY-MM-DD).
REM    - Uso: GENERAR-EXECUTABLE.bat [nueva_version]
REM      Si se pasa una version (ej: 1.1) se actualiza pom.xml antes de compilar.
REM ============================================================================

REM El .bat esta en CI-CD-LOCAL\ pero los archivos del proyecto estan arriba:
set "ROOT=%~dp0.."
set "OUT=%ROOT%\OUT"

echo.
echo ============================================================
echo   Build ClockerTray  -^>  OUT\
echo ============================================================
echo.

REM ---------------------------------------------------------------------------
REM 1 - VERIFICAR JAVA Y MAVEN EN EL PATH:
REM ---------------------------------------------------------------------------
echo [1/6] Verificando Java y Maven...
java -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Java no encontrado en el PATH ^(se necesita JDK 17+^).
    pause
    exit /b 1
)
REM call obligatorio: mvn es mvn.cmd y un call pelado a otro .bat/.cmd
REM transfiere el control y el script nunca retoma (muere en silencio):
call mvn -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Maven no encontrado en el PATH.
    pause
    exit /b 1
)
for /f "tokens=3" %%i in ('mvn -version 2^>^&1 ^| findstr /R /C:"Apache Maven [0-9]"') do set "MVNVER=%%i"
echo       Maven !MVNVER! OK

REM ---------------------------------------------------------------------------
REM 2 - VERSION (pom.xml) Y FECHA DEL BUILD:
REM ---------------------------------------------------------------------------
echo.
echo [2/6] Leyendo version de pom.xml y fecha del build...

REM El primer <version>X</version> del pom es la del proyecto
REM (los <version> de dependencias/plugins vienen despues):
set "VERSION=?"
for /f "tokens=3 delims=<>" %%v in ('findstr /R /C:" *<version>[^<]*</version>" "%ROOT%\pom.xml"') do (
    set "VERSION=%%v"
    goto :VERSION_OK
)
:VERSION_OK

REM Si se paso una version por parametro -> actualizar pom.xml antes de compilar
REM (reemplazo exacto: solo matchea la linea de version del proyecto):
if not "%~1"=="" (
    echo       Actualizando version en pom.xml: !VERSION! -^> %~1
    powershell -NoProfile -Command "$p='%ROOT%\pom.xml'; $c=Get-Content -Raw $p; $c=$c -replace '<version>!VERSION!</version>','<version>%~1</version>'; Set-Content -NoNewline $p $c"
    if errorlevel 1 (
        echo ERROR: No se pudo actualizar la version en pom.xml.
        pause
        exit /b 1
    )
    set "VERSION=%~1"
)

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "FECHA=%%d"
echo       Version: !VERSION!  -  Fecha: !FECHA!

REM ---------------------------------------------------------------------------
REM 3 - MATAR PROCESOS QUE BLOQUEEN target\ u OUT\ Y LIMPIAR BUILD ANTERIOR:
REM ---------------------------------------------------------------------------
echo.
echo [3/6] Cerrando instancias previas...

taskkill /F /IM ClockerTray.exe >nul 2>&1

timeout /t 2 /nobreak >nul 2>&1

REM Forzar borrado del exe si sigue ahi (en target y en out):
if exist "%ROOT%\target\ClockerTray.exe" (
    del /F /Q "%ROOT%\target\ClockerTray.exe" >nul 2>&1
)
if exist "%OUT%\ClockerTray.exe" (
    del /F /Q "%OUT%\ClockerTray.exe" >nul 2>&1
)
if exist "%ROOT%\target\ClockerTray.exe" goto :NO_BORRAR
if exist "%OUT%\ClockerTray.exe" goto :NO_BORRAR

echo      - Limpieza completada.
echo.
goto :COMPILAR

:NO_BORRAR
echo      AVISO: ClockerTray.exe sigue bloqueado por otro proceso.
echo      Cierralo manualmente y volve a correr el script.
pause
exit /b 1

:COMPILAR
REM ---------------------------------------------------------------------------
REM 4 - COMPILAR CON MAVEN (jar-with-dependencies + launch4j -> ClockerTray.exe):
REM ---------------------------------------------------------------------------
echo.
echo [4/6] Compilando con Maven (mvn clean package)...
pushd "%ROOT%"
call mvn clean package
set MVN_EXIT=%ERRORLEVEL%
popd
if not "%MVN_EXIT%"=="0" goto :ERROR_MAVEN

echo.
echo       Compilacion exitosa!
echo.

REM ---------------------------------------------------------------------------
REM 5 - ARMAR CARPETA OUT: exe + jar (deps empaquetadas) + config + resources:
REM ---------------------------------------------------------------------------
echo [5/6] Copiando artefactos y dependencias a OUT\...

if not exist "%OUT%" mkdir "%OUT%"
if not exist "%OUT%\src\main\resources" mkdir "%OUT%\src\main\resources"

REM El .exe envuelve al jar-with-dependencies (todas las deps adentro);
REM se copia tambien el jar como alternativa de ejecucion:
copy /Y "%ROOT%\target\ClockerTray.exe" "%OUT%\" >nul
if errorlevel 1 goto :ERROR_COPIA
copy /Y "%ROOT%\target\clocker-!VERSION!-jar-with-dependencies.jar" "%OUT%\" >nul
if errorlevel 1 goto :ERROR_COPIA

REM app.properties filtrado (${project.artifactId} ya resuelto) junto al exe,
REM para sobreescribir claves app.* sin recompilar:
copy /Y "%ROOT%\target\classes\app.properties" "%OUT%\" >nul
if errorlevel 1 goto :ERROR_COPIA

REM Resources que la app lee por FILESYSTEM con cwd = carpeta del exe
REM (RutasGlobales arma <cwd>\src\main\resources\): se replica esa estructura
REM dentro de OUT\ para que sonidos (SOUNDS\*.mp3) y libs funcionen:
xcopy /E /I /Y /Q "%ROOT%\src\main\resources" "%OUT%\src\main\resources" >nul
if errorlevel 1 goto :ERROR_COPIA

echo      - OUT\ClockerTray.exe
echo      - OUT\clocker-!VERSION!-jar-with-dependencies.jar
echo      - OUT\app.properties
echo      - OUT\src\main\resources\  (SOUNDS + resources de runtime)
echo.

REM ---------------------------------------------------------------------------
REM 6 - VERIFICAR QUE QUEDO EL EXE EN OUT\:
REM ---------------------------------------------------------------------------
echo [6/6] Verificando OUT\...
if not exist "%OUT%\ClockerTray.exe" goto :ERROR_COPIA

echo.
echo ============================================================
echo   BUILD COMPLETADO - OUT\
echo ============================================================
echo.
echo   Version:  !VERSION!
echo   Fecha:    !FECHA!
echo.
echo   Para ejecutar:
echo     OUT\ClockerTray.exe
echo     java -jar OUT\clocker-!VERSION!-jar-with-dependencies.jar
echo.
echo   IMPORTANTE: correrlo con cwd = OUT\ (doble click alcanza).
echo   Junto al exe van app.properties (override de config) y
echo   src\main\resources\ (sonidos/libs que la app lee por filesystem).
echo.
pause
exit /b 0

:ERROR_COPIA
echo.
echo ============================================
echo   ERROR: no se pudieron copiar los artefactos a OUT\
echo   Revisa que target\ tenga el exe/jar (mvn clean package).
echo ============================================
pause
exit /b 1

:ERROR_MAVEN
echo.
echo ============================================
echo   ERROR: La compilacion fallo.
echo   Revisa los mensajes de Maven arriba.
echo ============================================
pause
exit /b 1