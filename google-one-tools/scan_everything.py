# -*- coding: utf-8 -*-
"""
scan_everything.py —— Enumera todos los SKUs de Google One de la cuenta y genera la lista explicativa

① Descubrimiento: busca literales de SKU en el directorio de datos del dispositivo (root)
② Combinación: capacidades × sufijos + familias play/ai
③ Verificación: scan_offers.js consulta las ofertas y fases completas de cada SKU
④ Renderizado: SKU-清单.md (detalla qué incluye cada prueba o promo, cuánto dura y cuánto cuesta después)

Uso:
  .\\.venv\\Scripts\\python.exe scan_everything.py emulator-5554
  .\\.venv\\Scripts\\python.exe scan_everything.py --render-only
"""
import argparse
import json
import re
import subprocess
import threading
import time
from pathlib import Path

import one_common

ultra0 = one_common.ultra0

HERE = Path(__file__).parent


def mask_serial(s):
    """Enmascara el número de serie al guardar JSON o renderizar: 127.0.0.1:5555 → 127.0.0.1:****."""
    s = str(s or "")
    if not s:
        return ""
    if ":" in s:                      # adb por TCP: conserva el host y oculta el puerto
        return s.rpartition(":")[0] + ":****"
    return (s[:4] + "****") if len(s) > 4 else "****"


def json_path_for(tag):
    return HERE / (f"scan_result_{tag}.json" if tag else "scan_result_all.json")


JSON_PATH = HERE / "scan_result_all.json"
DOC_PATH = HERE / "SKU-清单.md"
CHUNK = 18

SIZES = ["30gb", "100gb", "200gb", "2tb", "5tb", "10tb", "20tb", "30tb", "helium"]
SUFFIXES = ["", ".annual", ".v2", ".ai", ".ai.annual", ".ai.subs_variant", ".subs_variant",
            ".1month_eft", ".3months_eft", ".6months_eft", ".12months_eft",
            ".3months_ip_85p.acq", ".3months_ip_75p.acq", ".3months_ip_83p.acq"]
PLAY_EXTRA = ["g1.play", "g1.play.ai", "g1.play.ai.pro", "g1.play.ai.plus", "g1.play.ai.ultra",
              "g1.play.pro", "g1.play.plus", "g1.play.home", "g1.play.health", "g1.play.helium",
              "g1.play.2tb", "g1.play.5tb", "g1.play.20tb", "g1.play.30tb"]
PLAY_MONTHS = [f"g1.play.{s}.{m}" for s in ("2tb", "5tb", "10tb", "20tb", "30tb")
               for m in ("1month", "3month", "6month", "12month")]
AI_EXTRA = ["g1.ai", "g1.ai.pro", "g1.ai.plus", "g1.ai.ultra",
            "g1.ai.pro.annual", "g1.ai.ultra.annual", "g1.ai.pro.subs_variant",
            "g1.ai.ultra.subs_variant", "g1.ai.plus.subs_variant"]
ADDONS = ["g1.youtube_premium_individual_add_on", "g1.youtube_premium_family_add_on",
          "g1.home_premium", "g1.health_premium", "g1.pro", "g1.plus", "g1.premium",
          "g1.ultra", "g1.ultra.20tb", "g1.ultra.30tb"]

PATTERN = r'g1\.[a-z0-9]{1,12}(\.[a-z0-9_-]{2,30}){0,4}'

# Capacidad → Nombre legible
CAP = {"30gb": "30 GB", "100gb": "100 GB", "200gb": "200 GB", "2tb": "2 TB", "5tb": "5 TB",
       "10tb": "10 TB", "20tb": "20 TB", "30tb": "30 TB", "helium": "Helium"}


# ---------- Utilidades ----------
def period_days(p):
    """Convierte un período ISO-8601 a días (P1Y/P6M/P13W1D/P4W3D…)."""
    m = re.fullmatch(r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?", str(p or ""))
    if not m:
        return None
    y, mo, w, d = (int(x) if x else 0 for x in m.groups())
    return y * 365 + mo * 30 + w * 7 + d


def period_cn(p):
    """Convierte el período a duración legible en español (con días)."""
    d = period_days(p)
    if d is None:
        return str(p)
    if d >= 360 and d % 365 < 10:
        n = round(d / 365)
        return f"{n} {'año' if n == 1 else 'años'} ({d} días)"
    if d % 30 == 0:
        n = d // 30
        return f"{n} {'mes' if n == 1 else 'meses'} ({d} días)"
    if d % 7 == 0:
        n = d // 7
        return f"{n} {'semana' if n == 1 else 'semanas'} ({d} días)"
    return f"{d} días"


def money(micros, cur=""):
    try:
        m = int(micros) / 1e6
    except Exception:
        return ""
    s = f"{m:,.2f}"
    return f"{s} {cur}" if cur else s


def cap_of(sku, title=""):
    """Capacidad: prioriza el título del checkout y si no lo deduce del SKU."""
    m = re.search(r"\((\d+(?:\.\d+)?\s*(?:GB|TB))\)", title or "")
    if m:
        return m.group(1).replace(" ", "")
    body = sku[3:] if sku.startswith("g1.") else sku
    for k in CAP:
        if body == k or body.startswith(k + "."):
            return CAP[k]
    return ""


def describe(sku, oid, phases):
    """Genera una descripción legible para una oferta."""
    if not phases:
        return ""
    first = phases[0]
    typ = "trial" if len(phases) > 1 and first.get("free") else ("free" if first.get("free") else "paid")
    if typ == "trial":
        nxt = phases[1] if len(phases) > 1 else {}
        return (f"**Prueba gratuita**: primeros {period_cn(first.get('period'))} a 0, "
                f"luego se renueva automáticamente a {money(nxt.get('micros'), nxt.get('cur'))}/período (cancela antes de finalizar)")
    if typ == "free":
        return "**Gratis completo** (sin fase de cobro posterior)"
    # Precio introductorio
    if oid and oid.lower() != "null" and len(phases) > 1:
        cycles = first.get("cycles") or 0
        nxt = phases[1]
        return (f"**Oferta inicial**: primeros {cycles or '?'} ciclos a {money(first.get('micros'), first.get('cur'))}, "
                f"luego vuelve a {money(nxt.get('micros'), nxt.get('cur'))}/período")
    return "Suscripción estándar (sin descuento ni prueba)"


# ---------- Descubrimiento / Escaneo ----------
def discover_from_device():
    found = set()
    for path in ("/data/data/com.google.android.apps.subscriptions.red",
                 "/data/data/com.android.vending/databases"):
        cmd = [ultra0.ADB, "-s", ultra0.SERIAL, "shell",
               f"su -c \"grep -a -r -o -E '{PATTERN}' {path} | sed 's/.*://' | sort -u\""]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            for line in r.stdout.decode("utf-8", "ignore").splitlines():
                line = line.strip()
                if re.fullmatch(PATTERN, line):
                    found.add(line)
        except Exception as e:
            print(f"  Error al descubrir en {path}: {e}", flush=True)
    return found


def build_candidates(discovered):
    gen = set(discovered)
    for s in SIZES:
        for suf in SUFFIXES:
            gen.add(f"g1.{s}{suf}")
    gen.update(PLAY_EXTRA)
    gen.update(PLAY_MONTHS)
    gen.update(AI_EXTRA)
    gen.update(ADDONS)
    return sorted(gen)


def scan_skus(skus):
    pid = ultra0.launch_app()
    print("GOOGLE_ONE_PID =", pid, flush=True)
    if not pid:
        raise SystemExit("Google One no pudo iniciar")

    import frida
    dev = frida.get_device(ultra0.SERIAL, timeout=10)
    sess = dev.attach(pid)
    template = (HERE / "scan_offers.js").read_text(encoding="utf-8")
    offers = []

    def scan_chunk(part, idx):
        js = template.replace("var PRODUCTS = [];",
                              "var PRODUCTS = " + json.dumps(part) + ";", 1)
        got, done = [], threading.Event()

        def on_msg(m, _d):
            p = m.get("payload") or {}
            ev = p.get("ev")
            if ev == "offer":
                got.append(p)
            elif ev in ("done", "query_err", "setup") and (ev != "setup" or p.get("code")):
                if ev != "setup":
                    done.set()

        sc = sess.create_script(js)
        sc.on("message", on_msg)
        sc.load()
        done.wait(timeout=15)
        time.sleep(0.3)
        try:
            sc.unload()
        except Exception:
            pass
        print(f"   Lote {idx}: {len(part)} SKUs → {len(got)} resultados", flush=True)
        return got

    for i in range(0, len(skus), CHUNK):
        offers.extend(scan_chunk(skus[i:i + CHUNK], i // CHUNK + 1))
        time.sleep(0.4)
    return offers


# ---------- Renderizado ----------
def render_doc(offers, candidates_count, serial, scanned_at):
    trials, intros, paid = {}, {}, {}
    for o in offers:
        prod, oid = o.get("product"), o.get("id")
        phases = o.get("phases") or []
        if not phases:
            continue
        oid_s = "" if oid in (None, "null", "None") else str(oid)
        first = phases[0]
        is_trial = len(phases) > 1 and first.get("free")
        is_intro = bool(oid_s) and not first.get("free") and len(phases) > 1
        key = (prod, oid_s)
        row = {
            "sku": prod, "title": o.get("title", ""), "oid": oid_s,
            "cap": cap_of(prod, o.get("title", "")), "tags": o.get("tags", ""), "phases": phases,
        }
        if is_trial:
            trials[key] = row
        elif is_intro:
            intros[key] = row
        else:
            paid.setdefault(prod, []).append(row)

    listed = {p for p, _ in trials} | {p for p, _ in intros} | set(paid)

    L = ["# Lista de SKUs de suscripción Google One / AI", "",
         f"> Dispositivo `{serial}`, fecha de escaneo {scanned_at}; probados {candidates_count} candidatos, "
         f"disponibles {len(listed)} SKUs. Precios en la moneda local de la región de Play de la cuenta.", ""]

    # ---- 1. Pruebas gratuitas ----
    L += ["## 1. Planes con prueba gratuita", "",
          "> «Duración» = duración de la fase a costo 0; «Al finalizar» = precio de renovación automática si no se cancela antes.",
          "",
          "| SKU | Nombre en checkout | Capacidad | offerId | Etiquetas | Duración | Al finalizar |",
          "|---|---|---|---|---|---|---|"]
    for (prod, oid), r in sorted(trials.items()):
        ph = r["phases"]
        nxt = ph[1] if len(ph) > 1 else {}
        L.append(f"| `{prod}` | {r['title'] or '-'} | {r['cap'] or '-'} | `{oid}` | "
                 f"{r['tags'] or '-'} | {period_cn(ph[0].get('period'))} | "
                 f"{money(nxt.get('micros'), nxt.get('cur'))}/período |")

    # ---- 2. Ofertas iniciales (introprice) ----
    L += ["", "## 2. Ofertas con precio inicial (introprice)", "",
          "> «Precio inicial» = importe por ciclo durante los primeros N ciclos; «Precio normal» = tarifa regular posterior.",
          "",
          "| SKU | Nombre en checkout | Capacidad | offerId | Precio inicial | Ciclos | Precio normal |",
          "|---|---|---|---|---|---|---|"]
    for (prod, oid), r in sorted(intros.items()):
        ph = r["phases"]
        nxt = ph[1] if len(ph) > 1 else {}
        L.append(f"| `{prod}` | {r['title'] or '-'} | {r['cap'] or '-'} | `{oid}` | "
                 f"{money(ph[0].get('micros'), ph[0].get('cur'))}/período | {ph[0].get('cycles')} ciclos | "
                 f"{money(nxt.get('micros'), nxt.get('cur'))}/período |")

    # ---- 3. Precio estándar ----
    L += ["", "## 3. Suscripciones a precio estándar", "", "| SKU | Nombre en checkout | Capacidad | Período | Precio |",
          "|---|---|---|---|---|"]
    for prod in sorted(paid):
        for r in paid[prod]:
            ph = r["phases"][0]
            L.append(f"| `{prod}` | {r['title'] or '-'} | {r['cap'] or '-'} | "
                     f"{ph.get('period')} | {money(ph.get('micros'), ph.get('cur'))} |")

    # ---- 4. Glosario ----
    L += ["", "## 4. Glosario de términos", "",
          "| Fragmento | Significado |", "|---|---|",
          "| `eft` / `freetrial` | Prueba gratuita (free trial). `12months-eft` = 12 meses, `eft-3mo` = 3 meses |",
          "| `subs_variant` | Variante de suscripción donde suelen publicarse pruebas y promociones |",
          "| `.1month_eft` / `.3months_eft` / `.6months_eft` / `.12months_eft` | SKUs específicos por duración de prueba |",
          "| `_ip_85p.acq` | Precio inicial con 85% de descuento de captación durante los primeros ciclos |",
          "| `_ip_75p` / `_ip_83p` | Igual que el anterior, con 75% y 83% de descuento respectivamente |",
          "| `g1.play.*` | Familia promocional de Play (la mayoría de las pruebas gratis están aquí) |",
          "| `youtube_premium_*` / `home_premium` / `health_premium` | Complementos adicionales (no son planes de almacenamiento) |",
          "",
          "### Etiquetas de oferta (tags)",
          "",
          "| Etiqueta | Significado |",
          "|---|---|",
          "| `eft` | Oferta de prueba gratuita |",
          "| `promotional` | Oferta promocional (prueba o descuento inicial) |",
          "| `play` | Grupo promocional del canal Play |",
          "| `genai` | Nuevo plan con funciones de IA (como Gemini) |",
          "| `helium` | Línea de planes Helium (AI Plus de menor capacidad) |",
          "| `intro-pricing` | Precio promocional inicial (intro price) |",
          "",
          "## 5. Equivalencia de períodos", "",
          "| Campo | Días | Equivalencia |",
          "|---|---|---|",
          "| `P1M` | 30 | 1 mes |",
          "| `P4W3D` | 31 | ~1 mes (4 semanas y 3 días) |",
          "| `P3M` | 90 | 3 meses |",
          "| `P13W1D` | 92 | 3 meses (13 semanas y 1 día) |",
          "| `P6M` | 180 | 6 meses |",
          "| `P26W2D` | 184 | 6 meses (26 semanas y 2 días) |",
          "| `P1Y` | 365 | 12 meses (1 año) |",
          "",
          "## 6. Reglas y avisos", "",
          "- Costo 0 durante la prueba: **si cancelas antes de que termine no se cobra**; de lo contrario, se renovará automáticamente al precio indicado.",
          "- En precios iniciales, se cobra el descuento durante los ciclos indicados y luego vuelve al precio regular.",
          "- Requisitos: la cuenta **no debe tener otra suscripción similar activa** y debe contar con un método de pago válido; `launchBillingFlow` puede consumir la elegibilidad de prueba con solo abrirse.",
          "- Los tokens gratuitos son por dispositivo; el checkout final confirma si la cuenta es elegible.",
          ""]

    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Escanea todos los SKUs de Google One y genera el documento resumen")
    ap.add_argument("serial", nargs="?", help="Serie del dispositivo")
    ap.add_argument("--render-only", action="store_true", help="Solo regenerar el markdown desde scan_result_all.json")
    ap.add_argument("--tag", default="", help="Etiqueta de región, ej. us/hk/gb, para nombrar el JSON")
    ap.add_argument("--json-only", action="store_true", help="Guardar solo el JSON sin renderizar markdown")
    args = ap.parse_args()

    if args.render_only:
        d = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        offers = d["offers"] if isinstance(d, dict) else d
        cand = d.get("candidates", 0) if isinstance(d, dict) else 0
        ser = d.get("serial", "") if isinstance(d, dict) else ""
        at = d.get("at", "") if isinstance(d, dict) else ""
        DOC_PATH.write_text(render_doc(offers, cand, ser, at), encoding="utf-8")
        print(f"Reescrito {DOC_PATH} ({len(offers)} ofertas)", flush=True)
        return

    one_common.setup(serial=args.serial)
    if not one_common.ensure_vending():
        one_common.reboot_and_recover()

    print("① Descubriendo SKUs en el dispositivo…", flush=True)
    discovered = discover_from_device()
    print(f"   {len(discovered)} encontrados", flush=True)

    print("② Generando candidatos…", flush=True)
    skus = build_candidates(discovered)
    print(f"   Total: {len(skus)}", flush=True)

    print("③ Verificando…", flush=True)
    offers = scan_skus(skus)
    if not offers:
        raise SystemExit("Sin respuestas — error en facturación, no se sobrescribió el documento")

    at = time.strftime("%Y-%m-%d %H:%M")
    jpath = json_path_for(args.tag)
    jpath.write_text(json.dumps(
        {"serial": mask_serial(ultra0.SERIAL), "tag": args.tag, "candidates": len(skus),
         "at": at, "offers": offers},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON guardado en {jpath} ({len(offers)} ofertas)", flush=True)
    if args.json_only:
        return
    DOC_PATH.write_text(render_doc(offers, len(skus), mask_serial(ultra0.SERIAL), at), encoding="utf-8")
    print(f"\nListo: {len(offers)} ofertas escritas en {DOC_PATH}", flush=True)


if __name__ == "__main__":
    main()
