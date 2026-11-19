"""Editor de los datos de la persona de una imagen (VentanaImagen) y diálogos relacionados."""

import os
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageOps, ImageTk
from pydantic import ValidationError

from app_config import DIRECTORIO_DATABASE, DIRECTORIO_DESCARTADOS, EVENTO_DATABASE_MODIFICADA
from filesystem_service import mover_a_directorio, mover_archivo, obtener_ruta_disponible
from models import MAX_BYTES_NOTAS, MAX_CARACTERES, Persona

# Tamaño inicial del cuadro de imagen. Al abrir la ventana, el cuadro se ajusta
# para ocupar todo el espacio libre de la ventana maximizada, y queda fijo.
ANCHO_IMAGEN = 800
ALTO_IMAGEN = 698
MIN_LADO_IMAGEN = 200  # el cuadro nunca queda más chico que esto
ANCHO_VENTANA = 1000
MARGEN = 10
COLOR_ESTADO_MODIFICADO = "red"
COLOR_ESTADO_ERROR = "red"
COLOR_ESTADO_OK = "dark green"


def preguntar_si_guardar(padre):
    """Diálogo modal con Cancelar / No guardar / Descartar / Guardar.

    Devuelve "cancelar", "no_guardar", "descartar" o "guardar".
    """
    if padre.state() == "iconic":
        padre.deiconify()

    dlg = tk.Toplevel(padre)
    dlg.title("Cambios sin guardar")
    dlg.transient(padre)
    dlg.resizable(False, False)

    resultado = {"valor": "cancelar"}

    def elegir(valor):
        resultado["valor"] = valor
        dlg.grab_release()
        dlg.destroy()

    tk.Label(dlg, text="Hay datos sin guardar. ¿Desea guardarlos?").pack(
        padx=20, pady=(20, 10))
    marco_botones = tk.Frame(dlg)
    marco_botones.pack(padx=20, pady=(0, 20))
    botones = {}
    for texto, valor in (("Cancelar", "cancelar"),
                         ("No guardar", "no_guardar"),
                         ("Descartar", "descartar"),
                         ("Guardar", "guardar")):
        botones[valor] = tk.Button(marco_botones, text=texto, width=11,
                                   command=lambda v=valor: elegir(v))
        botones[valor].pack(side="left", padx=5)

    dlg.protocol("WM_DELETE_WINDOW", lambda: elegir("cancelar"))
    dlg.bind("<Escape>", lambda e: elegir("cancelar"))
    dlg.bind("<Return>",
             lambda e: e.widget.invoke() if isinstance(e.widget, tk.Button) else None)

    # Centrar sobre la ventana padre.
    dlg.update_idletasks()
    x = padre.winfo_rootx() + (padre.winfo_width() - dlg.winfo_width()) // 2
    y = padre.winfo_rooty() + (padre.winfo_height() - dlg.winfo_height()) // 2
    dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    dlg.grab_set()
    dlg.focus_force()
    botones["guardar"].focus_set()
    dlg.wait_window()
    return resultado["valor"]


class VentanaImagen(tk.Toplevel):
    """Ventana que muestra una imagen y permite cargar sus datos.

    Si se pasa `persona`, los campos se inicializan con sus datos (edición de una
    imagen ya guardada) y se consideran sin cambios.
    """

    def __init__(self, master, ruta, persona: Persona | None = None):
        super().__init__(master)
        # Invisible mientras se arma: para medir el espacio la ventana se
        # maximiza, se restaura y se vuelve a maximizar, y eso no debe verse.
        self._poner_opacidad(0.0)
        self.ruta = ruta
        self._foto = None  # referencia a la PhotoImage para que no la libere el GC
        self._after_topmost = None
        self._variables = []  # StringVar de los Entry (se guardan para que no las libere el GC)
        # Últimos valores guardados (apellido, nombre, documento, notas).
        self._guardado = ("", "", "", "")
        # Tamaño del cuadro de imagen (se recalcula en _ajustar_canvas()).
        self._ancho_canvas, self._alto_canvas = ANCHO_IMAGEN, ALTO_IMAGEN

        self.title(os.path.basename(ruta))
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

        self._construir()
        if persona is not None:
            self._cargar_persona(persona)
        self._mostrar()
        self._ajustar_canvas()
        if self._cargar_imagen():
            # Ya maximizada y con la imagen: recién ahora se hace visible.
            self.update_idletasks()
            self._poner_opacidad(1.0)

    def _poner_opacidad(self, valor):
        try:
            self.attributes("-alpha", valor)
        except tk.TclError:  # sistemas sin soporte de transparencia
            pass

    # ----------------------------------------------------------- interfaz --

    def _construir(self):
        self.canvas = tk.Canvas(self, width=ANCHO_IMAGEN, height=ALTO_IMAGEN,
                                highlightthickness=0, bd=0)
        # Márgenes de 10px: arriba y a los lados de la imagen, entre la imagen
        # y el formulario, y debajo de los botones.
        self.canvas.pack(padx=10, pady=10)

        form = tk.Frame(self)
        form.pack(padx=10, pady=(0, 10))
        # Columnas 0, 2 y 4: campos; columnas 1 y 3: separación de 10px.
        for col, ancho in ((0, 200), (1, 10), (2, 250), (3, 10), (4, 150)):
            form.columnconfigure(col, minsize=ancho)

        vcmd = (self.register(lambda texto: len(texto) <= MAX_CARACTERES), "%P")
        self.txtApellido = self._crear_entry(form, "Apellido", 0, vcmd)
        self.txtNombre = self._crear_entry(form, "Nombre", 2, vcmd)
        self.txtDocumento = self._crear_entry(form, "Documento", 4, vcmd)

        tk.Label(form, text="Notas").grid(row=2, column=0, columnspan=5,
                                          sticky="w", pady=(8, 0))
        marco_notas = tk.Frame(form)
        marco_notas.grid(row=3, column=0, columnspan=5, sticky="ew")
        scroll = tk.Scrollbar(marco_notas, orient="vertical")
        # width=1: el ancho real lo determina la grilla (ancho de los 3 campos).
        self.txtNotas = tk.Text(marco_notas, width=1, height=5, wrap="word",
                                yscrollcommand=scroll.set)
        scroll.config(command=self.txtNotas.yview)
        scroll.pack(side="right", fill="y")
        self.txtNotas.pack(side="left", fill="both", expand=True)
        self.txtNotas.bind("<KeyPress>", self._limitar_tecla_notas)
        self.txtNotas.bind("<<Paste>>", self._pegar_notas)
        self.txtNotas.bind("<<Modified>>", self._al_modificar_notas)

        marco_botones = tk.Frame(form)
        marco_botones.grid(row=4, column=0, columnspan=5, sticky="e", pady=(10, 0))
        self.btGuardar = tk.Button(marco_botones, text="Guardar", width=10,
                                   command=self.guardar)
        self.btDescartar = tk.Button(marco_botones, text="Descartar", width=10,
                                     command=self.confirmar_descartar)
        self.btCerrar = tk.Button(marco_botones, text="Cerrar", width=10,
                                  command=self.cerrar)
        self.btGuardar.pack(side="left", padx=(0, 10))
        self.btDescartar.pack(side="left", padx=(0, 10))
        self.btCerrar.pack(side="left")

        # Estado: alto fijo de 2 líneas para que un mensaje largo no cambie el
        # tamaño del formulario; width=1 para que el ancho lo fije la grilla.
        self.lblEstado = tk.Label(form, text="", width=1, height=2, anchor="nw",
                                  justify="left", wraplength=620)
        self.lblEstado.grid(row=5, column=0, columnspan=5, sticky="ew", pady=(5, 0))

    def _crear_entry(self, form, etiqueta, columna, vcmd):
        tk.Label(form, text=etiqueta).grid(row=0, column=columna, sticky="w")
        variable = tk.StringVar(self)
        variable.trace_add("write", lambda *_: self._al_modificar())
        self._variables.append(variable)
        # width=1: el ancho en píxeles lo fija el minsize de la columna.
        entry = tk.Entry(form, width=1, textvariable=variable,
                         validate="key", validatecommand=vcmd)
        entry.grid(row=1, column=columna, sticky="ew")
        entry.bind("<<Paste>>", self._pegar_entry)
        return entry

    # ------------------------------------------------------------ estado --

    def _poner_estado(self, texto, color="black"):
        # Mensajes en una sola línea (los de error pueden traer saltos de línea).
        self.lblEstado.config(text=" ".join(texto.split()), fg=color)

    def _al_modificar(self):
        """Se llama al cambiar cualquier campo."""
        if self.hay_cambios():
            self._poner_estado("Datos modificados.", COLOR_ESTADO_MODIFICADO)
        else:
            self._poner_estado("")

    def _al_modificar_notas(self, event):
        # <<Modified>> se dispara una sola vez hasta resetear la marca; al
        # resetearla se dispara de nuevo, por eso se ignora cuando está en False.
        if not self.txtNotas.edit_modified():
            return
        self.txtNotas.edit_modified(False)
        self._al_modificar()

    def _error(self, titulo, mensaje, advertencia=False):
        """Muestra el error en un diálogo modal y lo deja en lblEstado."""
        self._poner_estado(mensaje, COLOR_ESTADO_ERROR)
        if advertencia:
            messagebox.showwarning(titulo, mensaje, parent=self)
        else:
            messagebox.showerror(titulo, mensaje, parent=self)

    # ---------------------------------------------- límites de longitud --

    @staticmethod
    def _portapapeles(widget):
        try:
            return widget.clipboard_get()
        except tk.TclError:  # portapapeles vacío o sin texto
            return ""

    def _pegar_entry(self, event):
        """Pega el portapapeles truncado para no superar MAX_CARACTERES."""
        entry = event.widget
        texto = self._portapapeles(entry)
        if entry.selection_present():
            seleccion = entry.index("sel.last") - entry.index("sel.first")
        else:
            seleccion = 0
        libres = MAX_CARACTERES - (len(entry.get()) - seleccion)
        if seleccion:
            entry.delete("sel.first", "sel.last")
        if libres > 0:
            entry.insert("insert", texto[:libres])
        return "break"

    def _texto_notas(self):
        return self.txtNotas.get("1.0", "end-1c")

    def _bytes_libres_notas(self):
        """Bytes disponibles en txtNotas, contando como libre el texto seleccionado
        (que se reemplaza al escribir o pegar)."""
        rango = self.txtNotas.tag_ranges("sel")
        seleccion = self.txtNotas.get(*rango) if rango else ""
        usados = len(self._texto_notas().encode("utf-8")) - len(seleccion.encode("utf-8"))
        return MAX_BYTES_NOTAS - usados

    def _limitar_tecla_notas(self, event):
        """Impide escribir en txtNotas si se supera MAX_BYTES_NOTAS."""
        ch = event.char
        if ch and (ch.isprintable() or ch in "\r\t"):
            if len(ch.encode("utf-8")) > self._bytes_libres_notas():
                return "break"
        return None

    def _pegar_notas(self, event):
        """Pega el portapapeles truncado para no superar MAX_BYTES_NOTAS."""
        texto = self._portapapeles(self.txtNotas)
        libres = max(self._bytes_libres_notas(), 0)
        # Truncar por bytes sin cortar un carácter multibyte a la mitad.
        texto = texto.encode("utf-8")[:libres].decode("utf-8", "ignore")
        rango = self.txtNotas.tag_ranges("sel")
        if rango:
            self.txtNotas.delete(*rango)
        self.txtNotas.insert("insert", texto)
        self.txtNotas.see("insert")
        return "break"

    def _maximizar(self):
        try:
            self.state("zoomed")              # Windows / macOS
        except tk.TclError:
            self.attributes("-zoomed", True)  # Linux

    def _ajustar_canvas(self):
        """Agranda el cuadro de imagen para ocupar todo el espacio libre de la
        ventana maximizada, dejando visible el formulario. El tamaño queda fijo
        mientras la ventana esté abierta."""
        self.update()  # aplica la maximización para poder medir el espacio disponible
        if not self.winfo_exists():
            return
        alto_resto = self.winfo_reqheight() - int(self.canvas.cget("height"))
        self._ancho_canvas = max(self.winfo_width() - 2 * MARGEN, MIN_LADO_IMAGEN)
        self._alto_canvas = max(self.winfo_height() - alto_resto, MIN_LADO_IMAGEN)
        self.canvas.config(width=self._ancho_canvas, height=self._alto_canvas)
        # Tamaño al restaurar la ventana: el que necesita todo el contenido,
        # centrado en la pantalla. Windows ignora la posición si se fija con la
        # ventana maximizada, por eso se pasa a normal un instante.
        self.update_idletasks()
        ancho = max(self.winfo_reqwidth(), ANCHO_VENTANA)
        alto = self.winfo_reqheight()
        x = max((self.winfo_screenwidth() - ancho) // 2, 0)
        y = max((self.winfo_screenheight() - alto) // 2, 0)
        self.state("normal")
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.update_idletasks()
        self._maximizar()

    def _mostrar(self):
        """Maximiza la ventana, la trae al frente y le da el foco."""
        self._maximizar()
        # self.lift()
        # Forzar el frente aunque otra aplicación tenga el foco.
        self.attributes("-topmost", True)
        self._after_topmost = self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()
        self.txtApellido.focus_set()

    def _cargar_imagen(self):
        """Carga la imagen ajustada al cuadro sin deformarla. Devuelve False si falla."""
        try:
            with Image.open(self.ruta) as img:
                img = ImageOps.exif_transpose(img)  # respeta la orientación de la cámara
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                # Escala (agrandando o achicando) hasta el máximo que entra en
                # el cuadro sin deformarla.
                img = ImageOps.contain(img, (self._ancho_canvas, self._alto_canvas))
                self._foto = ImageTk.PhotoImage(img)
        except Exception:
            # La ventana todavía es invisible: se cierra primero y el error se
            # muestra sobre la ventana que queda al frente. Si el error tuviera
            # como dueña a esta ventana invisible, quedaría oculto pero
            # capturando el teclado (cada tecla sonaría como un beep).
            padre = self.master
            self.destroy()
            messagebox.showerror("Error", f"No se puede mostrar la imagen {self.ruta}.",
                                 parent=self._siguiente_ventana(padre))
            return False
        self.canvas.create_image(self._ancho_canvas // 2, self._alto_canvas // 2,
                                 image=self._foto, anchor="center")
        return True

    # -------------------------------------------------------------- datos --

    def _valores_actuales(self):
        return (self.txtApellido.get(), self.txtNombre.get(),
                self.txtDocumento.get(), self.txtNotas.get("1.0", "end-1c"))

    def hay_cambios(self):
        return self._valores_actuales() != self._guardado

    @staticmethod
    def _poner_texto(entry, texto):
        entry.delete(0, "end")
        entry.insert(0, texto)

    def guardar(self):
        """Valida y rectifica los datos con el modelo Persona y llama a guardar_imagen().

        Devuelve True si se guardó.
        """
        if not self.txtNombre.get().strip():
            self._error("Datos incompletos",
                        "El nombre debe tener al menos un carácter.", advertencia=True)
            self.txtNombre.focus_set()
            return False

        try:
            # Persona quita los espacios periféricos y pasa apellido y nombre a mayúsculas.
            persona = Persona(apellido=self.txtApellido.get()[:MAX_CARACTERES],
                              nombre=self.txtNombre.get()[:MAX_CARACTERES],
                              documento=self.txtDocumento.get(),
                              notas=self._texto_notas())
        except ValidationError as e:
            errores = "\n".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
                                for err in e.errors())
            self._error("Datos inválidos", errores, advertencia=True)
            return False

        # Mostrar en pantalla los valores rectificados.
        self._poner_texto(self.txtApellido, persona.apellido)
        self._poner_texto(self.txtNombre, persona.nombre)
        self._poner_texto(self.txtDocumento, persona.documento)
        if persona.notas != self._texto_notas():
            self.txtNotas.delete("1.0", "end")
            self.txtNotas.insert("1.0", persona.notas)

        # Ruta definitiva de la imagen en database. Si ya hay un archivo con ese
        # nombre, se usa uno con sufijo (foto.jpg -> foto_1.jpg).
        if self._en_database():
            # La imagen y su JSON ya están en database: se omite moverlos y solo
            # se actualiza el JSON en su lugar.
            ruta_destino = self.ruta
        else:
            try:
                os.makedirs(DIRECTORIO_DATABASE, exist_ok=True)
            except OSError as e:
                self._error("Error",
                            f"No se pudo crear la carpeta {DIRECTORIO_DATABASE}.\n\n{e}")
                return False
            ruta_destino = obtener_ruta_disponible(DIRECTORIO_DATABASE,
                                                   os.path.basename(self.ruta))

        # El JSON conserva la extensión de la imagen: foto_1.jpg -> foto_1.jpg.json
        ruta_json = ruta_destino + ".json"
        if not self.guardar_imagen(persona, ruta_json):
            return False

        if ruta_destino != self.ruta:
            try:
                mover_archivo(self.ruta, ruta_destino)
            except OSError as e:
                # Sin la imagen, el JSON no sirve: se borra y no se da por guardado.
                try:
                    os.remove(ruta_json)
                except OSError:
                    pass
                self._error("Error",
                            f"No se pudo mover la imagen {self.ruta} a "
                            f"{ruta_destino}. Los datos no se guardaron.\n\n{e}")
                return False
            self.ruta = ruta_destino
            self.title(os.path.basename(self.ruta))

        self._guardado = self._valores_actuales()
        self._poner_estado("Datos guardados correctamente.", COLOR_ESTADO_OK)
        self._avisar_database_modificada()
        return True

    def _avisar_database_modificada(self):
        """Avisa a la galería (ventana principal) que cambió el contenido de database."""
        self.master.event_generate(EVENTO_DATABASE_MODIFICADA, when="tail")

    def _en_database(self):
        """True si la imagen ya está en DIRECTORIO_DATABASE (carpeta database junto
        a main.py). En ese caso guardar() solo actualiza su JSON, sin mover nada.

        Compara rutas reales y normalizadas, así coincide aunque la ruta esté
        escrita de otra forma (relativa, con otras mayúsculas o con "..").
        """
        carpeta_imagen = os.path.dirname(os.path.realpath(self.ruta))
        return (os.path.normcase(carpeta_imagen)
                == os.path.normcase(os.path.realpath(DIRECTORIO_DATABASE)))

    def _cargar_persona(self, persona: Persona):
        """Pone los datos de `persona` en los campos y los toma como ya guardados."""
        self._poner_texto(self.txtApellido, persona.apellido)
        self._poner_texto(self.txtNombre, persona.nombre)
        self._poner_texto(self.txtDocumento, persona.documento)
        self.txtNotas.delete("1.0", "end")
        self.txtNotas.insert("1.0", persona.notas)
        self._guardado = self._valores_actuales()
        self._poner_estado("")

    def guardar_imagen(self, persona: Persona, ruta_json: str) -> bool:
        """Guarda `persona` en el archivo JSON `ruta_json` (ruta completa).

        El archivo se puede volver a leer con Persona.model_validate_json().
        Devuelve True si se guardó.
        """
        temporal = ruta_json + ".tmp"
        try:
            # Se escribe primero un archivo temporal y luego se reemplaza el
            # definitivo, para no dejar un JSON a medio escribir si algo falla.
            with open(temporal, "w", encoding="utf-8") as f:
                f.write(persona.model_dump_json(indent=2))
            os.replace(temporal, ruta_json)
        except OSError as e:
            try:
                os.remove(temporal)
            except OSError:
                pass
            self._error("Error", f"No se pudo guardar el archivo {ruta_json}.\n\n{e}")
            return False
        return True

    def cerrar(self):
        if self.hay_cambios():
            respuesta = preguntar_si_guardar(self)
            if respuesta == "cancelar":
                self.focus_force()
                return
            if respuesta == "descartar":
                self.confirmar_descartar()
                return
            if respuesta == "guardar" and not self.guardar():
                return
        self.destroy()

    def destroy(self):
        # Cancelar el callback pendiente: si se dispara después de cerrar la
        # ventana, su nombre en Tcl puede haber sido reutilizado por otro callback.
        if self._after_topmost is not None:
            self.after_cancel(self._after_topmost)
            self._after_topmost = None
        padre = self.master
        super().destroy()
        self._activar_ventana(self._siguiente_ventana(padre))

    @staticmethod
    def _siguiente_ventana(padre):
        """Ventana a mostrar al cerrar un editor: el editor abierto que esté más
        arriba (el último que se usó); si no queda ninguno, `padre` (la galería)."""
        try:
            editores = [w for w in padre.winfo_children()
                        if isinstance(w, VentanaImagen) and w.winfo_exists()]
            if not editores:
                return padre
            # wm stackorder: ventanas visibles de abajo hacia arriba.
            orden = [str(nombre) for nombre in
                     padre.tk.splitlist(padre.tk.call("wm", "stackorder", padre))]
        except tk.TclError:  # se está cerrando la aplicación
            return padre
        por_nombre = {str(w): w for w in editores}
        for nombre in reversed(orden):
            if nombre in por_nombre:
                return por_nombre[nombre]
        return editores[-1]  # todos minimizados: el último abierto

    @staticmethod
    def _activar_ventana(ventana):
        """Muestra `ventana` (otro editor o la galería) y le da el foco. No hace
        nada si está oculta a propósito (withdraw) o si se cierra la aplicación."""
        try:
            if not ventana.winfo_exists() or ventana.state() == "withdrawn":
                return
            if ventana.state() == "iconic":
                ventana.deiconify()
            ventana.lift()
            # Foco al último campo usado en esa ventana (no a la ventana en sí,
            # porque entonces lo que se tipea no llega a ningún campo).
            (ventana.focus_lastfor() or ventana).focus_force()
        except tk.TclError:  # la ventana se destruyó mientras tanto
            pass

    def confirmar_descartar(self):
        """Pide confirmación y, si el usuario acepta, llama a descartar().

        Se llama desde btDescartar y desde la opción Descartar de preguntar_si_guardar.
        """
        if messagebox.askyesno("Descartar imagen",
                               "¿Está seguro de que desea descartar la imagen?\n\n"
                               f"{self.ruta}",
                               icon="warning", default="no", parent=self):
            self.descartar()
        else:
            self.focus_force()

    def descartar(self):
        """Descarta la imagen self.ruta sin guardar los cambios y cierra la ventana.

        Mueve la imagen a DIRECTORIO_DESCARTADOS (la carpeta se crea si no existe),
        junto con su JSON si lo tiene. Devuelve True si se descartó.
        """
        ruta_json = self.ruta + ".json"
        try:
            mover_a_directorio(self.ruta,
                               ruta_json if os.path.isfile(ruta_json) else None,
                               DIRECTORIO_DESCARTADOS)
        except OSError as e:
            self._error("Error",
                        f"No se pudo mover {self.ruta} a {DIRECTORIO_DESCARTADOS}.\n\n{e}")
            return False
        self._avisar_database_modificada()
        self.destroy()
        return True
