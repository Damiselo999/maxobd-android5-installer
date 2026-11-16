# Diagnóstico comprobado

Fecha: 16 de noviembre de 2026. Dispositivo: Lenovo TAB 2 A8-50F-YZ-A, Android 5.1/API 22, kernel 3.10.65, ABI principal arm64-v8a. No se publican los logs completos del dispositivo.

## Antes

MAXOBD 1.0.30/código 46 estaba instalado únicamente como APK base:

```text
splits=[base]
primaryCpuAbi=null
```

Al abrirlo, la actividad principal fallaba en `ObdHomeMainfragment.onCreateView` con `Resources$NotFoundException`, recurso `0x7f070105`.

Al inspeccionar con AAPT2 la copia del APK instalada y el XAPK guardado se encontró:

```text
Base:
  resource 0x7f070105 drawable/ic_iv_rightselect
  (anydpi-v24) res/drawable-anydpi-v24/ic_iv_rightselect.xml

config.xxhdpi.apk:
  resource 0x7f070105 drawable/ic_iv_rightselect
  (xxhdpi) res/drawable-xxhdpi-v4/ic_iv_rightselect.png
```

El gráfico utilizable en Android 5.1 estaba en un componente ausente. Además, el XAPK incluía `config.arm64_v8a.apk` con 21 bibliotecas nativas, entre ellas `libobd.so`, bibliotecas por marca de vehículo y PDFium. El proceso fallaba antes de poder validar su uso completo.

## Intervención

1. Se comprobó que el base del XAPK y el APK instalado eran idénticos mediante SHA-256.
2. Se compararon los certificados del base y ambos componentes; coincidían.
3. Se instalaron los tres APK originales en una sola sesión con `adb install-multiple -r`.
4. Android respondió `Success`; se conservaron el UID de la aplicación y la fecha de primera instalación.

No se cambiaron datos de MAXOBD mediante borrado o desinstalación. No se modificaron, fusionaron, recompilaron ni volvieron a firmar los APK.

## Después

```text
versionName=1.0.30
versionCode=46
splits=[base, config.arm64_v8a, config.xxhdpi]
primaryCpuAbi=arm64-v8a
```

La pantalla principal se mostró en español y `dumpsys activity activities` confirmó la actividad `RESUMED`. En los registros posteriores examinados no aparecieron `FATAL EXCEPTION`, `UnsatisfiedLinkError` ni `Fatal signal`.

Bluetooth estaba activado; al abrir la conexión se registró escaneo BLE. Se canceló la búsqueda sin seleccionar dispositivos cercanos ajenos. El usuario confirmó que el escáner aún no estaba conectado al vehículo, por lo que no se declara validada la comunicación OBD.

## Conclusión

El cierre observado se resolvió completando la instalación. El requisito mínimo de este APK era API 21; no fue necesario instalar una ROM Android 7. Las guías de ROMs que mezclan TAB 2 A8-50F, A5500, A8-50L/LC o TB3 no se usaron para modificar la tableta.

Para repetir el diagnóstico en Android 5.1 se pueden usar buffers compatibles, sin borrar el historial:

```sh
adb -s SERIAL logcat -v threadtime -b main -b system
```

Inicia esa captura antes de abrir la aplicación y detenla con Ctrl+C después del fallo o de la prueba. Guardar un recurso `v24` en el base no demuestra por sí solo que el conjunto completo requiera API24: hay que inspeccionar también los componentes.
