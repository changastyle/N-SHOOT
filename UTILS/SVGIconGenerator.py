#!/usr/bin/env python3
"""SVGIconGenerator — genera el icono SVG de la app de capturas.

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
SVG_TEMPLATE = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{bg_top}"/>
      <stop offset=".5" stop-color="{bg_mid}"/>
      <stop offset="1" stop-color="{bg_bot}"/>
    </linearGradient>
    <linearGradient id="lens" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{lens_top}"/>
      <stop offset="1" stop-color="{lens_bot}"/>
    </linearGradient>
    <radialGradient id="glint" cx=".35" cy=".3" r=".8">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".9"/>
      <stop offset=".35" stop-color="#ffffff" stop-opacity=".12"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="1" stdDeviation="1.2" flood-color="#0f172a" flood-opacity=".35"/>
    </filter>
  </defs>

  <!-- fondo -->
  <rect x="2" y="2" width="60" height="60" rx="15" fill="url(#bg)"/>

  <!-- marcas de recorte (screenshot) -->
  <g stroke="#ffffff" stroke-opacity=".55" stroke-width="2.5" stroke-linecap="round" fill="none">
    <path d="M9 15v-3a3 3 0 0 1 3-3h3"/>
    <path d="M49 9h3a3 3 0 0 1 3 3v3"/>
    <path d="M55 49v3a3 3 0 0 1-3 3h-3"/>
    <path d="M15 55h-3a3 3 0 0 1-3-3v-3"/>
  </g>

  <!-- cuerpo de cámara -->
  <g filter="url(#soft)">
    <path d="M24 15h16a3 3 0 0 1 3 3v3h-22v-3a3 3 0 0 1 3-3z" fill="#eef2ff"/>
    <rect x="9" y="19" width="46" height="31" rx="7" fill="#f8fafc"/>
  </g>

  <!-- lente -->
  <circle cx="32" cy="34.5" r="11.5" fill="#1e293b"/>
  <circle cx="32" cy="34.5" r="9" fill="url(#lens)"/>
  <circle cx="32" cy="34.5" r="4.5" fill="#0f172a"/>
  <circle cx="32" cy="34.5" r="9" fill="url(#glint)"/>
  <circle cx="27.5" cy="30" r="2" fill="#ffffff" fill-opacity=".85"/>

  <!-- flash -->
  <circle cx="48.5" cy="25.5" r="2" fill="{flash}"/>

  <!-- destello -->
  <path d="M50 42l1.2 3 3 1.2-3 1.2-1.2 3-1.2-3-3-1.2 3-1.2z" fill="#ffffff" fill-opacity=".9"/>
</svg>
"""

PALETTE = {
    "bg_top":   "#a78bfa",   # violeta claro
    "bg_mid":   "#8b5cf6",   # violeta
    "bg_bot":   "#6d28d9",   # violeta profundo
    "lens_top": "#ddd6fe",   # lavanda
    "lens_bot": "#7c3aed",   # violeta
    "flash":    "#f0abfc",   # fucsia suave
}

PNG_SIZES = (16, 24, 32, 48, 64, 128)

# Ubicación persistente del icono: la app lo carga de acá al arrancar.
ICON_PATH = (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
             / "screenshot-tool" / "icon.svg")


def ensure_saved_icon(force: bool = False) -> Path | None:
    """Garantiza que el icono persista en ICON_PATH y devuelve la ruta.

    Si ya existe (y no se fuerza), no lo regenera: así un icono generado a
    mano sobrevive a los reinicios de la app. Devuelve None si falla."""
    try:
        if force or not ICON_PATH.exists():
            write_svg(ICON_PATH)
        return ICON_PATH
    except OSError:
        return None


def build_svg(palette: dict[str, str] | None = None) -> str:
    """Devuelve el contenido SVG del icono como string."""
    colors = dict(PALETTE)
    if palette:
        colors.update(palette)
    return SVG_TEMPLATE.format(**colors)


def write_svg(out_path: Path, palette: dict[str, str] | None = None) -> Path:
    """Escribe el SVG en out_path y devuelve la ruta."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_svg(palette), encoding="utf-8")
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
