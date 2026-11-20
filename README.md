# ImageTagger

Aplicación de escritorio para **identificar a las personas que aparecen en imágenes**. Vigila una carpeta (por ejemplo, la de capturas de pantalla o la de fotos de una cámara) y, cada vez que aparece una imagen nueva, abre una ventana para cargar los datos de la persona: apellido, nombre, documento y notas. Las imágenes etiquetadas se archivan junto con sus datos y se pueden buscar, consultar y editar desde una galería.

**Versión actual:** Está en la constante `VERSION` de `main.py`

---

## Índice

1. [Funcionamiento general](#funcionamiento-general)
2. [Casos de uso](#casos-de-uso)
3. [Requisitos](#requisitos)
4. [Instalación](#instalación)
5. [Configuración](#configuración)
6. [Ejecución](#ejecución)
7. [Uso](#uso)
8. [Archivos y carpetas que genera](#archivos-y-carpetas-que-genera)
9. [Registro de errores (log)](#registro-de-errores-log)
10. [Estructura del proyecto](#estructura-del-proyecto)
11. [Limitaciones conocidas](#limitaciones-conocidas)
12. [Solución de problemas](#solución-de-problemas)
13. [Autor y licencia](#autor-y-licencia)

---

## Funcionamiento general

```
 Carpeta monitoreada          Editor (una ventana por imagen)          database/
 (config.ini)                                                          ┌──────────────────────┐
 ┌──────────────┐  imagen     ┌────────────────────────────┐ Guardar   │ foto.jpg             │
 │ foto.jpg     │ ──nueva──▶  │ imagen + Apellido, Nombre, │ ────────▶ │ foto.jpg.json        │
 │ ...          │             │ Documento, Notas           │           └──────────────────────┘
 └──────────────┘             └────────────────────────────┘                    │
                                     │ Borrar                                   │ lista, búsqueda,
                                     ▼                                          ▼ edición
                              Borrados/                                 Galería (ventana principal)
```

1. Al iniciar se abre la **galería**, maximizada: es la ventana principal.
2. Un proceso en segundo plano revisa la **carpeta monitoreada** cada segundo, sin entrar en subcarpetas.
3. Por cada imagen nueva (`.jpg`, `.jpeg`, `.png` o `.gif`) se abre un **editor**. Una imagen recién llegada se abre recién cuando terminó de copiarse. Las imágenes que ya estaban en la carpeta al iniciar también se abren, porque están pendientes de etiquetar.
4. Al **guardar**, se escribe un archivo JSON con los datos y la imagen se mueve, junto con su JSON, a la carpeta `database`.
5. Al **borrar**, la imagen (y su JSON, si lo tiene) se mueve a la carpeta `Borrados`.
6. La galería lista todo lo que hay en `database`, permite buscar, ver cada imagen con sus datos y volver a editarlos.

Como las imágenes procesadas salen de la carpeta monitoreada, todo lo que queda en ella está pendiente de procesar.

## Casos de uso

- **Registro de visitas o pacientes:** se toma una foto o una captura de la persona y se cargan sus datos en el momento.
- **Etiquetado de capturas de pantalla:** por ejemplo, de videollamadas, para saber luego quién es cada persona.
- **Archivo de fotos identificadas:** construir una colección de imágenes con los datos de quien aparece, buscable por apellido, nombre, documento o notas.
- **Consulta rápida:** buscar a una persona, ver su foto y copiar su documento al portapapeles con un clic.

## Requisitos

- **Probado en Windows 11 de 64 bits con Python 3.13.5.** Otras versiones de Windows o de Python 3 pueden funcionar, pero no están probadas.
- Python instalado desde [python.org](https://www.python.org/downloads/), con la opción **tcl/tk and IDLE**, que viene marcada por defecto. La aplicación usa `tkinter`.
- Dependencias de terceros, con versiones exactas en [requirements.txt](requirements.txt):

  | Librería | Versión | Para qué se usa |
  |---|---|---|
  | Pillow | 13.0.0 | Abrir, rotar y escalar imágenes, y mostrarlas en la interfaz |
  | pydantic | 2.14.3 | Modelo `Persona`: validación y lectura y escritura de los JSON |
  | pydantic-core, annotated-types, typing-extensions, typing-inspection | ver archivo | Dependencias de pydantic |

## Instalación

Todos los comandos se ejecutan en la carpeta del proyecto, la que contiene `main.py`.

### 1. Crear el entorno virtual

El entorno virtual (`.venv`) mantiene las librerías de la aplicación separadas de las del resto del sistema.

```bat
python -m venv .venv
```

### 2. Activar el entorno virtual

En **cmd** (Símbolo del sistema):

```bat
.venv\Scripts\activate.bat
```

En **PowerShell**:

```powershell
.venv\Scripts\Activate.ps1
```

> Si PowerShell responde que la ejecución de scripts está deshabilitada, habilítela solo para su usuario y vuelva a intentarlo:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

Con el entorno activado, el indicador de la consola empieza con `(.venv)`. Para desactivarlo, escriba `deactivate`.

### 3. Instalar las dependencias

Con el entorno activado:

```bat
python -m pip install -r requirements.txt
```

Para comprobar lo instalado:

```bat
python -m pip freeze
```

## Configuración

La carpeta a monitorear se define en el archivo **`config.ini`**, que debe estar en la misma carpeta que `main.py`.

- **`config.example.ini`** es la plantilla incluida en el repositorio. Para empezar, cópiela con el nombre `config.ini` y edítela:

  ```bat
  copy config.example.ini config.ini
  ```

- **`config.ini`** es la configuración de cada equipo. Está excluida de git (`.gitignore`) porque contiene rutas propias de cada usuario.

Contenido:

```ini
[GENERAL]
; Directorio donde se buscan imágenes nuevas (sin recursividad).
directorio_monitoreo = C:\Users\usuario\Pictures\Screenshots
; Opcional. Directorio donde se guardan las imágenes procesadas con su JSON.
directorio_database = database
```

| Sección | Clave | Descripción |
|---|---|---|
| `[GENERAL]` | `directorio_monitoreo` | Ruta de la carpeta a monitorear. Puede tener espacios y acentos, sin comillas. La carpeta debe existir. |
| `[GENERAL]` | `directorio_database` | Opcional. Carpeta donde se guardan las imágenes procesadas con su JSON. Una ruta absoluta se usa tal cual; una relativa se toma desde la carpeta de `main.py`. Si falta o está vacía, se usa `database` junto a `main.py`. Si la carpeta no existe, se crea al iniciar; si no se puede crear, se avisa y se usa `database` junto a `main.py`. Si no se puede escribir en la carpeta, se informa el error y la aplicación no arranca. |

Notas:

- El archivo puede guardarse con el Bloc de notas; se acepta UTF-8 con o sin BOM.
- Las líneas que empiezan con `;` son comentarios.
- Si falta el archivo, la clave o la carpeta, la aplicación muestra el error en un cuadro de diálogo y no arranca.

## Ejecución

### Con `iniciar.bat` (recomendado)

Doble clic en **`iniciar.bat`**, o desde una consola:

```bat
iniciar.bat
```

- Usa automáticamente el `pythonw` de `.venv` si existe; si no, el que esté en el `PATH`. No hace falta activar el entorno virtual antes.
- Funciona desde cualquier carpeta, porque se ubica en la carpeta del proyecto.
- Ejecuta la aplicación con `pythonw`, sin consola: la ventana del `.bat` se cierra enseguida y queda solo la galería.
- Los errores de inicio, como la falta de `config.ini` o una carpeta que no existe, se muestran en un cuadro de diálogo.

Para monitorear otra carpeta sin tocar `config.ini`, pásela como argumento. Tiene prioridad sobre `config.ini`:

```bat
iniciar.bat "D:\Fotos\Pendientes"
```

### Directamente con Python

Con el entorno virtual activado:

```bat
python main.py
python main.py "D:\Fotos\Pendientes"
```

Con `python` en lugar de `pythonw`, la consola queda abierta, muestra qué carpeta se monitorea y permite cerrar con Ctrl+C. Es útil para depurar, porque ahí se ven los errores internos.

La galería también puede abrirse sola, sin monitorear ninguna carpeta, para consultar `database`:

```bat
python gallery.py
```

### Cerrar la aplicación

- Cerrando la ventana de la galería. Antes se cierra cada editor abierto, y si alguno tiene datos sin guardar, se pregunta qué hacer. Si se elige **Cancelar**, la aplicación sigue abierta.
- Solo si se ejecutó con `python main.py` desde una consola: con **Ctrl+C** en esa consola, que cierra todo de inmediato, sin preguntar.

### Desde Visual Studio Code

El proyecto incluye `.vscode/settings.json` con `"code-runner.runInTerminal": true`, para que la extensión *Code Runner* ejecute en la terminal integrada. Para depurar, conviene ejecutar `main.py` con `python`, porque así se ven en la terminal los mensajes y los errores internos.

## Uso

### Galería (ventana principal)

| Elemento | Función |
|---|---|
| **Buscar** | Filtra la lista mientras se escribe. Busca en apellido, nombre y documento, sin distinguir mayúsculas ni acentos ("perez" encuentra "PÉREZ"). |
| **Buscar en notas** | Si está marcado, la búsqueda también incluye las notas. Desmarcado por defecto. |
| **Actualizar** | Vuelve a leer los JSON de `database`. La lista también se actualiza sola al guardar o borrar desde un editor. |
| **Lista** | Cada persona como `APELLIDO, NOMBRE (DOCUMENTO)`, en orden alfabético. Debajo se indica la cantidad de ítems mostrados. |
| **Vista previa** | Al hacer clic en una persona se muestran su imagen, apellido, nombre, documento y notas. |
| **Copiar** | Copia el documento al portapapeles. |
| **Editar** | Abre el editor con la imagen y los datos de esa persona. |

Si algún JSON de `database` no se puede leer, se muestra un aviso con el archivo y el motivo, y se cargan los demás.

### Editor (una ventana por imagen)

Se abre maximizado, al frente y con el cursor en **Apellido**. La imagen se ajusta al máximo tamaño posible sin deformarse.

| Campo | Reglas |
|---|---|
| Apellido | Hasta 25 caracteres. Se guarda en mayúsculas. |
| Nombre | **Obligatorio**. Hasta 25 caracteres. Se guarda en mayúsculas. |
| Documento | Hasta 25 caracteres. |
| Notas | Varias líneas, hasta 1 MB. |

- Al guardar, se quitan los espacios al principio y al final de todos los campos, y la pantalla muestra los valores ya corregidos.
- Si se pega un texto más largo que el máximo permitido, se pega recortado.
- La línea de estado, debajo de los botones, indica en rojo **"Datos modificados."** o el último error, y en verde **"Datos guardados correctamente."**

Botones:

| Botón | Qué hace |
|---|---|
| **Guardar** | Valida los datos, escribe el JSON y mueve la imagen y su JSON a `database`. Si la imagen ya estaba en `database`, porque se abrió con *Editar*, solo actualiza su JSON. |
| **Borrar** (en rojo) | Pide confirmación y mueve la imagen, y su JSON si lo tiene, a `Borrados`. |
| **Cerrar** | Cierra la ventana. Si hay datos sin guardar, pregunta: **Cancelar**, **No guardar**, **Borrar** o **Guardar**. |

Al cerrar un editor pasa al frente el siguiente editor abierto, o la galería si no queda ninguno.

## Archivos y carpetas que genera

Las dos carpetas se crean automáticamente junto a `main.py` cuando hacen falta, y están excluidas de git.

| Carpeta | Contenido |
|---|---|
| `database/` | Imágenes etiquetadas y sus datos |
| `Borrados/` | Imágenes borradas, con su JSON si lo tenían. Para recuperar una, mueva la imagen y su JSON a la carpeta de la base de datos. Se crea al iniciar; si no se puede escribir en ella, la aplicación informa el error y no arranca. |
| `logs/` | Registro de la aplicación (`imagetagger.log`); ver [Registro de errores](#registro-de-errores-log) |

**Nombre del archivo de datos:** es el nombre de la imagen con `.json` agregado, conservando la extensión original: `foto.jpg` → `foto.jpg.json`.

**Nombres repetidos:** si en la carpeta de destino ya existe una imagen con el mismo nombre, no se sobrescribe. Se agrega un sufijo numérico a la imagen y a su JSON: `foto_1.jpg` y `foto_1.jpg.json`, `foto_2.jpg` y `foto_2.jpg.json`, etc.

Ejemplo de JSON, guardado en UTF-8 y compatible con el modelo `Persona`:

```json
{
  "tipo_objeto": "persona",
  "apellido": "PÉREZ",
  "nombre": "JUAN",
  "documento": "30.123.456",
  "notas": "Primera visita.\nTraer estudios."
}
```

## Registro de errores (log)

Como la aplicación corre sin consola (`pythonw`), los errores y los eventos principales se guardan en **`logs/imagetagger.log`**, junto a `main.py`. El archivo usa UTF-8.

Se registra:

| Nivel | Qué |
|---|---|
| INFO | Inicio y cierre (con versión de la aplicación y de Python), carpeta monitoreada, archivos nuevos detectados, imágenes guardadas y borradas, y avisos de validación al guardar (por ejemplo, nombre vacío). |
| WARNING | Imágenes que no se pueden abrir y archivos de `database` que no se pueden leer. |
| ERROR | Errores al guardar o mover archivos, errores de inicio (configuración), carpeta monitoreada inaccesible y errores inesperados, con el detalle técnico (traceback). |

- Ante un error inesperado, la aplicación muestra un aviso que indica la ruta del log.
- Si la carpeta monitoreada deja de estar accesible, el error se registra una sola vez y no cada segundo; cuando vuelve a estar disponible, también queda registrado.
- El archivo rota al llegar a 1 MB: se conservan los 3 anteriores (`imagetagger.log.1` a `.3`) y se descartan los más viejos.
- Ejecutando con `python main.py` desde una consola, los mismos mensajes se ven también en la consola.

Ejemplo:

```
2026-11-18 22:41:07,512 INFO     [MainThread] main: Iniciando ImageTagger v. 1.0.2 - 2026-11-18 (Python 3.13.5, pythonw.exe)
2026-11-18 22:41:07,840 INFO     [MainThread] main: Monitoreando C:\Users\usuario\Pictures\Screenshots (log: ...\logs\imagetagger.log)
2026-11-18 22:41:10,103 INFO     [MonitorDirectorio] filesystem_service: Archivos nuevos: foto.jpg
2026-11-18 22:41:31,977 INFO     [MainThread] persona_editor: Guardado: ...\database\foto.jpg (...\database\foto.jpg.json)
```

## Estructura del proyecto

| Archivo | Contenido |
|---|---|
| `main.py` | Punto de entrada: lee la configuración, abre la galería y monitorea la carpeta. Contiene la versión. |
| `gallery.py` | Galería: lista, búsqueda y vista previa de las personas de `database`. |
| `persona_editor.py` | Editor de los datos de una imagen y el diálogo de cambios sin guardar. |
| `filesystem_service.py` | Monitoreo de la carpeta, nombres disponibles y movimiento de archivos. |
| `models.py` | Modelo `Persona` (pydantic) con sus validaciones. |
| `app_config.py` | Rutas (`database`, `Borrados`, `logs`, `config.ini`), lectura de la configuración, configuración del log y fuente por defecto (Arial 12). |
| `iniciar.bat` | Lanzador para Windows. |
| `config.example.ini` | Plantilla de configuración. |
| `requirements.txt` | Dependencias con versiones exactas. |

## Limitaciones conocidas

- **Una sola carpeta, sin subcarpetas:** solo se monitorea una carpeta, y no se revisan sus subcarpetas.
- **Una ventana por imagen:** si llegan muchas imágenes a la vez, se abren todas juntas.
- **Una sola instancia:** no conviene ejecutar dos instancias a la vez sobre la misma carpeta, porque la misma imagen se abriría dos veces.
- **Copias que se detienen:** si la copia de una imagen se detiene más de un segundo a mitad de camino, por ejemplo una descarga de OneDrive que se traba, puede abrirse incompleta. En ese caso se muestra un error, la imagen queda en la carpeta y se vuelve a abrir la próxima vez que se inicie la aplicación.
- **Notas en una sola línea muy larga:** el cuadro de texto de Tk se vuelve lento, o puede fallar, con una sola línea de cientos de miles de caracteres sin saltos de línea. Con texto normal, repartido en líneas, no hay problema.
- **Imágenes GIF animadas:** se muestra solo el primer cuadro.

## Solución de problemas

| Problema | Solución |
|---|---|
| `No se encontró el archivo de configuración` | Copie `config.example.ini` como `config.ini` y edite la ruta. |
| `El directorio a monitorear no existe` | Revise `directorio_monitoreo` en `config.ini`. |
| `ModuleNotFoundError: No module named 'PIL'` o `'pydantic'` | Faltan las dependencias: siga los pasos de [Instalación](#instalación). Si usa `python main.py`, active antes el entorno virtual. |
| `No se encontro Python` al usar `iniciar.bat` | Instale Python 3.13 o cree el entorno `.venv`. |
| La aplicación no abre, falla o se comporta de forma extraña | Revise `logs/imagetagger.log`. Si no alcanza, ejecute `python main.py` desde una consola, con el entorno activado, para ver los mensajes en el momento. |
| Las imágenes que ya estaban en la carpeta no se abren | Se abren al iniciar. Si había otra instancia abierta, ciérrela y vuelva a iniciar. |
| No se ve ninguna ventana nueva | Revise la barra de tareas: Windows a veces deja una ventana nueva detrás de otra aplicación. |
| VS Code (Pylance) marca errores que no aparecen al ejecutar | Ejecute *Python: Restart Language Server* desde la paleta de comandos (Ctrl+Shift+P). |

## Autor y licencia

- **Autor:** Roberto Marcelo Chas Cruz — chascruzrm2@gmail.com
- **Licencia:** GPLv3 (GNU General Public License v3.0)
