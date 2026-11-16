# Servidores y descarga fallida

Observaciones del 16 de noviembre de 2026, MAXOBD 1.1.01 en Android 5.1. Se comprobó la petición real de la app; no se dedujeron rutas Nissan a partir de constantes antiguas de BMW.

| Dirección | Función observada |
|---|---|
| `http://www.konnweis.cn/maxobd/pyaservice/DiagnosDatManage.php` | POST que obtiene el catálogo al seleccionar fabricante |
| `http://www.konnweis.cn/CarDiagnosApp/OSSInfoManage.php` | Configuración; su respuesta privada no se publica |
| `http://www.konnweis.cn/cnkwpm/checkAppVer.php` | Comprobación de versión |
| `http://www.konnweis.cn/cnkwpm/deviceupdate.php` | Consulta de versión del dispositivo |
| `https://car-diagnostic-app.oss-accelerate.aliyuncs.com/MAXOBD/CarDat/` | Objetos exactos del catálogo |
| `https://car-diagnostic-app.oss-us-east-1.aliyuncs.com/MAXOBD/CarDat/` | Mismo bucket regional; recuperación de dos archivos por rangos desde Linux |

El catálogo respondió **HTTP200, código100 y mensaje de éxito**, con 19 grupos. El cuerpo estaba comprimido con gzip aunque la captura no mostraba `Content-Encoding`; al descomprimirlo resultó JSON válido de 705.518 bytes. El primer analizador no reconocía esa compresión: su resultado «no JSON visible» no demuestra una respuesta rota.

Nissan usa rutas bajo `https://car-diagnostic-app.oss-accelerate.aliyuncs.com/MAXOBD/CarDat/NISSAN/V1.0.0/`. Los 23 archivos comunes y españoles respondieron y coincidieron con tamaño y MD5. Después se recuperó el resto del catálogo. Dos archivos grandes de Mazda y VW agotaron tiempos de espera y se recuperaron por bloques desde el mismo bucket regional; sus huellas finales coincidieron.

## Comparación de versiones

Las cadenas examinadas de **1.0.30, 1.1.01 y 1.1.04** coinciden: [comparación](../datos/comparacion-servidores.json). No demuestra peticiones idénticas en todas las funciones, pero no aporta evidencia de un reemplazo general de servidores.

También aparecen `svr.oscanner.com`, ayudas de otros productos y rutas de BMW en `139.9.2.19`. Son referencias estáticas; no se confirmó su uso para descargar Nissan. Un HTTP403 en la raíz de un bucket no prueba que sus objetos estén caídos: se comprobaron los archivos exactos.

## Intervención y límites

No se parchearon servidores del APK. Se descargaron los originales en la computadora y se copiaron a las carpetas que utiliza MAXOBD. La app reconoció Nissan. La causa concreta del descargador integrado no quedó aislada; no se atribuye sin pruebas a una caída de servidores, TLS, el reloj o la interfaz.

La captura temporal observó HTTP y dejó HTTPS como túnel cifrado. No se instalaron certificados ni se desactivó su validación. El proxy fue retirado y se restauraron sus ajustes. No se publican peticiones con identificadores, firmas, credenciales o respuestas privadas.
