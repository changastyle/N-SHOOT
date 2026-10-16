# 📷 Screenshot Tool — GreenShot pero mejor (Linux Mint)

Capturador de pantalla que vive en el tray. Presionás un atajo (por defecto **F10**),
la pantalla se congela, dibujás el área, y al soltar el mouse:

1. ✅ Se **guarda** el crop como JPEG en tu carpeta
2. ✅ Se **copia** al portapapeles
3. ✅ Toast de confirmación + preview flotante + 💥 sonido de obturador

## Instalación

```bash
CI-CD-LOCAL/install.sh     # crea el venv, instala deps y configura autoarranque
CI-CD-LOCAL/run.sh         # arranca (o reiniciá la sesión para autostart)
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
| `screenshot_tray_linux.py` | Programa principal |
| `requirements.txt` | Dependencias |
| `CI-CD-LOCAL/install.sh` | Instalación (venv + deps + autostart) |
| `CI-CD-LOCAL/run.sh` | Lanzar manualmente |
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
