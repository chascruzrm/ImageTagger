"""Galería: lista las personas guardadas en la carpeta database y muestra la
imagen y los datos de la seleccionada."""

import logging
import os
import unicodedata
from dataclasses import dataclass
from functools import cached_property
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageOps, ImageTk
from pydantic import ValidationError

from app_config import (ARCHIVO_LOG, DIRECTORIO_DATABASE, EVENTO_DATABASE_MODIFICADA,
                        configurar_fuentes, configurar_log)
from models import Persona
from persona_editor import VentanaImagen

log = logging.getLogger(__name__)

ANCHO_VENTANA = 1000
ALTO_VENTANA = 900
MARGEN = 10
# Tamaño máximo con el que se guarda en memoria la imagen de vista previa
# (se reescala desde aquí cada vez que cambia el tamaño del cuadro).
MAX_LADO_PREVIA = 1600


@dataclass
class Registro:
    """Una persona leída de un archivo de metadatos de database."""
    ruta_json: str
    ruta_imagen: str
    persona: Persona

    @property
    def texto(self):
        """Texto para la lista: APELLIDO, NOMBRE (DOCUMENTO)."""
        p = self.persona
        texto = ", ".join(x for x in (p.apellido, p.nombre) if x)
        if p.documento:
            texto += f" ({p.documento})"
        return texto

    # Versiones normalizadas para la búsqueda; se calculan una sola vez por
    # registro (las notas pueden ser largas).
    @cached_property
    def texto_busqueda(self):
        return normalizar(self.texto)

    @cached_property
    def notas_busqueda(self):
        return normalizar(self.persona.notas)


def texto_cantidad(cantidad):
    """Texto para lblCantidadResultados."""
    if cantidad == 0:
        return "No se muestran ítems."
    if cantidad == 1:
        return "1 ítem mostrado"
    return f"{cantidad} ítems mostrados"


def normalizar(texto):
    """Minúsculas y sin acentos, para buscar sin distinguir 'Pérez' de 'PEREZ'."""
    sin_acentos = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn").casefold()


def cargar_registros(directorio):
    """Lee todos los .json de `directorio` como Persona.

    Devuelve (registros ordenados alfabéticamente, lista de errores en texto).
    """
    registros, errores = [], []
    if not os.path.isdir(directorio):
        return registros, errores
    for nombre in os.listdir(directorio):
        if not nombre.lower().endswith(".json"):
            continue
        ruta_json = os.path.join(directorio, nombre)
        try:
            with open(ruta_json, encoding="utf-8") as f:
                persona = Persona.model_validate_json(f.read())
        except ValidationError as e:
            detalle = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'json'}: {err['msg']}"
                                for err in e.errors())
            errores.append(f"{nombre}: {detalle}")
            continue
        except (OSError, UnicodeDecodeError) as e:
            errores.append(f"{nombre}: {e}")
            continue
        # La imagen se llama como el JSON sin la extensión .json (foto.jpg.json -> foto.jpg).
        registros.append(Registro(ruta_json, ruta_json[:-len(".json")], persona))
    registros.sort(key=lambda r: normalizar(r.texto))
    return registros, errores


class Galeria(tk.Tk):
    def __init__(self):
        super().__init__()
        configurar_fuentes()
        self.title("Galería")
        # Tamaño normal 1000x900 centrado en la pantalla (es el que toma al
        # restaurarla); al iniciar se muestra maximizada.
        x = max((self.winfo_screenwidth() - ANCHO_VENTANA) // 2, 0)
        y = max((self.winfo_screenheight() - ALTO_VENTANA) // 2, 0)
        self.geometry(f"{ANCHO_VENTANA}x{ALTO_VENTANA}+{x}+{y}")
        try:
            self.state("zoomed")              # Windows / macOS
        except tk.TclError:
            self.attributes("-zoomed", True)  # Linux

        self._registros = []      # todos los registros leídos
        self._visibles = []       # registros que pasan el filtro, en el orden de la lista
        self._actual = None       # registro mostrado a la derecha
        self._imagen = None       # imagen PIL de la vista previa (sin escalar al cuadro)
        self._mensaje_imagen = ""  # texto a mostrar en el cuadro si no hay imagen
        self._foto = None         # PhotoImage dibujada (referencia para el GC)
        self._after_copiado = None  # callback que restaura el texto de btCopiarDoc

        self._construir()
        self._limpiar_detalle()
        self.actualizar()
        self.bind(EVENTO_DATABASE_MODIFICADA, lambda e: self.actualizar())

    def report_callback_exception(self, tipo, valor, traza):
        """Errores no controlados en cualquier ventana de la aplicación (Tk los
        informa a la ventana raíz, que es la galería): se registran en el log
        y se avisan al usuario."""
        log.error("Error no controlado en la interfaz", exc_info=(tipo, valor, traza))
        try:
            messagebox.showerror("Error inesperado",
                                 f"Ocurrió un error inesperado:\n\n{valor}\n\n"
                                 f"Los detalles se guardaron en {ARCHIVO_LOG}",
                                 parent=self)
        except tk.TclError:  # la aplicación se está cerrando
            pass

    # ----------------------------------------------------------- interfaz --

    def _construir(self):
        # Columna izquierda: 1/3 del ancho; derecha: 2/3.
        self.columnconfigure(0, weight=1, uniform="columnas")
        self.columnconfigure(1, weight=2, uniform="columnas")
        self.rowconfigure(0, weight=1)

        # --- Izquierda: búsqueda y lista ---
        izq = tk.Frame(self)
        izq.grid(row=0, column=0, sticky="nsew", padx=(MARGEN, MARGEN // 2), pady=MARGEN)
        izq.columnconfigure(0, weight=1)
        izq.rowconfigure(2, weight=1)

        tk.Label(izq, text="Buscar").grid(row=0, column=0, sticky="sw")
        self.btActualizar = tk.Button(izq, text="Actualizar", command=self.actualizar)
        self.btActualizar.grid(row=0, column=1, sticky="e", pady=(0, 4))

        self._buscar = tk.StringVar(self)
        self._buscar.trace_add("write", lambda *_: self._filtrar())
        self.txtBuscar = tk.Entry(izq, width=1, textvariable=self._buscar)
        self.txtBuscar.grid(row=1, column=0, sticky="ew")

        # Si está marcado, la búsqueda también mira las notas.
        self._buscar_en_notas = tk.BooleanVar(self, value=False)
        self.chkBuscarEnNotas = tk.Checkbutton(izq, text="Buscar en notas",
                                               variable=self._buscar_en_notas,
                                               command=self._filtrar)
        self.chkBuscarEnNotas.grid(row=1, column=1, sticky="e", padx=(MARGEN // 2, 0))

        marco_lista = tk.Frame(izq)
        marco_lista.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(MARGEN, 0))
        scroll_lista = tk.Scrollbar(marco_lista, orient="vertical")
        # exportselection=False: la selección no se pierde al seleccionar texto en txtBuscar.
        self.lstPersonas = tk.Listbox(marco_lista, width=1, exportselection=False,
                                      activestyle="none", yscrollcommand=scroll_lista.set)
        scroll_lista.config(command=self.lstPersonas.yview)
        scroll_lista.pack(side="right", fill="y")
        self.lstPersonas.pack(side="left", fill="both", expand=True)
        self.lstPersonas.bind("<<ListboxSelect>>", self._al_seleccionar)

        self.lblCantidadResultados = tk.Label(izq, anchor="w")
        self.lblCantidadResultados.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        # --- Derecha: vista previa y datos ---
        der = tk.Frame(self)
        der.grid(row=0, column=1, sticky="nsew", padx=(MARGEN // 2, MARGEN), pady=MARGEN)
        der.columnconfigure(0, weight=1)
        der.rowconfigure(0, weight=3)  # imagen: 3/4 del alto libre
        der.rowconfigure(5, weight=1)  # notas: 1/4 del alto libre

        self.imgVistaPrevia = tk.Canvas(der, width=1, height=1, highlightthickness=1,
                                        highlightbackground="gray70")
        self.imgVistaPrevia.grid(row=0, column=0, sticky="nsew")
        self.imgVistaPrevia.bind("<Configure>", lambda e: self._dibujar_imagen())

        self.lblApellido = tk.Label(der, anchor="w")
        self.lblApellido.grid(row=1, column=0, sticky="ew", pady=(MARGEN, 0))
        self.lblNombre = tk.Label(der, anchor="w")
        self.lblNombre.grid(row=2, column=0, sticky="ew")

        fila_documento = tk.Frame(der)
        fila_documento.grid(row=3, column=0, sticky="ew")
        self.lblDocumento = tk.Label(fila_documento, anchor="w")
        self.lblDocumento.pack(side="left")
        self.btCopiarDoc = tk.Button(fila_documento, text="Copiar", width=10,
                                     command=self.copiar_doc_al_clipboard)
        self.btCopiarDoc.pack(side="left", padx=(MARGEN, 0))
        self.btEditar = tk.Button(fila_documento, text="Editar", width=10,
                                  command=self.editar_persona)
        self.btEditar.pack(side="left", padx=(MARGEN, 0))

        tk.Label(der, text="Notas:", anchor="w").grid(row=4, column=0, sticky="ew",
                                                       pady=(MARGEN, 0))
        marco_notas = tk.Frame(der)
        marco_notas.grid(row=5, column=0, sticky="nsew")
        scroll_notas = tk.Scrollbar(marco_notas, orient="vertical")
        # Un Label de Tk no admite scrollbar: se usa un Text de solo lectura con
        # el aspecto de un label.
        self.lblNotas = tk.Text(marco_notas, width=1, height=1, wrap="word",
                                relief="flat", highlightthickness=0, cursor="arrow",
                                background=self.cget("background"),
                                yscrollcommand=scroll_notas.set)
        scroll_notas.config(command=self.lblNotas.yview)
        scroll_notas.pack(side="right", fill="y")
        self.lblNotas.pack(side="left", fill="both", expand=True)

    # -------------------------------------------------------------- lista --

    def actualizar(self):
        """Relee los JSON de database y regenera la lista."""
        self._registros, errores = cargar_registros(DIRECTORIO_DATABASE)
        self._filtrar(recargar_detalle=True)
        if errores:
            for error in errores:
                log.warning("No se pudo leer un archivo de database: %s", error)
            mas = f"\n... y {len(errores) - 10} más." if len(errores) > 10 else ""
            messagebox.showwarning("Archivos con errores",
                                   f"No se pudieron leer {len(errores)} archivo(s):\n\n"
                                   + "\n".join(errores[:10]) + mas,
                                   parent=self)

    def _filtrar(self, recargar_detalle=False):
        """Muestra en la lista los registros que contienen el texto de txtBuscar
        (en apellido, nombre o documento; y en notas si chkBuscarEnNotas está marcado)."""
        buscado = normalizar(self._buscar.get().strip())
        en_notas = self._buscar_en_notas.get()
        self._visibles = [r for r in self._registros
                          if buscado in r.texto_busqueda
                          or (en_notas and buscado in r.notas_busqueda)]
        self.lstPersonas.delete(0, "end")
        for registro in self._visibles:
            self.lstPersonas.insert("end", registro.texto)
        self.lblCantidadResultados.config(text=texto_cantidad(len(self._visibles)))

        # Mantener seleccionada la persona mostrada, si sigue en la lista.
        ruta_actual = self._actual.ruta_json if self._actual else None
        for i, registro in enumerate(self._visibles):
            if registro.ruta_json == ruta_actual:
                self.lstPersonas.selection_set(i)
                self.lstPersonas.see(i)
                if recargar_detalle:
                    self._mostrar(registro)  # los datos pueden haber cambiado
                return
        self._limpiar_detalle()

    def _al_seleccionar(self, event):
        seleccion = self.lstPersonas.curselection()
        if seleccion:
            self._mostrar(self._visibles[seleccion[0]])

    # ------------------------------------------------------------ detalle --

    def _mostrar(self, registro):
        """Muestra la imagen y los datos de `registro` a la derecha."""
        self._actual = registro
        p = registro.persona
        self.lblApellido.config(text=f"Apellido: {p.apellido}")
        self.lblNombre.config(text=f"Nombre: {p.nombre}")
        self.lblDocumento.config(text=f"Documento: {p.documento}")
        self._poner_notas(p.notas)
        self.btEditar.config(state="normal")
        self.btCopiarDoc.config(state="normal" if p.documento else "disabled")

        try:
            with Image.open(registro.ruta_imagen) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                img.thumbnail((MAX_LADO_PREVIA, MAX_LADO_PREVIA))
                self._imagen = img
                self._mensaje_imagen = ""
        except Exception:
            self._imagen = None
            self._mensaje_imagen = f"No se puede mostrar la imagen {registro.ruta_imagen}."
        self._dibujar_imagen()

    def _limpiar_detalle(self):
        self._actual = None
        self.lblApellido.config(text="Apellido:")
        self.lblNombre.config(text="Nombre:")
        self.lblDocumento.config(text="Documento:")
        self._poner_notas("")
        self.btEditar.config(state="disabled")
        self.btCopiarDoc.config(state="disabled")
        self._imagen = None
        self._mensaje_imagen = ""
        self._dibujar_imagen()

    def _poner_notas(self, texto):
        self.lblNotas.config(state="normal")
        self.lblNotas.delete("1.0", "end")
        self.lblNotas.insert("1.0", texto)
        self.lblNotas.config(state="disabled")
        self.lblNotas.yview_moveto(0)

    def _dibujar_imagen(self):
        """Dibuja la imagen ajustada al tamaño actual del cuadro, sin deformarla."""
        cuadro = self.imgVistaPrevia
        cuadro.delete("all")
        ancho, alto = cuadro.winfo_width(), cuadro.winfo_height()
        if ancho < 2 or alto < 2:  # todavía no tiene tamaño
            return
        if self._imagen is None:
            if self._mensaje_imagen:
                cuadro.create_text(ancho // 2, alto // 2, text=self._mensaje_imagen,
                                   fill="red", width=ancho - 2 * MARGEN)
            return
        self._foto = ImageTk.PhotoImage(ImageOps.contain(self._imagen, (ancho, alto)))
        cuadro.create_image(ancho // 2, alto // 2, image=self._foto, anchor="center")

    # ------------------------------------------------------------ acciones --

    def copiar_doc_al_clipboard(self):
        """Copia al portapapeles el documento mostrado en lblDocumento."""
        if self._actual is None or not self._actual.persona.documento:
            return
        self.clipboard_clear()
        self.clipboard_append(self._actual.persona.documento)
        self.update()  # entrega el contenido al portapapeles del sistema
        # Confirmación breve en el propio botón.
        self.btCopiarDoc.config(text="¡Copiado!")
        if self._after_copiado is not None:
            self.after_cancel(self._after_copiado)
        self._after_copiado = self.after(1500, self._restaurar_bt_copiar)

    def _restaurar_bt_copiar(self):
        self._after_copiado = None
        self.btCopiarDoc.config(text="Copiar")

    def editar_persona(self):
        """Abre el editor (persona_editor.VentanaImagen) con la imagen de la persona
        seleccionada y los datos de su JSON, ambos en la carpeta database."""
        if self._actual is None:
            return
        ruta_imagen, ruta_json = self._actual.ruta_imagen, self._actual.ruta_json

        # Si ya hay un editor abierto para esta imagen, se trae al frente.
        for ventana in self.winfo_children():
            if (isinstance(ventana, VentanaImagen) and ventana.winfo_exists()
                    and os.path.normcase(os.path.realpath(ventana.ruta))
                    == os.path.normcase(os.path.realpath(ruta_imagen))):
                ventana.deiconify()
                ventana.lift()
                ventana.focus_force()
                return

        if not os.path.isfile(ruta_imagen):
            log.warning("Editar: no se encontró la imagen %s", ruta_imagen)
            messagebox.showerror("Error", f"No se encontró la imagen {ruta_imagen}.",
                                 parent=self)
            return
        # Se relee el JSON por si cambió desde la última actualización de la lista.
        try:
            with open(ruta_json, encoding="utf-8") as f:
                persona = Persona.model_validate_json(f.read())
        except (OSError, UnicodeDecodeError, ValidationError) as e:
            log.warning("Editar: no se pudo leer %s: %s", ruta_json, e)
            messagebox.showerror("Error", f"No se pudo leer {ruta_json}.\n\n{e}", parent=self)
            return
        VentanaImagen(self, ruta_imagen, persona)


def main():
    configurar_log()
    app = Galeria()
    app.mainloop()


if __name__ == "__main__":
    main()
