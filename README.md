# GEMINI ONE PORTABLE

GEMINI ONE PORTABLE es un entorno portátil para Windows diseñado para probar y administrar herramientas relacionadas con Google One dentro de LDPlayer.

El paquete incluye Python 3.11 portátil, Frida 16.7.19, herramientas ADB y scripts listados para diagnóstico, exploración de ofertas y consulta de servicios compatibles.

## Compatibilidad

- Emulador recomendado: LDPlayer 9.
- Android: 9 o superior en arquitectura de 64 bits.
- Requiere activación de **ADB**, modo **root** y Google Play Store.
- Debes iniciar sesión en una cuenta de Google y tener instalada la aplicación Google One.
- LDPlayer 4 y LDPlayer 5 usan Android 7.1 y no son compatibles con estos requisitos.

## Funciones principales

- Diagnosticar la conexión entre Windows y LDPlayer.
- Preparar el entorno de ADB y Frida.
- Comprobar la compatibilidad de Frida y Google Play.
- Escanear ofertas disponibles asociadas a Google One.
- Consultar SKUs y regiones configuradas.
- Mostrar información de precios y fases de suscripción.
- Ejecutar herramientas sin instalar Python ni Frida de forma global en Windows.

## Requisitos

1. Windows.
2. LDPlayer con Android 9 o superior.
3. Arquitectura de Android de 64 bits.
4. Depuración ADB habilitada.
5. Permiso root habilitado.
6. Google Play Store instalado y actualizado.
7. Aplicación Google One instalada.
8. Una cuenta de Google iniciada en el emulador.

## Inicio rápido

1. Descomprime toda la carpeta `GEMINI-ONE-PORTABLE` sin mover sus archivos.
2. Activa el acceso root y la depuración ADB en LDPlayer.
3. Reinicia LDPlayer.
4. Ejecuta `INICIAR.bat`.
5. Selecciona la opción de diagnóstico.
6. Continúa solo si el programa confirma que el entorno está funcionando correctamente.

## Advertencia

Este proyecto se ofrece con fines educativos y de investigación. El usuario debe respetar los términos de servicio de Google, los acuerdos de la plataforma y la legislación aplicable. No contiene credenciales propias ni debe utilizarse para eludir controles, pagos, suscripciones o restricciones de servicios.
