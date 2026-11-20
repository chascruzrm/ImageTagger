"""Autocompletado reutilizable para tk.Entry.

Uso:
    Autocompletado(entry, fuente)

`fuente(texto, cancelado)` se ejecuta en un thread aparte y devuelve la lista de
sugerencias para `texto`. Debe revisar `cancelado` (threading.Event) cada tanto y
terminar si está activo: significa que se lanzó otra búsqueda. No debe usar tkinter.

Debajo del Entry se muestra una lista flotante (dentro de la misma ventana) con
las sugerencias. El foco queda siempre en el Entry y las teclas se manejan ahí:
  - Escribir (o borrar, pegar...) vuelve a buscar, cancelando la búsqueda anterior.
    Con el Entry vacío no se busca y la lista se oculta.
  - Clic en el Entry: busca con el texto actual.
  - Flecha abajo / arriba: recorre los ítems en forma circular.
  - Enter: reemplaza el texto del Entry por el ítem seleccionado (si hay uno).
  - Escape, Tab o clic fuera: oculta la lista sin cambiar el texto.
  - Clic en un ítem: lo inserta en el Entry.
"""

import logging
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

log = logging.getLogger(__name__)

ID_NO_SELECCIONABLE = -1
TEXTO_BUSCANDO = "Buscando..."
TEXTO_NO_ENCONTRADO = "(Texto no encontrado)"
COLOR_NO_SELECCIONABLE = "gray50"
INTERVALO_REVISION_MS = 50  # cada cuánto se revisa si el thread terminó

Fuente = Callable[[str, threading.Event], list[str]]


class Autocompletado:
    """Lista flotante de sugerencias vinculada a un tk.Entry.

    Parámetros:
        entry: Entry a autocompletar.
        fuente: función que devuelve las sugerencias (ver docstring del módulo).
        ancho: ancho de la lista en píxeles; None = el mismo que el Entry.
        max_filas: máximo de filas visibles (menos si no entran en la ventana).
        demora_ms: espera desde la última tecla hasta lanzar la búsqueda.
    """

    def __init__(self, entry: tk.Entry, fuente: Fuente, ancho: int | None = None,
                 max_filas: int = 8, demora_ms: int = 150):
        self.entry = entry
        self.fuente = fuente
        self.ancho = ancho
        self.max_filas = max_filas
        self.demora_ms = demora_ms

        self._items: list[tuple[int, str]] = []  # (id, texto) de cada fila de la lista
        self._visible = False
        self._texto_buscado = entry.get()  # texto de la última búsqueda pedida
        self._cancelado: threading.Event | None = None  # búsqueda en curso
        self._generacion = 0  # identifica la búsqueda vigente
        self._resultados = queue.Queue()  # (generacion, valores) desde el thread
        self._after_buscar = None
        self._after_revisar = None

        ventana = entry.winfo_toplevel()
        self._marco = tk.Frame(ventana, bd=1, relief="solid")
        self._scroll = tk.Scrollbar(self._marco, orient="vertical", takefocus=0)
        # exportselection=False: seleccionar un ítem no borra la selección del Entry.
        self._lista = tk.Listbox(self._marco, exportselection=False, takefocus=0,
                                 activestyle="none", bd=0, highlightthickness=0,
                                 yscrollcommand=self._scroll.set)
        self._scroll.config(command=self._lista.yview)
        self._scroll.pack(side="right", fill="y")
        self._lista.pack(side="left", fill="both", expand=True)

        # El clic en la lista se maneja acá ("break"): así la lista no toma el foco.
        self._lista.bind("<Button-1>", self._al_clic_lista)
        self._lista.bind("<B1-Motion>", lambda e: "break")

        for evento, funcion in (("<Button-1>", self._al_clic_entry),
                                ("<KeyRelease>", self._al_soltar_tecla),
                                ("<Down>", lambda e: self._mover(1)),
                                ("<Up>", lambda e: self._mover(-1)),
                                ("<Return>", self._al_enter),
                                ("<KP_Enter>", self._al_enter),
                                ("<Escape>", self._al_escape),
                                ("<FocusOut>", lambda e: self.ocultar()),
                                ("<Destroy>", self._al_destruir)):
            entry.bind(evento, funcion, add="+")
        # Clic en cualquier otro lugar de la ventana: ocultar.
        ventana.bind("<Button-1>", self._al_clic_ventana, add="+")

    # ------------------------------------------------------------ público --

    def buscar(self):
        """Lanza la búsqueda con el texto actual del Entry, cancelando la anterior."""
        self._cancelar_after_buscar()
        self._cancelar_busqueda()
        texto = self.entry.get()
        self._texto_buscado = texto
        if not texto:
            self.ocultar()
            return
        self._mostrar_items([(ID_NO_SELECCIONABLE, TEXTO_BUSCANDO)])
        self._generacion += 1
        self._cancelado = threading.Event()
        threading.Thread(target=self._buscar_en_thread,
                         args=(texto, self._cancelado, self._generacion),
                         name="Autocompletado", daemon=True).start()
        if self._after_revisar is None:
            self._after_revisar = self.entry.after(INTERVALO_REVISION_MS,
                                                   self._revisar_resultados)

    def set_autocompleted_text(self, texto: str):
        """Reemplaza el texto del Entry por `texto` y oculta la lista."""
        self.ocultar()
        self.entry.delete(0, "end")
        self.entry.insert(0, texto)
        self.entry.icursor("end")
        self.entry.xview("end")
        self._texto_buscado = texto  # para que no se vuelva a buscar
        self.entry.focus_set()

    def ocultar(self):
        """Oculta la lista y cancela la búsqueda pendiente o en curso."""
        self._cancelar_after_buscar()
        self._cancelar_busqueda()
        if self._visible:
            self._marco.place_forget()
            self._visible = False

    # ---------------------------------------------------------- búsqueda --

    def _programar_busqueda(self, demora_ms):
        """Muestra "Buscando..." y lanza la búsqueda tras `demora_ms`.
        Con el Entry vacío no busca y oculta la lista."""
        self._cancelar_after_buscar()
        self._cancelar_busqueda()
        texto = self.entry.get()
        self._texto_buscado = texto
        if not texto:
            self.ocultar()
            return
        self._mostrar_items([(ID_NO_SELECCIONABLE, TEXTO_BUSCANDO)])
        self._after_buscar = self.entry.after(demora_ms, self.buscar)

    def _buscar_en_thread(self, texto, cancelado, generacion):
        try:
            valores = self.fuente(texto, cancelado)
        except Exception:
            log.exception("Error buscando sugerencias para %r", texto)
            valores = []
        if not cancelado.is_set():
            self._resultados.put((generacion, valores))

    def _revisar_resultados(self):
        """Corre en el thread principal: muestra el resultado de la búsqueda vigente."""
        self._after_revisar = None
        try:
            while True:
                generacion, valores = self._resultados.get_nowait()
                if generacion == self._generacion and self._cancelado is not None:
                    self._cancelado = None  # terminó
                    if valores:
                        self._mostrar_items(list(enumerate(valores)))
                    else:
                        self._mostrar_items([(ID_NO_SELECCIONABLE, TEXTO_NO_ENCONTRADO)])
        except queue.Empty:
            pass
        if self._cancelado is not None:  # sigue buscando
            self._after_revisar = self.entry.after(INTERVALO_REVISION_MS,
                                                   self._revisar_resultados)

    def _cancelar_busqueda(self):
        if self._cancelado is not None:
            self._cancelado.set()
            self._cancelado = None

    def _cancelar_after_buscar(self):
        if self._after_buscar is not None:
            self.entry.after_cancel(self._after_buscar)
            self._after_buscar = None

    # ------------------------------------------------------------- lista --

    def _mostrar_items(self, items):
        """Carga `items` en la lista, sin selección, y la muestra bajo el Entry."""
        self._items = items
        self._lista.delete(0, "end")
        for i, (id_item, texto) in enumerate(items):
            self._lista.insert("end", texto)
            if id_item == ID_NO_SELECCIONABLE:
                self._lista.itemconfig(i, fg=COLOR_NO_SELECCIONABLE)
        self._lista.yview_moveto(0)

        # Filas: las que haya, hasta max_filas y sin salirse de la ventana.
        ventana = self._marco.master
        libre = (ventana.winfo_rooty() + ventana.winfo_height()
                 - self.entry.winfo_rooty() - self.entry.winfo_height() - 2)
        alto_fila = tkfont.Font(font=self._lista.cget("font")).metrics("linespace") + 1
        filas = max(1, min(len(items), self.max_filas, libre // alto_fila))
        self._lista.config(height=filas)

        if self.ancho is None:
            self._marco.place(in_=self.entry, x=0, rely=1.0, relwidth=1.0)
        else:
            self._marco.place(in_=self.entry, x=0, rely=1.0, width=self.ancho)
        self._marco.lift()
        self._visible = True

    def _indice_seleccionado(self):
        seleccion = self._lista.curselection()
        return seleccion[0] if seleccion else None

    def _seleccionar(self, indice):
        self._lista.selection_clear(0, "end")
        self._lista.selection_set(indice)
        self._lista.see(indice)

    # ----------------------------------------------------------- eventos --

    def _al_clic_entry(self, event):
        self._programar_busqueda(0)

    def _al_soltar_tecla(self, event):
        # Solo si cambió el texto: ignora flechas, Shift, Ctrl, Escape, Enter...
        if self.entry.get() != self._texto_buscado:
            self._programar_busqueda(self.demora_ms)

    def _mover(self, paso):
        """Selecciona el ítem siguiente (paso=1) o anterior (paso=-1), en forma circular."""
        if not self._visible:
            return None
        indices = [i for i, (id_item, _) in enumerate(self._items)
                   if id_item != ID_NO_SELECCIONABLE]
        if indices:
            actual = self._indice_seleccionado()
            if actual not in indices:
                nuevo = indices[0] if paso > 0 else indices[-1]
            else:
                nuevo = indices[(indices.index(actual) + paso) % len(indices)]
            self._seleccionar(nuevo)
        return "break"

    def _al_enter(self, event):
        if not self._visible:
            return None
        indice = self._indice_seleccionado()
        if indice is not None and self._items[indice][0] != ID_NO_SELECCIONABLE:
            self.set_autocompleted_text(self._items[indice][1])
        return "break"

    def _al_escape(self, event):
        if not self._visible:
            return None
        self.ocultar()
        self.entry.focus_set()
        return "break"

    def _al_clic_lista(self, event):
        indice = self._lista.nearest(event.y)
        caja = self._lista.bbox(indice) if self._items else None
        if (caja and caja[1] <= event.y < caja[1] + caja[3]
                and self._items[indice][0] != ID_NO_SELECCIONABLE):
            self.set_autocompleted_text(self._items[indice][1])
        return "break"

    def _al_clic_ventana(self, event):
        if self._visible and event.widget not in (self.entry, self._lista,
                                                  self._scroll, self._marco):
            self.ocultar()

    def _al_destruir(self, event):
        # Cancelar los after pendientes: si se disparan con el Entry destruido, fallan.
        self.ocultar()
        if self._after_revisar is not None:
            self.entry.after_cancel(self._after_revisar)
            self._after_revisar = None
