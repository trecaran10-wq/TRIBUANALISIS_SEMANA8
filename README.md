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

## Publicar en Render

El proyecto incluye `render.yaml` para desplegar Flask con Gunicorn y un disco persistente para SQLite. El servicio usa un plan con disco persistente; no cambies el montaje del disco ni subas la carpeta `instance`, que contiene la base de datos y la clave de sesión local.

1. Antes de publicar, inicia sesión en la aplicación local. Si aún no tienes una cuenta local, créala: la primera cuenta adopta los casos que todavía no tienen propietario.
2. En **Registro y análisis → Casos registrados**, usa **Exportar mis casos**. Guarda el Excel en un lugar privado; no lo agregues al repositorio.
3. Crea un repositorio en GitHub y sube el contenido de esta carpeta, excluyendo `instance`, `.venv` y `__pycache__`. El `.gitignore` incluido protege esos datos al usar Git.
4. En Render, crea un **Blueprint** desde ese repositorio y aplica la configuración de `render.yaml`. Revisa el costo vigente del plan con disco persistente antes de confirmar.
5. Una vez desplegada la web, copia el valor generado de `TRIBUANALISIS_REGISTRATION_CODE` desde las variables del servicio. Usa ese código en **Crear cuenta** para registrar tu cuenta inicial. El código temporal evita que otra persona reclame primero los casos que importarás.
6. Inicia sesión, importa el Excel privado desde **Registro y análisis → Importación Excel** y confirma la vista previa.
7. Cuando compruebes que tus casos están en tu cuenta, elimina `TRIBUANALISIS_REGISTRATION_CODE` de las variables del servicio y aplica el cambio para habilitar el registro público. Conserva `TRIBUANALISIS_SECRET_KEY`, `TRIBUANALISIS_COOKIE_SECURE=1` y el disco persistente.

El enlace `onrender.com` será accesible públicamente. Cada persona crea su propia cuenta; las consultas y casos están aislados por usuario. El almacenamiento SQLite reside en el disco persistente de Render, no en el repositorio.

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
