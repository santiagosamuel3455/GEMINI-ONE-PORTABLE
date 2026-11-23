# -*- coding: utf-8 -*-
"""Extrae la parte necesaria del script original ultra0.py para generar el núcleo autónomo ultra0_core.py."""
import os
from pathlib import Path

# Ruta por defecto del script original: <usuario>/Downloads/google-ultra-main/ultra0.py
# También se puede sobrescribir con la variable de entorno ULTRA0_SRC.
SRC = Path(os.environ.get(
    "ULTRA0_SRC",
    Path.home() / "Downloads" / "google-ultra-main" / "ultra0.py",
))
DST = Path(__file__).resolve().parent / "ultra0_core.py"

lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)


def seg(a, b):
    """Extrae un rango cerrado de líneas (base 1)"""
    return "".join(lines[a - 1:b])


HEADER = '''# -*- coding: utf-8 -*-
"""
ultra0_core.py —— Núcleo autónomo extraído de google-ultra-main/ultra0.py (sin dependencias externas)

Incluye: detección de adb/dispositivo, root, gestión de frida-server (con descarga automática),
instalación del módulo de facturación, arranque de Google One, plantilla BillingClient (FRIDA_JS)
y binario del módulo de facturación (MODULE_B64).
"""
import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

'''

# Localiza el bloque if __name__ final para conservar solo FRIDA_JS + MODULE_B64
tail_start = next(i for i, l in enumerate(lines, 1) if l.startswith('if __name__'))
FRIDA_AND_MODULE = "".join(lines[759:tail_start - 1]).rstrip() + "\n"

parts = [
    HEADER,
    "# ---------- Constantes (líneas originales 52-74) ----------\n",
    seg(53, 74),
    "\n# ---------- Variables globales (líneas originales 91-92) ----------\n",
    seg(91, 92),
    "\n# ---------- Detección de adb (líneas originales 78-88) ----------\n",
    seg(78, 88),
    "\n# ---------- Utilidades base: sh / impresión (líneas originales 95-117) ----------\n",
    seg(95, 117),
    "\n# ---------- Selección de dispositivo / root / frida-server / módulo (líneas originales 120-218) ----------\n",
    seg(120, 218),
    "\n# ---------- Inicio de Google One (líneas originales 462-467) ----------\n",
    seg(462, 467),
    "\n# ---------- Plantilla de inyección BillingClient (líneas originales 470-488) ----------\n",
    seg(470, 488),
    "\n# ---------- Recursos embebidos: FRIDA_JS + MODULE_B64 (línea 760 hasta el final) ----------\n",
    FRIDA_AND_MODULE,
]

DST.write_text("".join(parts), encoding="utf-8")
print("escrito:", DST, DST.stat().st_size, "bytes")
