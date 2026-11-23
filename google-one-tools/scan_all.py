# -*- coding: utf-8 -*-
"""
scan_all.py —— Escaneo completo de ofertas (gratuitas y de pago) para los SKUs de Google One en la cuenta actual

Uso:
    .\\.venv\\Scripts\\python.exe scan_all.py                      # Selección automática, escanea los 70 SKUs candidatos
    .\\.venv\\Scripts\\python.exe scan_all.py emulator-5554        # Instancia específica
    .\\.venv\\Scripts\\python.exe scan_all.py --sku a --sku b      # Escanea solo los SKUs indicados

Salida:
    1) Detalle de ofertas gratuitas (micros == 0) + token
    2) Resumen por cada SKU devuelto: cantidad de ofertas / gratuitas / precios de pago

Nota:
    BillingClient admite ~20 SKUs por consulta; el script divide automáticamente en lotes de 18.
    Solo consulta; no abre la pantalla de pago (sin riesgo).
"""
import argparse
import json
import threading
import time
from pathlib import Path

import one_common
ultra0 = one_common.ultra0  # Núcleo autónomo (ver ultra0_core.py)
# Pool de SKUs candidatos (almacenamiento / anual / IA / familia play / descuentos de bienvenida)
CANDIDATES = [
    # Niveles básicos de almacenamiento
    "g1.30gb", "g1.100gb", "g1.200gb", "g1.helium", "g1.2tb", "g1.5tb", "g1.10tb",
    "g1.20tb", "g1.30tb",
    # Variantes anuales
    "g1.100gb.annual", "g1.200gb.annual", "g1.2tb.annual", "g1.5tb.annual",
    # Sufijos de prueba gratuita de 1 mes
    "g1.30gb.1month_eft", "g1.100gb.1month_eft", "g1.200gb.1month_eft",
    "g1.2tb.1month_eft", "g1.20tb.1month_eft", "g1.30tb.1month_eft",
    # Sufijos de prueba gratuita de 12 meses
    "g1.2tb.12months_eft", "g1.20tb.12months_eft", "g1.30tb.12months_eft",
    # Planes de IA
    "g1.ai", "g1.ai.pro", "g1.ai.plus", "g1.ai.ultra",
    "g1.2tb.ai", "g1.2tb.ai.subs_variant", "g1.5tb.ai", "g1.20tb.ai", "g1.30tb.ai",
    "g1.5tb.ai.subs_variant", "g1.20tb.ai.subs_variant", "g1.30tb.ai.subs_variant",
    # Familia promocional play (donde suelen estar las pruebas gratuitas)
    "g1.play", "g1.play.ai", "g1.play.2tb", "g1.play.5tb", "g1.play.20tb", "g1.play.30tb",
    "g1.play.ai.pro", "g1.play.ai.plus", "g1.play.ai.ultra",
    "g1.play.helium", "g1.play.pro", "g1.play.plus",
    "g1.play.20tb.12month", "g1.play.ai.pro.12month", "g1.play.30tb.12month", "g1.play.5tb.12month",
    # Descuentos iniciales (introprice)
    "g1.2tb.3months_ip_85p.acq", "g1.5tb.3months_ip_75p.acq",
    "g1.100gb.3months_ip_83p.acq", "g1.200gb.3months_ip_83p.acq",
    "g1.30gb.3months_ip_83p.acq", "g1.helium.3months_ip_83p.acq",
    # Complementos adicionales
    "g1.youtube_premium_individual_add_on", "g1.youtube_premium_family_add_on",
    "g1.home_premium", "g1.health_premium", "g1.play.home", "g1.play.health",
    # Otras variantes
    "g1.ultra", "g1.ultra.20tb", "g1.ultra.30tb", "g1.pro", "g1.plus", "g1.premium",
]

CHUNK = 18  # Límite por lote (Play limita a ~20)


def main():
    ap = argparse.ArgumentParser(description="Escanea ofertas disponibles de SKUs de Google One")
    ap.add_argument("serial", nargs="?", help="Serie del dispositivo")
    ap.add_argument("--sku", action="append", help="Escanear solo los SKUs especificados (se puede repetir)")
    args = ap.parse_args()

    skus = args.sku or CANDIDATES
    # Deduplicar conservando el orden
    seen, uniq = set(), []
    for c in skus:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    skus = uniq
    print(f"Total: {len(skus)} SKUs candidatos, escaneando en lotes de {CHUNK}", flush=True)

    one_common.setup(serial=args.serial)
    if not one_common.ensure_vending():
        one_common.reboot_and_recover()

    pid = ultra0.launch_app()
    print("GOOGLE_ONE_PID =", pid, flush=True)
    if not pid:
        raise SystemExit("Google One no pudo iniciar")

    import frida
    dev = frida.get_device(ultra0.SERIAL, timeout=10)
    sess = dev.attach(pid)

    all_offers = []

    def scan_chunk(part, idx):
        """Escanea un lote usando la plantilla list_only y recopila eventos offer."""
        js = ultra0.build_js("5x", True)  # Plantilla de producto único + list_only, sin abrir checkout
        js = js.replace('var PRODUCTS=["g1.play.20tb"];', "var PRODUCTS=" + json.dumps(part) + ";", 1)
        got = []
        done = threading.Event()

        def on_msg(m, _d):
            p = m.get("payload") or {}
            ev = p.get("ev")
            if ev == "offer":
                got.append(p)
            elif ev in ("no_trial", "list_only", "query_err", "boot_err", "boot_fail"):
                done.set()

        sc = sess.create_script(js)
        sc.on("message", on_msg)
        sc.load()
        done.wait(timeout=12)
        time.sleep(0.3)
        try:
            sc.unload()
        except Exception:
            pass
        print(f"  Lote {idx}: {len(part)} consultados → {len(got)} ofertas devueltas", flush=True)
        return got

    for i in range(0, len(skus), CHUNK):
        all_offers.extend(scan_chunk(skus[i:i + CHUNK], i // CHUNK + 1))
        time.sleep(0.5)

    # ---- Resumen ----
    def fmt(micros):
        try:
            m = int(micros)
            return "Gratis $0" if m == 0 else f"${m / 1e6:.2f}"
        except Exception:
            return str(micros)

    print("\n" + "=" * 70 + "\nOfertas gratuitas (micros == 0):\n" + "=" * 70, flush=True)
    dedup = {}
    for o in all_offers:
        if str(o.get("micros")) == "0":
            dedup[(o.get("product"), o.get("id"), o.get("token"))] = o
    if not dedup:
        print("  (No se encontró ninguna oferta gratuita de $0)", flush=True)
    for (prod, oid, tok), o in sorted(dedup.items(), key=lambda x: str(x[0][0])):
        print(f"  {prod:28s} offer={str(oid):20s} period={o.get('period')}", flush=True)
        print(f"      token={tok}", flush=True)

    print("\n" + "=" * 70 + "\nTodos los productos devueltos (incluidos precios estándar):\n" + "=" * 70, flush=True)
    prods = {}
    for o in all_offers:
        prods.setdefault(o.get("product"), []).append(o)
    for p in sorted(prods.keys(), key=str):
        lst = prods[p]
        f = sum(1 for x in lst if str(x.get("micros")) == "0")
        prices = sorted({fmt(x.get("micros")) for x in lst if int(x.get("micros", -1)) > 0})
        print(f"  {p:30s} ofertas={len(lst)} gratis={f} pago={','.join(prices) if prices else '-'}", flush=True)

    out = Path(__file__).parent / "scan_result.json"
    out.write_text(json.dumps(all_offers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Detalle guardado en {out}", flush=True)


if __name__ == "__main__":
    main()
