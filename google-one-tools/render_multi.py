# -*- coding: utf-8 -*-
"""
render_multi.py —— Combina resultados de escaneo multirregión: una fila por SKU con importes por país

Lee scan_result_{gb,us,hk,tr,in}.json
Genera SKU-清单.md
"""
import json
import time
from pathlib import Path

import scan_everything as se

HERE = Path(__file__).parent
DOC = HERE / "SKU-清单.md"

REGIONS = [("GB", "scan_result_gb.json"), ("US", "scan_result_us.json"),
           ("HK", "scan_result_hk.json"), ("TR", "scan_result_tr.json"),
           ("IN", "scan_result_in.json")]


def load():
    out = {}
    for tag, fn in REGIONS:
        p = HERE / fn
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out[tag] = d
    return out


def split(offers):
    """Devuelve (trials, intros, base):
       trials/intros: {(sku, oid): row}; base: {sku: row}"""
    trials, intros, base = {}, {}, {}
    for o in offers:
        ph = o.get("phases") or []
        if not ph:
            continue
        oid = "" if o.get("id") in (None, "null", "None") else str(o.get("id"))
        sku = o.get("product")
        title = o.get("title", "")
        row = {"sku": sku, "title": title, "oid": oid, "ph": ph}
        if len(ph) > 1 and ph[0].get("free"):
            trials[(sku, oid)] = row
        elif oid and len(ph) > 1:
            intros[(sku, oid)] = row
        else:
            base.setdefault(sku, row)
    return trials, intros, base


def short_name(title):
    """Google AI Pro (5 TB) (Google One) → Google AI Pro 5TB"""
    t = (title or "").replace("(Google One)", "").strip()
    t = t.replace("(Google One)", "")
    t = t.replace("(", "").replace(")", "")
    return " ".join(t.split())


def cell_price(row, idx=0):
    if not row:
        return "-"
    ph = row["ph"][idx] if len(row["ph"]) > idx else row["ph"][0]
    return se.money(ph.get("micros"), ph.get("cur")) or "-"


def main():
    data = load()
    parsed = {tag: split(d["offers"]) for tag, d in data.items()}
    heads = " | ".join(t for t, _ in REGIONS)
    div = "---|" * len(REGIONS)

    L = ["# Lista de SKUs de suscripción Google One / AI (comparativa multirregión)", ""]

    # Resumen
    L += ["| Región | Dispositivo | Fecha de escaneo | SKUs disponibles | Pruebas gratis |", "|---|---|---|---|---|"]
    for tag, d in data.items():
        tr, it, base = parsed[tag]
        L.append(f"| {tag} | `{se.mask_serial(d.get('serial',''))}` | {d.get('at','')} | "
                 f"{len(set(base) | {k[0] for k in tr} | {k[0] for k in it})} | {len(tr)} |")

    # 1. Pruebas gratuitas
    L += ["", "## 1. Planes con prueba gratuita", "",
          "> Celda = precio de renovación mensual tras la prueba; `-` = no disponible en esa región.", "",
          f"| SKU | Nombre | offerId | Duración | {heads} |", f"|---|---|---|---|{div}"]
    keys = sorted({k for tag in parsed for k in parsed[tag][0]})
    for key in keys:
        rows = {tag: parsed[tag][0].get(key) for tag in parsed}
        sample = next(r for r in rows.values() if r)
        dur = se.period_cn(sample["ph"][0].get("period"))
        cells = " | ".join(cell_price(rows[tag], 1) for tag, _ in REGIONS)
        L.append(f"| `{key[0]}` | {short_name(sample['title'])} | `{key[1]}` | {dur} | {cells} |")

    # 2. Precios iniciales
    L += ["", "## 2. Ofertas iniciales (introprice)", "",
          "> Celda = precio promocional/período (durante N ciclos) → precio regular posterior.", "",
          f"| SKU | Nombre | offerId | Ciclos | {heads} |", f"|---|---|---|---|{div}"]
    keys = sorted({k for tag in parsed for k in parsed[tag][1]})
    for key in keys:
        rows = {tag: parsed[tag][1].get(key) for tag in parsed}
        sample = next(r for r in rows.values() if r)
        cyc = sample["ph"][0].get("cycles")
        cells = []
        for tag, _ in REGIONS:
            r = rows[tag]
            if not r:
                cells.append("-")
            else:
                first = se.money(r["ph"][0].get("micros"), r["ph"][0].get("cur"))
                nxt = se.money(r["ph"][1].get("micros"), r["ph"][1].get("cur")) if len(r["ph"]) > 1 else "-"
                cells.append(f"{first} → {nxt}")
        L.append(f"| `{key[0]}` | {short_name(sample['title'])} | `{key[1]}` | {cyc} ciclos | " + " | ".join(cells) + " |")

    # 3. Precio estándar
    L += ["", "## 3. Suscripciones a precio estándar", "",
          f"| SKU | Nombre | Período | {heads} |", f"|---|---|---|{div}"]
    skus = sorted({s for tag in parsed for s in parsed[tag][2]})
    for sku in skus:
        rows = {tag: parsed[tag][2].get(sku) for tag in parsed}
        sample = next(r for r in rows.values() if r)
        period = sample["ph"][0].get("period", "")
        cells = " | ".join(cell_price(rows[tag]) for tag, _ in REGIONS)
        L.append(f"| `{sku}` | {short_name(sample['title'])} | {period} | {cells} |")

    # Notas / Reglas
    L += ["", "## 4. Notas", "",
          "- **Prueba gratuita**: sin cobro si cancelas antes de que termine; de lo contrario, se renueva mensualmente al precio indicado.",
          "- **Precio inicial**: aplica durante N ciclos y luego pasa al precio regular.",
          "- Cada oferta suele tener un solo intento de prueba; abrir `launchBillingFlow` puede consumir la elegibilidad.",
          "- Términos: `eft` = prueba gratuita, `subs_variant` = variante de suscripción, `_ip_85p.acq` = oferta de captación 85% off, "
          "`g1.play.*` = familia promocional Play; etiquetas `genai` = incluye IA, `helium` = línea Helium.",
          "- Períodos: `P1M` = 1 mes, `P4W3D` = 31 días, `P3M` = 3 meses, `P13W1D` = 92 días, `P6M` = 6 meses, "
          "`P26W2D` = 184 días, `P1Y` = 12 meses.",
          f"- Fecha de generación: {time.strftime('%Y-%m-%d %H:%M')}", ""]

    DOC.write_text("\n".join(L), encoding="utf-8")
    print(f"Escrito {DOC} ({len(L)} líneas)")


if __name__ == "__main__":
    main()
