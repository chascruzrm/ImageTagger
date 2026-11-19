"""Punto de entrada: muestra la galería y monitorea un directorio (sin
recursividad) buscando archivos nuevos cada 1 segundo.

Por cada imagen nueva (jpg, jpeg, png, gif) abre una ventana para cargar sus datos.

Tkinter solo puede usarse desde el thread principal: el thread del monitor deja
los archivos detectados en una cola y el thread principal (que corre el mainloop
de Tk) la revisa periódicamente y llama a nuevo_archivo_detectado().
"""

VERSION = "1.0.0 - 2026-11-18"
AUTOR = "Roberto Marcelo Chas Cruz"
EMAIL = "chascruzrm2@gmail.com"
LICENCE = "GPLv3"
TITULO_APLICACION = f"ImageTagger v. {VERSION} - {AUTOR}"

import configparser
import os
import queue
import signal
import sys

from app_config import leer_directorio_monitoreo
from filesystem_service import MonitorDirectorio, nuevo_archivo_detectado
from gallery import Galeria
from persona_editor import VentanaImagen


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


def main():
    # Un argumento en la línea de comandos tiene prioridad sobre config.ini.
    try:
        directorio = sys.argv[1] if len(sys.argv) > 1 else leer_directorio_monitoreo()
    except (ValueError, configparser.Error) as e:
        print(f"Error de configuración: {e}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(directorio):
        print(f"El directorio a monitorear no existe: {directorio}", file=sys.stderr)
        sys.exit(1)

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
                except Exception as e:
                    print(f"Error en nuevo_archivo_detectado: {e}", file=sys.stderr)
        finally:
            root.after(100, procesar_cola)

    root.after(100, procesar_cola)
    # Ctrl+C: Tk atrapa KeyboardInterrupt dentro de los callbacks, así que se
    # usa un manejador de señal que termina el mainloop.
    signal.signal(signal.SIGINT, lambda *_: root.quit())

    print(f"Monitoreando '{os.path.abspath(directorio)}' (Ctrl+C para salir)...")
    root.mainloop()

    monitor.detener()
    monitor.join()
    root.destroy()
    print("Monitor detenido.")


if __name__ == "__main__":
    main()
