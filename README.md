# Tribuanálisis · Semana 8

Aplicación local académica para registrar negocios, comparar los cuatro regímenes tributarios empresariales peruanos, guardar evaluaciones, importar Excel y generar informes.

## Ejecutar en Windows

Desde PowerShell, en esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000`. Si ya existe el entorno `D:\TRIBUANALISIS_2U\.venv`, se puede activar ese entorno e instalar las dependencias desde el `requirements.txt` de esta carpeta.

La base de datos se crea automáticamente en `instance\tribuanalisis.db` y persiste entre ejecuciones. Para elegir otra ubicación, define la variable de entorno `TRIBUANALISIS_DB` antes de iniciar el servidor.

## Despliegue

Este proyecto usa Flask y escribe en SQLite. El repositorio no incluye una adaptación específica para Vercel; antes de desplegarlo allí, verifica que el entorno conserve los archivos de la base de datos entre ejecuciones. No publiques `instance`, archivos `.db`, claves de sesión ni datos de usuarios. Si el almacenamiento del hosting es efímero, se necesita una base de datos persistente externa o adaptar la aplicación.

## Los cinco apartados

1. **Dashboard:** indicadores y gráficos calculados desde SQLite.
2. **Registro y análisis:** formulario completo, importación masiva Excel, edición, eliminación e historial de evaluaciones.
3. **Regímenes tributarios:** fichas con acceso directo a la página SUNAT de cada régimen, comparación personalizada, estimación, recomendación preliminar, proyección, alertas, Excel y PDF.
4. **Guía tributaria:** buscador y filtros con referencias y enlaces directos a los apartados SUNAT correspondientes.
5. **Perfil y créditos:** datos académicos, integrantes, preferencias y UIT de referencia.

Chart.js se carga desde jsDelivr; para ver los gráficos, el navegador requiere conexión a Internet. El resto de la aplicación funciona localmente.

Las imágenes de `static\images\imagenes_para_subir` se usan en la barra lateral, el encabezado del Dashboard y la marca del proyecto. Puedes reemplazarlas conservando esos nombres para actualizar los recursos.

Para la ilustración del encabezado de Registro y análisis, sube el recurso como `static\images\imagenes_registro\banner_registro.png`.

Para el encabezado y la ilustración de estado vacío del apartado Regímenes, usa `static\images\imagenes_regimenes\banner_regimenes.png` y `static\images\imagenes_regimenes\comparacion_vacia.png`. Para integrar el encabezado con su diseño, se recomienda una imagen panorámica con fondo transparente.

Para el encabezado de la Guía tributaria, la ilustración está en `static\images\imagenes_guia\banner_guia.png`.

El encabezado de Perfil y créditos usa las ilustraciones de `static\images\imagenes_perfil`. Los créditos del curso, docente e integrantes son fijos y no se editan desde la aplicación.

## Validación

```powershell
python -m unittest discover -s tests -v
```

## Límites importantes

Esta herramienta es académica, no presenta declaraciones a SUNAT y no sustituye asesoría tributaria. Los importes, límites y exclusiones de `engine.py` están centralizados para poder actualizarlos. Las fichas de régimen y la recomendación enlazan directamente con la orientación de SUNAT de Nuevo RUS, RER, RMT y Régimen General. Verifica la UIT correspondiente al ejercicio y la situación específica del contribuyente antes de utilizar una estimación.

Los pagos mensuales a cuenta del RMT y del Régimen General no se estiman sin los coeficientes e información fiscal del periodo anterior. El cálculo de IGV es aproximado y no contempla todos los ajustes y requisitos del crédito fiscal. El indicador de exclusiones no sustituye la revisión completa de las actividades, vinculación económica, historial y demás condiciones legales.

Las cuentas utilizan correo y contraseñas almacenadas como hash. Cada cuenta tiene sus propios casos y evaluaciones. Configura una contraseña única y conserva copias de seguridad del disco persistente: el alojamiento no sustituye un respaldo.
