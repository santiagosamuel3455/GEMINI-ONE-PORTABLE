# -*- coding: utf-8 -*-
"""
probe_env.py —— Diagnóstico del entorno: conectividad de frida + puente Java + estado de Play Store

Uso: Ejecútalo primero si falla la apertura del checkout o no se encuentran ofertas.

Comandos:
    .\\.venv\\Scripts\\python.exe probe_env.py                  # Selecciona dispositivo automáticamente
    .\\.venv\\Scripts\\python.exe probe_env.py emulator-5554    # Especifica instancia

Interpretación:
    Versión de frida  Debe ser 16.x (la 17.x rompe el puente Java en Android 12 / x86_64)
    hasJava=false     Puente Java no disponible → revisa que coincidan las versiones de frida
    vmOk=true         Inyección y Java.perform funcionando correctamente
    Proceso vending   Debe estar en ejecución; si no, BillingClient nunca responderá
"""
import argparse
import json

import one_common
ultra0 = one_common.ultra0  # Núcleo autónomo (ver ultra0_core.py)
PROBE_JS = r"""
rpc.exports.probe = function () {
  var out = { hasJava: (typeof Java !== 'undefined'), avail: null, version: null,
              vmOk: false, err: null };
  if (typeof Java !== 'undefined') {
    try {
      out.avail = Java.available;
      Java.perform(function () { out.vmOk = true; });
    } catch (e) { out.err = String(e); }
  }
  return out;
};
"""


def main():
    ap = argparse.ArgumentParser(description="Diagnóstico de frida, puente Java y Play Store")
    ap.add_argument("serial", nargs="?", help="Número de serie del dispositivo (ej. emulator-5554)")
    args = ap.parse_args()

    import frida
    print(f"Versión local de frida = {frida.__version__}"
          + ("   ✅ 16.x correcto" if frida.__version__.startswith("16") else "   ❌ ¡No es 16.x! Se requiere pip install frida==16.7.19")
          , flush=True)

    one_common.setup(serial=args.serial)

    vending = ultra0.sh("shell", "pidof com.android.vending")
    print(f"Proceso de Play Store = {vending or 'no existe'}"
          + ("   ❌ No está activo, BillingClient no responderá (ejecuta ensure_vending o reinicia el emulador)" if not vending else "   ✅")
          , flush=True)

    pid = ultra0.launch_app()
    print("GOOGLE_ONE_PID =", pid, flush=True)
    if not pid:
        raise SystemExit("Google One no pudo iniciar")

    dev = frida.get_device(ultra0.SERIAL, timeout=10)
    sess = dev.attach(pid)
    sc = sess.create_script(PROBE_JS)
    sc.load()
    r = sc.exports_sync.probe()
    print("Prueba de puente Java:", json.dumps(r, ensure_ascii=False), flush=True)
    if r.get("vmOk"):
        print("✅ Cadena de inyección funcionando; ya puedes ejecutar los scripts de escaneo o checkout", flush=True)
    else:
        print("❌ Puente Java no disponible — casi seguro por versión incompatible de frida "
              "(usa 16.x y elimina /data/local/tmp/frida-server en el emulador para que se descargue la versión correcta)", flush=True)


if __name__ == "__main__":
    main()
