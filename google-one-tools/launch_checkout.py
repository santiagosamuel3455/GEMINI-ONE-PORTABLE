# -*- coding: utf-8 -*-
"""
launch_checkout.py —— Abre la pantalla de pago de Google Play para cualquier SKU (solo la muestra, no suscribe automáticamente)

Uso:
    .\\.venv\\Scripts\\python.exe launch_checkout.py                     # Selecciona el primer dispositivo; SKU por defecto en launch_checkout.js
    .\\.venv\\Scripts\\python.exe launch_checkout.py emulator-5554       # Especifica una instancia del emulador
    .\\.venv\\Scripts\\python.exe launch_checkout.py --sku g1.30tb       # Cambia el SKU temporalmente sin editar el .js
    .\\.venv\\Scripts\\python.exe launch_checkout.py --sku g1.30tb emulator-5554

Flujo:
    Preparación (one_common.setup) → Reiniciar Google One → Inyección con frida →
    Consultar ofertas del SKU → Abrir checkout de Play → Esperar resultado

Eventos:
    setup    code=0  Conexión exitosa con el servicio de facturación (sin este evento = Play Store no está activo)
    offer            Oferta encontrada (micros es precio en millonésimas; 0 = prueba gratuita)
    launched code=0  Pantalla de pago abierta (★puede consumir la elegibilidad de prueba, úsalo con cuidado★)
"""
import argparse
import json
import sys
import time
from pathlib import Path

import one_common
ultra0 = one_common.ultra0  # Núcleo autónomo (ver ultra0_core.py)
HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser(description="Abre la pantalla de pago de Google Play para cualquier SKU de Google One")
    ap.add_argument("serial", nargs="?", help="Serie del dispositivo, ej. emulator-5554 o 127.0.0.1:5555")
    ap.add_argument("--sku", default=None, help="SKU objetivo, ej. g1.30tb; si se omite usa el de launch_checkout.js")
    args = ap.parse_args()

    serial = one_common.setup(serial=args.serial)

    # Si Play Store está bloqueado, intenta recuperarlo reiniciando el emulador
    if not one_common.ensure_vending():
        one_common.reboot_and_recover()

    import frida
    # Reinicia solo Google One (para un Activity limpio), sin detener Play Store
    ultra0.sh("shell", f"am force-stop {one_common.GOOGLE_ONE}")
    time.sleep(2)
    pid = ultra0.launch_app()
    print("GOOGLE_ONE_PID =", pid, flush=True)
    if not pid:
        sys.exit("Google One no inició (ábrelo manualmente una vez en el emulador e intenta de nuevo)")

    dev = frida.get_device(ultra0.SERIAL, timeout=10)   # Conectar por serial exacto
    sess = dev.attach(pid)

    js = (HERE / "launch_checkout.js").read_text(encoding="utf-8")
    if args.sku:  # Sobrescribe el valor por defecto del .js con --sku
        import re
        js = re.sub(r'var TARGET_PRODUCT = "[^"]+";', f'var TARGET_PRODUCT = "{args.sku}";', js, count=1)

    launched = {"p": None}

    def on_msg(m, _d):
        p = m.get("payload") or {}
        ev = p.get("ev")
        if ev in ("setup", "products", "offer", "launched", "no_offer", "no_activity",
                  "no_activity_ui", "launch_err", "act_err", "purchase_cb", "disc"):
            print("EVENTO:", json.dumps(p, ensure_ascii=False), flush=True)
        if ev == "launched":
            launched["p"] = p

    sc = sess.create_script(js)
    sc.on("message", on_msg)
    sc.load()

    for _ in range(15):           # Esperar como máximo 30 segundos
        time.sleep(2)
        if launched["p"] is not None:
            break

    code = (launched["p"] or {}).get("code")
    if code == 0:
        print("\nRESULTADO: ✅ Checkout abierto correctamente (launched code=0). Confírmalo manualmente en el emulador", flush=True)
    elif launched["p"] is not None:
        print(f"\nRESULTADO: ❌ Error al abrir el checkout code={code} msg={(launched['p'] or {}).get('msg')}", flush=True)
    else:
        print("\nRESULTADO: ❌ No se recibió el evento 'launched'"
              "\n  Verifica: ① Si Play Store está ejecutándose ② Si se quedó colgado (failed to attach → reinicia el emulador)"
              "\n            ③ Si tu frida local es 16.x (la 17.x rompe el puente Java)", flush=True)


if __name__ == "__main__":
    main()
