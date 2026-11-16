# Compatibilidad y perfiles

El alcance Android 5.0+ describe el mínimo declarado por los APK examinados, no una prueba exhaustiva en todas las versiones de Android ni una conversión de APK modernos.

| Perfil | minSdk | targetSdk | ABI del componente | Prueba en dispositivo |
|---|---|---|---|---|
| 1.0.30 / código 46 / xxhdpi | 21 | 35 | arm64-v8a | Lenovo TAB 2 A8-50F-YZ-A con API22: inicio, interfaz y búsqueda BLE |
| 1.0.29 / código 44 / hdpi | 21 | 35 | armeabi-v7a | Ninguna; solo se inspeccionaron los archivos |

Un dispositivo ARM64 no necesariamente permite aplicaciones de 32 bits. El instalador consulta la lista ABI del sistema y exige la arquitectura del conjunto que se va a instalar. No deduce soporte por el nombre comercial del procesador.

La densidad incluida puede escalarse por Android; en el caso probado se usó xxhdpi en una tableta cuya densidad reportada era distinta. Esto no acredita todos los tamaños de pantalla.

## Hashes y firmas

`perfiles.json` contiene los SHA-256 exactos de cada APK original, no del contenedor XAPK. Un XAPK recompreso puede ser reconocido si conserva exactamente esos componentes y su manifiesto esperado. Se rechazan componentes adicionales, versiones diferentes y archivos alterados.

Los tres APK de cada conjunto examinado presentaron la misma huella SHA-256 de certificado:

```text
68:88:CF:42:91:A9:AD:3A:DB:A5:01:60:BD:69:FB:A7:D3:22:31:7A:55:66:E0:1C:08:1A:95:3B:9F:97:73:EB
```

La huella se observó en las copias aportadas desde APKPure. No constituye una comprobación independiente con el fabricante. El script reconoce los bytes ya examinados y Android valida sus firmas al instalar. No se eluden errores de firma y no se concede acceso privilegiado.

## Permisos y conexión

Android 5.1 otorgaba al paquete permisos de Bluetooth clásico, ubicación, Internet y almacenamiento. Los permisos de versiones recientes, como BLUETOOTH_SCAN y BLUETOOTH_CONNECT, no existen en API22 y no se intentan forzar. En otros Android, revisa los permisos de Bluetooth/dispositivos cercanos o ubicación que correspondan al sistema y a la aplicación.

Tener Bluetooth LE no confirma el protocolo de un modelo concreto de adaptador ni la comunicación con ECU. En el caso original esa prueba está pendiente. USB en este proyecto se utiliza para ADB entre la computadora y la tableta; no demuestra soporte de un adaptador OBD USB.

## Casos que requieren otro diagnóstico

- Un APK cuyo minSdk sea mayor que el Android instalado.
- `UnsatisfiedLinkError`, símbolos nativos ausentes, errores de WebView o licencias.
- Un cierre que continúe teniendo instalados todos los componentes correctos.
- Un conjunto de la misma versión con hashes/ABI/densidad diferentes a los dos perfiles registrados.

No edites minSdk, firmas o controles de licencia. Un reinicio de fábrica o un cambio de ROM no se justifican por este error de recursos sin investigar primero la instalación completa.
