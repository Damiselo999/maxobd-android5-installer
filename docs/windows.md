# Windows

1. Instala Python 3.9 o superior desde [python.org](https://www.python.org/downloads/windows/).
2. Descarga [Platform Tools oficiales de Google](https://developer.android.com/tools/releases/platform-tools) y extrae el ZIP.
3. Descarga y extrae el repositorio y conserva tu XAPK completo en una carpeta conocida.
4. Activa depuración USB en la tableta, conecta un cable de datos y acepta el aviso RSA.

Desde PowerShell, en la carpeta del repositorio:

```powershell
py -3 instalar_maxobd.py --xapk "C:\Descargas\MAXOBD.xapk" --adb "C:\Android\platform-tools\adb.exe"
```

Si la verificación es correcta, instala:

```powershell
py -3 instalar_maxobd.py --xapk "C:\Descargas\MAXOBD.xapk" --adb "C:\Android\platform-tools\adb.exe" --instalar
```

Las rutas son ejemplos; sustitúyelas por las tuyas. Si usas varias tabletas, añade `--serial SERIAL` con el identificador de `adb devices -l`.

## Si no aparece el dispositivo

Consulta el Administrador de dispositivos. Un cable que solo carga no sirve para ADB. Usa el controlador ADB que corresponda al fabricante desde su soporte oficial; no instales controladores VCOM/preloader para reparar esta aplicación ni desactives la firma de controladores.

- `unauthorized`: desbloquea la tableta y acepta «¿Permitir depuración USB?» para tu computadora.
- `offline`: comprueba cable, puerto y conexión; no es un motivo para flashear.
- `No se encuentra ADB`: corrige la ruta de `--adb` o añade Platform Tools al PATH.

La reparación original se ejecutó en Linux; esta guía no afirma una prueba de instalación real en Windows. El script utiliza la biblioteca estándar y llamadas ADB compatibles con Windows.
