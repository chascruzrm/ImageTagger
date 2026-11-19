"""Punto de entrada: muestra la galería y monitorea un directorio (sin
recursividad) buscando archivos nuevos cada 1 segundo.

Por cada imagen nueva (jpg, jpeg, png, gif) abre una ventana para cargar sus datos.

Tkinter solo puede usarse desde el thread principal: el thread del monitor deja
los archivos detectados en una cola y el thread principal (que corre el mainloop
de Tk) la revisa periódicamente y llama a nuevo_archivo_detectado().
"""

VERSION = "1.0.3 - 2026-11-18"
AUTOR = "Roberto Marcelo Chas Cruz"
EMAIL = "chascruzrm2@gmail.com"
LICENCE = "GPLv3"
TITULO_APLICACION = f"ImageTagger v. {VERSION} - {AUTOR} - {EMAIL}"

import configparser
import logging
import os
import queue
import signal
import sys
from typing import NoReturn

from app_config import ARCHIVO_LOG, configurar_log, leer_directorio_monitoreo
from filesystem_service import MonitorDirectorio, nuevo_archivo_detectado
from gallery import Galeria
from persona_editor import VentanaImagen

log = logging.getLogger("main")


# --------------------------------------------------------------------------- #
# Programa principal
# --------------------------------------------------------------------------- #

def salir(root):
    """Cierra la aplicación desde la galería, cerrando antes cada ventana de
    imagen (que pregunta si hay datos sin guardar). Si el usuario cancela en
    alguna, la aplicación sigue abierta."""
    for ventana in list(root.winfo_children()):
        if isinstance(ventana, VentanaImagen) and ventana.winfo_exists():
            ventana.cerrar()
            if ventana.winfo_exists():  # el usuario canceló
                return
    root.quit()


def error_de_inicio(mensaje) -> NoReturn:
    """Informa un error que impide iniciar y termina el programa.

    Se registra en el log y se muestra en un cuadro de diálogo porque,
    ejecutado con pythonw (sin consola), lo que se imprime no lo ve nadie.
    """
    log.error("No se pudo iniciar: %s", " ".join(mensaje.split()))
    try:
        import tkinter as tk
        from tkinter import messagebox
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(TITULO_APLICACION, mensaje, parent=raiz)
        raiz.destroy()
    except Exception:
        pass
    sys.exit(1)


def main():
    configurar_log()
    log.info("Iniciando ImageTagger v. %s (Python %s, %s)", VERSION,
             sys.version.split()[0], os.path.basename(sys.executable))
    # Un argumento en la línea de comandos tiene prioridad sobre config.ini.
    try:
        directorio = sys.argv[1] if len(sys.argv) > 1 else leer_directorio_monitoreo()
    except (ValueError, configparser.Error) as e:
        error_de_inicio(f"Error de configuración:\n\n{e}")
    if not os.path.isdir(directorio):
        error_de_inicio(f"El directorio a monitorear no existe:\n\n{directorio}\n\n"
                        "Revise 'directorio_monitoreo' en config.ini.")

    # La galería es la ventana principal; las de cada imagen se abren como hijas.
    root = Galeria()
    root.title(TITULO_APLICACION)
    root.protocol("WM_DELETE_WINDOW", lambda: salir(root))

    cola = queue.Queue()
    # Las imágenes guardadas se mueven a database, así que las que siguen en el
    # directorio al iniciar están pendientes: también se procesan.
    monitor = MonitorDirectorio(directorio, cola.put, incluir_existentes=True)
    monitor.start()

    def procesar_cola():
        try:
            while True:
                try:
                    archivos = cola.get_nowait()
                except queue.Empty:
                    break
                try:
                    nuevo_archivo_detectado(
                        archivos, lambda ruta: VentanaImagen(root, ruta))
                except Exception:
                    log.exception("Error al abrir los archivos nuevos %s", archivos)
        finally:
            root.after(100, procesar_cola)

    root.after(100, procesar_cola)
    # Ctrl+C (solo si se ejecuta con python desde una consola): Tk atrapa
    # KeyboardInterrupt dentro de los callbacks, así que se usa un manejador
    # de señal que termina el mainloop.
    signal.signal(signal.SIGINT, lambda *_: root.quit())

    log.info("Monitoreando %s (log: %s)", os.path.abspath(directorio), ARCHIVO_LOG)
    root.mainloop()

    monitor.detener()
    monitor.join()
    root.destroy()
    log.info("ImageTagger cerrado")


if __name__ == "__main__":
    main()
