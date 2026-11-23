# -*- coding: utf-8 -*-
"""scan_debug.py —— Imprime todos los eventos de una consulta para depurar resultados vacíos"""
import argparse
import json
import sys
import time
from pathlib import Path

import one_common

ultra0 = one_common.ultra0
HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser(description="Depuración de eventos de consulta de SKUs")
    ap.add_argument("serial", help="Serie del dispositivo")
    ap.add_argument("--sku", action="append", default=["g1.2tb"], help="SKU a probar (por defecto g1.2tb)")
    a = ap.parse_args()

    one_common.setup(serial=a.serial)
    print("PID de Vending:", ultra0.sh("shell", "pidof com.android.vending") or "(ninguno)")
    print("PID de Google One:", ultra0.sh("shell", "pidof com.google.android.apps.subscriptions.red") or "(ninguno)")

    pid = ultra0.launch_app()
    print("launch_app pid =", pid, flush=True)
    if not pid:
        raise SystemExit("Google One no pudo iniciar")

    import frida
    dev = frida.get_device(ultra0.SERIAL, timeout=10)
    sess = dev.attach(pid)
    js = (HERE / "scan_offers.js").read_text(encoding="utf-8")
    js = js.replace("var PRODUCTS = [];", "var PRODUCTS = " + json.dumps(a.sku) + ";", 1)

    def on_msg(m, _d):
        print("EVENTO:", json.dumps(m.get("payload") or m, ensure_ascii=False)[:600], flush=True)

    sc = sess.create_script(js)
    sc.on("message", on_msg)
    sc.load()
    time.sleep(12)
    print("LISTO", flush=True)


if __name__ == "__main__":
    main()
