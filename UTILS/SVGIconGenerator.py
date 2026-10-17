#!/usr/bin/env python3
"""SVGIconGenerator — genera el icono SVG de la app de capturas.

Es una silueta blanca minimalista de cámara, al estilo de los iconos
monocromos del panel de Mint (escudo, wifi, volumen): vectorial, con
curvas suaves y lente calado, se ve nítida en el tray a 16-24 px.

Uso:
    python3 UTILS/SVGIconGenerator.py [ruta_salida.svg]

Si no se pasa ruta, escribe el icono en su ubicación persistente
(~/.config/screenshot-tool/icon.svg), de donde la app lo carga al arrancar.
Opcionalmente, si PyQt6 está disponible, exporta también PNGs en varios
tamaños (16/24/32/48/64/128) a UTILS/png/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Definición del icono
# --------------------------------------------------------------------------- #
# Cámara en silueta maciza (se lee mejor a tamaño de tray que el outline):
# cuerpo redondeado con visor y lente calado con pupila (anillo oscuro +
# punto blanco, como la doble línea del escudo pero en relleno).
SVG_TEMPLATE = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <!-- cuerpo + visor macizos; lente calado y pupila por fill-rule evenodd -->
  <path fill="#ffffff" fill-rule="evenodd" d="M10.5 5.5h3q1.5 0 1.5 1.5v1h2.7q2.8 0 2.8 2.8v5.4q0 2.8-2.8 2.8h-11.4q-2.8 0-2.8-2.8v-5.4q0-2.8 2.8-2.8h2.7v-1q0-1.5 1.5-1.5Z M12 9.9a3.6 3.6 0 1 0 0 7.2a3.6 3.6 0 1 0 0-7.2Z M12 12.3a1.2 1.2 0 1 0 0 2.4a1.2 1.2 0 1 0 0-2.4Z"/>
</svg>
"""

PNG_SIZES = (16, 24, 32, 48, 64, 128)

# Versión del diseño: ensure_saved_icon reescribe el icono persistido cuando
# este stamp no coincide, para que un cambio de icono se vea en el próximo
# arranque sin tener que borrar ~/.config/screenshot-tool/icon.svg a mano.
ICON_VERSION = 10
_STAMP = f"<!-- screenshot-tool icon v{ICON_VERSION} -->"

# Ubicación persistente del icono: la app lo carga de acá al arrancar.
ICON_PATH = (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
             / "screenshot-tool" / "icon.svg")


def ensure_saved_icon(force: bool = False) -> Path | None:
    """Garantiza que el icono persista en ICON_PATH y devuelve la ruta.

    Reescribe el archivo si no existe o si el stamp de versión no coincide
    (icono de un diseño anterior): así el icono nuevo carga desde el
    arranque sin intervención manual. Devuelve None si falla."""
    try:
        stale = True
        if ICON_PATH.exists():
            try:
                with ICON_PATH.open(encoding="utf-8") as f:
                    stale = f.readline().strip() != _STAMP
            except OSError:
                stale = True
        if force or stale:
            write_svg(ICON_PATH)
        return ICON_PATH
    except OSError:
        return None


def build_svg() -> str:
    """Devuelve el contenido SVG del icono como string."""
    return f"{_STAMP}\n{SVG_TEMPLATE}"


def write_svg(out_path: Path) -> Path:
    """Escribe el SVG en out_path y devuelve la ruta."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_svg(), encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- #
# Exportación a PNG (opcional, requiere PyQt6)
# --------------------------------------------------------------------------- #
def export_pngs(svg_path: Path, out_dir: Path, sizes: tuple[int, ...] = PNG_SIZES) -> list[Path]:
    """Renderiza el SVG a PNG en varios tamaños. Devuelve las rutas creadas."""
    try:
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QIcon, QImage, QPainter, Qt
        from PyQt6.QtSvg import QSvgRenderer
    except ImportError:
        print("PyQt6 no disponible: se omite la exportación a PNG.")
        return []

    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"SVG inválido: {svg_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for size in sizes:
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(p, QSize(size, size))
        p.end()
        path = out_dir / f"icon_{size}.png"
        img.save(str(path), "PNG")
        written.append(path)
    return written


def main(argv: list[str]) -> int:
    here = Path(__file__).resolve().parent
    out = Path(argv[1]) if len(argv) > 1 else ICON_PATH
    svg = write_svg(out)
    print(f"SVG generado: {svg}")

    for png in export_pngs(svg, here / "png"):
        print(f"PNG generado: {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
