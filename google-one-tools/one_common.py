# -*- coding: utf-8 -*-
"""
one_common.py —— Preparación común del entorno (importado por todos los scripts)

Tareas (en orden):
  1. Buscar adb y elegir el dispositivo destino (soporta múltiples instancias por parámetro o variable SERIAL)
  2. Asegurar permisos root (compatible con adb root en MuMu y su -c en LDPlayer)
  3. Asegurar que frida-server esté corriendo en el dispositivo (descarga automática según la versión local)
  4. Asegurar que el módulo de facturación module_521.apk esté copiado
  5. Asegurar que Play Store esté en ejecución (★clave★: si Play Store no está activo,
     BillingClient nunca invoca setup/queryProductDetails)

Lo que NO toca intencionalmente (compatible con VPN):
  —— No llama a ultra0.ensure_network(): no borra proxy ni cierra Clash/VPN
  —— No hace force-stop de Play Store (el servicio de cobro vive ahí)

Dependencias:
  —— ultra0_core.py (núcleo autónomo)
  —— frida==16.x en el entorno virtual (la 17.x rompe el puente Java en Android 12 / x86_64)
"""
import os
import subprocess
import sys
import time

# Núcleo autónomo sin dependencias externas
import ultra0_core as ultra0  # noqa: E402

VENDING = "com.android.vending"                       # Google Play Store
GOOGLE_ONE = "com.google.android.apps.subscriptions.red"


def setup(serial: str | None = None):
    """Prepara el entorno automáticamente. Ej. serial='emulator-5554'; None=selecciona el primero."""
    ultra0.ADB = ultra0.find_adb()
    ultra0.pick_device()
    # pick_device elige el primer dispositivo; para múltiples instancias usa parámetro o variable SERIAL
    if serial is None:
        serial = os.environ.get("SERIAL")
    if serial:
        ultra0.SERIAL = serial
    print(f"TARGET_DEVICE = {ultra0.SERIAL}", flush=True)

    ensure_root_retry()
    ultra0.ensure_frida_server()
    ultra0.ensure_module_apk()
    # ensure_vending() lo invoca cada script según corresponda
    return ultra0.SERIAL


def _adb(*args, timeout=15):
    """Llamada directa a adb (sin ultra0.sh, para root o reconexión)."""
    cmd = [ultra0.ADB, "-s", ultra0.SERIAL] + list(args)
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _reconnect():
    """Reintenta conectar adb tras reiniciar adbd o el emulador."""
    try:
        _adb("connect", ultra0.SERIAL, timeout=8)
    except Exception:
        pass


def ensure_root_retry():
    """Asegura permisos root en el dispositivo.

    Reintenta adb root + reconexión para MuMu tras reiniciar, y también detecta
    inmediatamente `su -c` en emuladores como LDPlayer sin esperar timeouts innecesarios.
    """
    for attempt in range(3):
        try:
            uid = ultra0.sh("shell", "id", timeout=10)
            if "uid=0" in uid:
                ultra0.ok(f"root listo (intento {attempt + 1})")
                return
            su_uid = ultra0.sh("shell", "su -c id", timeout=10)
            if "uid=0" in su_uid:
                ultra0.ok("root listo (su -c)")
                return
        except Exception:
            pass
        # Intenta adb root (adbd puede desconectarse un momento al reiniciar)
        try:
            _adb("root", timeout=20)
        except Exception:
            pass
        time.sleep(3)
        _reconnect()
        time.sleep(2)
    # Último respaldo con el flujo completo de ultra0 (incluye salida con error)
    ultra0.ensure_root()


def ensure_vending():
    """Mantiene Play Store en ejecución (★condición crítica para abrir el checkout★).

    El servicio de facturación de BillingClient se aloja en el proceso de Play Store;
    si no está activo, onBillingSetupFinished nunca responde y no llega el evento launched.
    """
    if ultra0.sh("shell", f"pidof {VENDING}"):
        ultra0.ok("Play Store en ejecución")
        return True
    ultra0.warn("Play Store no está corriendo, iniciando…")
    try:
        ultra0.sh("shell", f"monkey -p {VENDING} -c android.intent.category.LAUNCHER 1", timeout=30)
    except Exception as e:
        ultra0.warn(f"Error al iniciar con monkey: {e}")
    for _ in range(20):
        time.sleep(1)
        if ultra0.sh("shell", f"pidof {VENDING}"):
            ultra0.ok("Play Store iniciado")
            time.sleep(2)  # Espera a que enlace el servicio de facturación
            return True
    ultra0.warn("Play Store no inició — si aparece repetidamente 'failed to attach / start timeout', "
                "está bloqueado; reinicia el emulador: adb -s <serial> reboot")
    return False


def reboot_and_recover():
    """Recuperación automática si Play Store está congelado: reinicia dispositivo → espera boot → abre Play Store."""
    ultra0.warn("Reiniciando emulador para recuperar Play Store…")
    try:
        _adb("reboot", timeout=20)
    except Exception:
        pass
    # Esperar a que vuelva el dispositivo
    for _ in range(60):
        time.sleep(5)
        try:
            r = _adb("shell", "getprop sys.boot_completed", timeout=8)
            if r.stdout.decode(errors="ignore").strip() == "1":
                break
        except Exception:
            continue
    time.sleep(20)          # Esperar servicios del sistema
    _reconnect()
    ensure_root_retry()
    ultra0.ensure_frida_server()
    ultra0.ensure_module_apk()
    time.sleep(5)
    return ensure_vending()
