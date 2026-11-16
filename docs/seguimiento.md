# Seguimiento del caso real

Sesión del **16 de noviembre de 2026**. Lenovo TAB 2 A8-50F-YZ-A, Android 5.1/API 22, 1 GB de RAM y kernel 3.10.65. Adaptador informado: MAXOBD OBD2 Scanner. Vehículo: Nissan Sentra 2019. Se omiten VIN, MAC, números de serie, cuentas y códigos del escáner.

## Arranque y versiones

MAXOBD 1.0.30 tenía solo el base. Faltaban el split gráfico con el recurso `0x7f070105` compatible con Android 5 y las bibliotecas ARM64. Instalar los tres APK originales juntos con `install-multiple -r` conservó datos y permitió abrir la app. El [diagnóstico original](diagnostico.md) corresponde a ese momento, antes del vehículo.

Después se probaron 1.0.30/ARM64 y 1.1.01/ARM64 y ARM32. La instalación final quedó en **1.1.01/código 57, armeabi-v7a + hdpi**. El usuario la percibió más ágil, pero hubo nuevos cierres. El base de las variantes 1.1.01 era idéntico; los componentes de cada conjunto tenían certificado observado coincidente. No se mezclaron ediciones ni se modificaron firmas.

1.0.29 se inspeccionó y no se instaló. Un intento de `adb backup` produjo cero bytes: no es un respaldo válido. Sí se guardaron archivos externos antes de las intervenciones sobre paquetes. El conjunto 1.1.04 examinado exige API 24 y no se instaló en API 22. No se modificó el firmware, el bootloader ni root.

## Cierre interno pendiente

Fragmento mínimo sin identificadores:

```text
JNI ERROR (app bug): local reference table overflow (max=512)
Fatal signal 6 (SIGABRT), pool-4-thread-1
```

Se observó también después de que Nissan reconociera sus archivos. Es diferente del recurso gráfico ausente y de la descarga fallida. No se corrigió con el cambio de ABI o la copia de datos. A petición del usuario se dejó su investigación y se continuó con los paquetes; no se modificaron bibliotecas nativas o protecciones.

## Nissan recuperado

La petición real al catálogo y sus objetos estaban disponibles. Se recuperaron 23 archivos aplicables al español, **14.731.534 bytes**, y se copiaron a `nissan/folder` y `nissan/es` en el directorio externo. Se recuperaron desde la tableta para comparar sus bytes: **23/23 idénticos**. MAXOBD abrió el menú Nissan / NISSAN GT-R y el usuario confirmó que funcionaba.

## Resto de los paquetes

Se recuperaron **19 grupos / 2.875 archivos / 907.211.045 bytes**, con español cuando existe, archivos comunes, regiones Toyota separadas y ambos idiomas disponibles para VAZ. Los tiempos de espera de Mazda y VW se resolvieron por bloques y las huellas coincidieron.

Antes de la copia se respaldaron 40 archivos externos previos, unos 29,5 MB. Se cerró MAXOBD durante la transferencia por ADB.

| Comprobación | Resultado |
|---|---:|
| Originales en computadora: tamaño, MD5 y SHA-256 | 2.875/2.875 |
| Archivos presentes en tableta | 2.875/2.875 |
| Tamaños en tableta | 2.875/2.875 |
| Muestras MD5 recuperadas, una por grupo | 19/19 |

Se abrió la app y se guardaron capturas. Una selección de BMW llegó al diálogo de comunicación y se regresó a fabricantes; no se presenta como prueba con un BMW real. No se ejecutaron funciones de servicio.

## Estado final

La Lenovo conserva Android 5.1 y MAXOBD 1.1.01. El arranque incompleto y el acceso a los datos cuentan con procedimientos reproducibles. La estabilidad del motor nativo sigue pendiente y no se afirma compatibilidad completa con todas las marcas o todos los Android 5.0+.

Evidencia: [resultados estructurados](../datos/resultado-caso-2026-11-16.json), [catálogo](../datos/catalogo-paquetes-2026-11-16.json) y [capturas](evidencias.md). Los registros privados completos permanecen fuera del repositorio público.
