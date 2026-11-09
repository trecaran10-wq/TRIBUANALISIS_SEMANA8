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

El proyecto conserva SQLite para uso local y admite PostgreSQL mediante `DATABASE_URL` para desplegarlo en Vercel con Supabase. La base PostgreSQL se inicializa automáticamente al arrancar la aplicación. En Vercel configura estas variables privadas antes del despliegue:

- `DATABASE_URL`: URL PostgreSQL del **pooler de transacciones** de Supabase con SSL habilitado. No uses la URL en el navegador ni la compartas por el chat.
- `TRIBUANALISIS_SECRET_KEY`: clave aleatoria larga y fija, generada desde Vercel.
- `TRIBUANALISIS_COOKIE_SECURE`: `1`.
- `TRIBUANALISIS_REGISTRATION_CODE`: opcional y temporal para proteger el primer registro; elimínala después de crear tu cuenta.

En Vercel, elige el preset **Flask** y deja el directorio raíz `./`: `app.py`, `requirements.txt`, `templates` y `static` están en la raíz del repositorio. La aplicación no usa la SQLite local cuando `DATABASE_URL` está configurada; en Vercel falla de forma explícita si faltan las variables de PostgreSQL o de sesión.

Para configurar Supabase, crea un proyecto y en el panel usa **Connect → Transaction pooler**. Copia la URI PostgreSQL completa y configura el campo `DATABASE_URL` en **Variables ambientales** de Vercel. Genera una clave privada localmente con `python -c "import secrets; print(secrets.token_urlsafe(48))"` y guárdala como `TRIBUANALISIS_SECRET_KEY`; no pegues la URL ni la clave en GitHub ni en el chat. Agrega `TRIBUANALISIS_COOKIE_SECURE` con valor `1`. Configura estas variables antes de pulsar **Despliegue**; cada cambio posterior requiere un nuevo despliegue.

No publiques `instance`, archivos `.db`, claves de sesión ni datos de usuarios. La base local no se copia automáticamente a Supabase; importa o migra registros existentes solo después de decidirlo.

## Los cinco apartados

1. **Dashboard:** indicadores y gráficos calculados desde la base de datos configurada.
2. **Registro y análisis:** formulario completo, importación masiva Excel, edición, eliminación e historial de evaluaciones.
3. **Regímenes tributarios:** fichas con acceso directo a la página SUNAT de cada régimen, comparación personalizada, estimación, recomendación preliminar, proyección, alertas, Excel y PDF.
4. **Guía tributaria:** buscador y filtros con referencias y enlaces directos a los apartados SUNAT correspondientes.
5. **Perfil y créditos:** datos académicos, integrantes, preferencias y UIT de referencia.

Chart.js se carga desde jsDelivr; para ver los gráficos, el navegador requiere conexión a Internet. El resto de la aplicación funciona localmente.

En el Dashboard se muestran hasta cinco alertas, priorizando posibles exclusiones y la previsión de superar límites, seguidas por actividades futuras excluidas, cercanía a límites y planes de crecimiento. Esta prioridad es orientativa, no una calificación legal. Cada alerta permite abrir el caso; cuando hay más de cinco, **Ver todas las alertas** permite consultar las restantes.

## Importación de Excel

Descarga la plantilla desde **Registro y análisis → Importación Excel**, conserva los encabezados y elimina la fila demostrativa. Solo son obligatorias las columnas y los valores indicados por la aplicación; los campos opcionales pueden quedar vacíos. Los importes deben ser números finitos no negativos, las cantidades de trabajadores, locales y sucursales deben ser enteras, y `taxable_share` debe estar entre 0 y 1. La fecha opcional `start_date` admite una fecha de Excel o `AAAA-MM-DD`; los campos booleanos admiten, entre otros, `sí`/`no` o `1`/`0`.

La vista previa indica la fila y la columna que necesitan corrección. Puedes editar las columnas visibles; para corregir otras, modifica el Excel y vuelve a subirlo. La confirmación vuelve a validar todos los registros antes de guardarlos.

El RUC debe tener 11 dígitos y no estar duplicado en la cuenta. La aplicación no verifica su dígito verificador ni consulta su existencia en SUNAT; confirma el RUC en SUNAT cuando corresponda.

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
