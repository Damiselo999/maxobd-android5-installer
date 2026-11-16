# Recuperación de paquetes de diagnóstico

La descarga integrada fallaba en Android 5.1, pero el catálogo y los objetos originales estaban disponibles. Se recuperaron en Linux, se verificaron y se copiaron por ADB, sin cambiar el APK ni obtener root.

## Inventario y comprobaciones

**19 grupos / 2.875 archivos / 907.211.045 bytes.** Todos los originales coincidieron con tamaño y MD5 del catálogo y cuentan con SHA-256 adicional. En la Lenovo se comprobaron presencia y tamaño de los 2.875 archivos, y una muestra MD5 por grupo: 19/19 correctas. Nissan/Infiniti necesita 23 archivos, 14.731.534 bytes; la app reconoció su menú y el usuario confirmó que funcionaba.

El [inventario CSV](../datos/grupos.csv) enumera BMW/MINI/Rolls-Royce, GM y sus marcas, Nissan/Infiniti, Benz/Maybach, VW/Audi y sus marcas, OBD, Ford/Lincoln/Mercury, Honda/Acura, Mazda, Toyota/Lexus, oilreset, Mitsubishi, Subaru, Suzuki, VAZ, Hyundai, Opel, Renault/Samsung/Dacia y Kia. Son grupos del catálogo, no 19 vehículos probados.

## Descarga reproducible

```sh
python3 paquetes_maxobd.py --descargar --destino datos-locales --hilos 8
python3 paquetes_maxobd.py --verificar --destino datos-locales
```

Para un solo grupo añade `--marca nissan`. Se puede repetir `--marca` para seleccionar varios. En Windows usa `py -3`.

La herramienta usa HTTPS con validación normal de certificados. Los archivos grandes se solicitan en bloques de 1 MiB, se comprueba `Content-Range` y se reintenta entre el endpoint acelerado y el regional del mismo bucket. El archivo final solo se reemplaza cuando coinciden tamaño, MD5 y SHA-256. Repetir la descarga reutiliza únicamente copias correctas. No requiere credenciales ni cambia servidores en la tableta.

El catálogo es una observación del **16 de noviembre de 2026**, no una consulta de actualización en vivo. Si el fabricante cambia o retira un objeto, el programa informa el fallo; no edites las huellas para aceptar otra respuesta.

## Carpetas

```text
datos-locales/archivos_android/
  nissan/folder/KONNWEI_NISSAN_FOLDER_TEXT_1.BIN
  nissan/es/KONNWEI_NISSAN_DATAFLOW_ES.BIN
  toyota/na/TYB_10.BIN
  toyota/jp/TYB_10.BIN
  toyota/eu/TYB_10.BIN
```

Los tres `TYB_10.BIN` son diferentes. No se aplanan las regiones. Los archivos comunes cuyo padre era `V1.0.0` van a `folder`; `LanES` pasa a `es`. Se descarga español donde existe; VAZ solo ofrece inglés y ruso y se incluyen ambos con los comunes.

## Copia por ADB y respaldo

El copiador se limita a **MAXOBD 1.1.01/código 57**, versión probada con el catálogo. No instala, degrada o desinstala APK. Abre la app una vez para que exista su directorio externo, autoriza la depuración USB y comprueba espacio libre para los paquetes y el respaldo.

```sh
adb devices -l
adb -s SERIAL shell df /sdcard
python3 paquetes_maxobd.py --copiar --destino datos-locales --respaldo respaldo-maxobd --serial SERIAL
```

`SERIAL` es el identificador de tu dispositivo; no se publica el del caso. `--respaldo` debe ser una carpeta nueva, fuera de los paquetes. El programa verifica primero los originales, comprueba la versión, cierra MAXOBD y copia sus archivos externos al respaldo. Si el respaldo falla, no empieza la transferencia. Después prepara solo archivos verificados y los copia a `/sdcard/Android/data/com.jiawei.maxobd/files/`, comprueba todos los tamaños y recupera una muestra por grupo para MD5/SHA-256.

El caso tenía 8,9 GB libres. El respaldo es de **archivos externos**: no incluye cuentas, licencias, preferencias o bases internas. Una prueba anterior de `adb backup` produjo cero bytes y no se considera válida. No se promete una recuperación completa de la app.

Si la copia se interrumpe, conserva el respaldo, verifica los originales y repite con otra carpeta de respaldo nueva. No borres datos o desinstales automáticamente. Para recuperar una carpeta concreta del respaldo, cierra MAXOBD y copia esa carpeta con ADB al mismo directorio externo.

Después abre MAXOBD manualmente y entra en Escaneo profundo de seguridad y fabricante. La herramienta no inicia diagnósticos, activaciones, borrado de fallos ni funciones de servicio. La copia de paquetes no resuelve el cierre interno documentado en el seguimiento.
