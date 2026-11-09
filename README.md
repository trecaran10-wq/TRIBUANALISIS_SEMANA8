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

## Publicar gratuitamente en PythonAnywhere

El plan gratuito ofrece una aplicación web pública en `tuusuario.pythonanywhere.com` y 512 MB de almacenamiento persistente. Tiene límites de conexiones salientes; esta aplicación no necesita servicios externos desde el backend. Chart.js y las fuentes se descargan directamente en el navegador.

1. Inicia sesión en la aplicación local. Antes de desplegar, se prepara por separado un ZIP con el código y una copia de la base SQLite; esta última contiene cuentas, casos e historial. **No subas la base de datos a GitHub ni la hagas pública.**
2. Crea una cuenta **Beginner** gratuita en PythonAnywhere. En la pestaña **Files**, sube ambos archivos privados a tu directorio personal.
3. Abre una consola Bash y extrae el código y coloca la base en la carpeta persistente del proyecto:

   ```bash
   mkdir -p ~/tribuanalisis/instance
   unzip ~/tribuanalisis-pythonanywhere.zip -d ~/tribuanalisis
   cp ~/tribuanalisis-migration.sqlite3 ~/tribuanalisis/instance/tribuanalisis.db
   ```

4. Crea el entorno e instala los requisitos:

   ```bash
   mkvirtualenv --python=/usr/bin/python3.13 tribuanalisis
   workon tribuanalisis
   pip install -r ~/tribuanalisis/requirements.txt
   ```

5. En **Web**, crea una aplicación con **Manual configuration** y Python 3.13 (o la versión disponible que coincida con el entorno). Asocia `~/.virtualenvs/tribuanalisis` en el campo **Virtualenv**.
6. Edita el archivo WSGI que proporciona PythonAnywhere. Antes de importar la aplicación, añade (cambia `YOUR_USERNAME` por tu usuario y el código temporal por una clave aleatoria larga):

   ```python
   import os
   import sys

   project_path = "/home/YOUR_USERNAME/tribuanalisis"
   if project_path not in sys.path:
       sys.path.insert(0, project_path)

   os.environ["TRIBUANALISIS_COOKIE_SECURE"] = "1"
   os.environ["TRIBUANALISIS_REGISTRATION_CODE"] = "TU-CODIGO-ALEATORIO-TEMPORAL"

   from app import app as application
   ```

   La variable temporal impide que otra persona se registre antes de que confirmes el acceso a tu cuenta. La aplicación conserva SQLite y la clave de sesión en `instance`, dentro de tu espacio persistente.
7. Guarda el WSGI y pulsa **Reload**. Inicia sesión con la cuenta local existente y confirma que aparecen tus casos e historial.
8. Cuando verifiques los datos, quita la línea `TRIBUANALISIS_REGISTRATION_CODE` del WSGI y vuelve a pulsar **Reload**. Así habilitas el registro para otras personas. Comparte entonces el enlace público.

El repositorio de GitHub se mantiene privado; la base SQLite y sus hashes de contraseña no forman parte del código publicado. Render también está configurado en `render.yaml`, pero su almacenamiento persistente requiere un plan de pago; su opción gratuita no es adecuada para conservar esta base SQLite.

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
