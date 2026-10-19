# 📷 Screenshot Tool — GreenShot pero mejor (Linux Mint)

Capturador de pantalla que vive en el tray. Presionás un atajo (por defecto **F10**),
la pantalla se congela, dibujás el área, y al soltar el mouse:

1. ✅ Se **guarda** el crop como JPEG en tu carpeta
2. ✅ Se **copia** al portapapeles
3. ✅ Toast de confirmación + preview flotante + 💥 sonido de obturador

## Instalación

No hay instalador: el **AppImage es autocontenido** (Python, Qt y
`libxcb-cursor` ya vienen adentro).

```bash
./screenshot-tool-<version>-x86_64.AppImage   # doble clic también vale
```

La primera ejecución ya registra el **autoarranque** (se puede desactivar
en Preferencias → Sistema). Si tu distro no tiene FUSE 2, ejecutala con
`--appimage-extract-and-run`.

Para generar el AppImage:

```bash
CI-CD-LOCAL/generate-appimage.sh [version]    # artefacto en OUT/
```

Modo desarrollo (opcional):

```bash
python3 -m venv .venv
.venv/bin/pip install $(grep -v pynput requirements.txt | tr '\n' ' ')
.venv/bin/pip install --no-deps pynput   # evdev necesita python3-dev; prescindible
.venv/bin/python N-SHOOT.py
```

## Uso

| Acción | Resultado |
|---|---|
| **F10** (cualquier app) | Congelar pantalla + modo selección |
| Clic izquierdo + arrastrar | Elegir el área |
| Soltar el mouse | Guarda + copia al portapapeles |
| **Enter** (sin arrastrar) | Captura la ventana señalada |
| **ESC** o clic derecho | Cancelar |

### Extras del overlay
- 🔎 Lupa con zoom junto al cursor
- 📐 Coordenadas `x,y` en vivo + tamaño `W×H` del área
- ➕ Guías cruzando toda la pantalla
- ▦ Regla de tercios dentro de la selección
- 🟨 Detección de ventanas al pasar el mouse

## Preferencias (clic derecho en el icono del tray)
Todo configurable por pestañas: **Captura** (atajo, detección de ventanas),
**Guardado** (carpeta, JPG/PNG/ambos, calidad, prefijo de nombre, abrir después),
**Aspecto** (lupa, tercios, color del borde, toast, preview, sonido),
**Sistema** (autoarranque).

## Archivos

| Archivo | Descripción |
|---|---|
| `N-SHOOT.py` | Programa principal |
| `requirements.txt` | Dependencias |
| `CI-CD-LOCAL/generate-appimage.sh` | Build del AppImage autocontenido |
| `~/.config/screenshot-tool/config.json` | Config persistida |
| `~/.config/autostart/screenshot-tool.desktop` | Autoarranque |
| `~/.cache/screenshot-tool.log` | Log de errores en runtime |

## Detalles técnicos
- **X11 real**: con `XGrabKey` la app **consume la tecla** a nivel servidor X:
  ningún otro programa recibe F10 (no se abren menúes al azar).
  Si falla, cae automáticamente a `pynput` como fallback.
- La pantalla se captura una vez al abrir el overlay (`mss`), así el recorte
  es exacto y **sin parpadeos ni re-capturas**.
- **Instancia única**: si ya hay un proceso corriendo, no se duplica.
- **Sin instalador**: el AppImage re-escribe su `.desktop` de autostart en
  cada arranque (Exec apunta al AppImage real, no a paths temporales).
