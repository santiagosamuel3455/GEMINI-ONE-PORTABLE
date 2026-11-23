# -*- coding: utf-8 -*-
"""
query_sku.py —— Consulta todas las ofertas (gratuitas y de pago, con token) de los SKUs indicados

Uso:
    .\\.venv\\Scripts\\python.exe query_sku.py g1.30tb g1.20tb             # Selección automática
    .\\.venv\\Scripts\\python.exe query_sku.py emulator-5554 g1.30tb       # Instancia específica

Solo consulta; no abre la pantalla de pago (sin riesgo).
"""
import argparse
import json
import threading
import time

import one_common
ultra0 = one_common.ultra0  # Núcleo autónomo (ver ultra0_core.py)
def main():
    ap = argparse.ArgumentParser(description="Consulta ofertas de SKUs específicos de Google One")
    ap.add_argument("serial", nargs="?", help="Serie del dispositivo (opcional, como primer argumento)")
    ap.add_argument("skus", nargs="+", help="SKUs a consultar, ej. g1.30tb g1.20tb")
    args = ap.parse_args()

    # Si el primer argumento no parece un SKU (no contiene punto), se toma como serial
    serial = None
    skus = list(args.skus)
    if args.serial and ("." not in args.serial):
        serial = args.serial
    elif args.serial:
        skus.insert(0, args.serial)

    one_common.setup(serial=serial)
    if not one_common.ensure_vending():
        one_common.reboot_and_recover()

    pid = ultra0.launch_app()
    print("GOOGLE_ONE_PID =", pid, flush=True)
    if not pid:
        raise SystemExit("Google One no pudo iniciar")

    import frida
    dev = frida.get_device(ultra0.SERIAL, timeout=10)
    sess = dev.attach(pid)

    js = ultra0.build_js("5x", True)
    js = js.replace('var PRODUCTS=["g1.play.20tb"];', "var PRODUCTS=" + json.dumps(skus) + ";", 1)

    offers = []
    done = threading.Event()

    def on_msg(m, _d):
        p = m.get("payload") or {}
        ev = p.get("ev")
        if ev == "offer":
            offers.append(p)
            micros = str(p.get("micros"))
            price = "Gratis $0" if micros == "0" else f"${int(micros) / 1e6:.2f}/período"
            print(f"  [{p.get('product')}] offer={p.get('id')} period={p.get('period')} → {price}", flush=True)
            if micros == "0":
                print(f"        token={p.get('token')}", flush=True)
        elif ev in ("no_trial", "list_only", "query_err", "boot_err", "boot_fail", "pd"):
            if ev != "pd":
                done.set()

    sc = sess.create_script(js)
    sc.on("message", on_msg)
    sc.load()
    done.wait(timeout=25)
    time.sleep(1)

    print(f"\n=== {', '.join(skus)} ===", flush=True)
    if not offers:
        print("  (No se devolvió ninguna oferta — el SKU no existe en la región de esta cuenta)", flush=True)


if __name__ == "__main__":
    main()
