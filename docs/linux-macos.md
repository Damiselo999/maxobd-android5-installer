# Linux y macOS

Necesitas Python 3.9+ y ADB en PATH o en una ruta indicada con `--adb`. Si falta ADB, usa [SDK Platform Tools de Google](https://developer.android.com/tools/releases/platform-tools) para tu sistema.

```sh
python3 --version
adb version
adb devices -l
```

Activa depuración USB, utiliza un cable de datos y acepta el aviso RSA de la tableta. Desde la carpeta del repositorio:

```sh
python3 instalar_maxobd.py --xapk "$HOME/Descargas/MAXOBD.xapk"
python3 instalar_maxobd.py --xapk "$HOME/Descargas/MAXOBD.xapk" --instalar
```

La primera llamada solo verifica. La segunda instala el conjunto reconocido conservando datos. Ajusta la ruta; en macOS tu carpeta puede ser `Downloads`. Si ADB no está en PATH, añade `--adb "/ruta/platform-tools/adb"`.

En Linux, un error de permisos USB puede requerir las reglas udev del sistema o pertenencia al grupo correspondiente de tu distribución. No ejecutes todo el instalador como root ni cambies el firmware para solucionarlo. Esta documentación no altera grupos o reglas automáticamente.

La ejecución original fue en Kali Linux con Platform Tools 34.0.5-debian, ya instaladas. macOS no fue probado con el dispositivo real.
