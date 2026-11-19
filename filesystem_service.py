"""Servicios de sistema de archivos: detección de archivos nuevos en un directorio."""

import os
import shutil
import sys
import threading

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".gif"}


def existe_en_directorio(directorio, nombre_archivo):
    """True si en `directorio` ya existe `nombre_archivo` o su JSON (`nombre_archivo`.json)."""
    ruta = os.path.join(directorio, nombre_archivo)
    return os.path.exists(ruta) or os.path.exists(ruta + ".json")


def obtener_ruta_disponible(directorio, nombre_archivo):
    """Devuelve la ruta completa en `directorio` con la que guardar `nombre_archivo`
    sin pisar otro archivo.

    Si el nombre ya existe (ver existe_en_directorio), agrega un sufijo numérico:
    foto.jpg -> foto_1.jpg, foto_2.jpg, ...
    El JSON correspondiente siempre es <ruta devuelta> + ".json" (foto_1.jpg.json).
    """
    base, ext = os.path.splitext(nombre_archivo)
    candidato, n = nombre_archivo, 1
    while existe_en_directorio(directorio, candidato):
        candidato = f"{base}_{n}{ext}"
        n += 1
    return os.path.join(directorio, candidato)


def mover_archivo(origen, destino):
    """Mueve `origen` a la ruta `destino` (también entre unidades). Lanza OSError si falla."""
    shutil.move(origen, destino)


def mover_a_directorio(ruta_imagen, ruta_json, destino):
    """Mueve la imagen y su JSON a `destino` (lo crea si no existe).

    El JSON se renombra junto con la imagen para que sigan correspondiéndose.
    Si `ruta_json` es None, se mueve solo la imagen.
    Devuelve (nueva_ruta_imagen, nueva_ruta_json o None). Lanza OSError si falla;
    si falla al mover el JSON, la imagen vuelve a su lugar.
    """
    os.makedirs(destino, exist_ok=True)
    nueva_imagen = obtener_ruta_disponible(destino, os.path.basename(ruta_imagen))
    shutil.move(ruta_imagen, nueva_imagen)
    if ruta_json is None:
        return nueva_imagen, None
    nuevo_json = nueva_imagen + ".json"
    try:
        shutil.move(ruta_json, nuevo_json)
    except OSError:
        shutil.move(nueva_imagen, ruta_imagen)
        raise
    return nueva_imagen, nuevo_json


def nuevo_archivo_detectado(archivos, abrir_imagen):
    """Llama a `abrir_imagen(ruta)` por cada imagen (jpg, jpeg, png, gif) de la lista.

    Si `abrir_imagen` usa tkinter, esta función debe llamarse desde el thread principal.
    """
    for ruta in archivos:
        if os.path.splitext(ruta)[1].lower() in EXTENSIONES_IMAGEN:
            abrir_imagen(ruta)


def listar_archivos(directorio):
    """Devuelve el conjunto de rutas de archivos (no subdirectorios) del directorio."""
    try:
        with os.scandir(directorio) as entradas:
            return {e.path for e in entradas if e.is_file()}
    except OSError as e:
        print(f"Error al leer '{directorio}': {e}", file=sys.stderr)
        return None


def _firma_archivo(ruta):
    """(tamaño, fecha de modificación) del archivo, o None si no se puede leer."""
    try:
        estado = os.stat(ruta)
    except OSError:
        return None
    return (estado.st_size, estado.st_mtime_ns)


def _se_puede_abrir(ruta):
    """True si el archivo se puede abrir para lectura (no lo bloquea otra copia)."""
    try:
        with open(ruta, "rb"):
            return True
    except OSError:
        return False


class MonitorDirectorio(threading.Thread):
    """Revisa el directorio (sin recursividad) cada `intervalo` segundos y llama a
    `al_detectar(archivos)` con la lista de archivos nuevos. `al_detectar` corre en
    este thread.

    Un archivo nuevo se informa recién cuando terminó de escribirse: su tamaño y
    fecha no cambiaron entre dos revisiones seguidas y se puede abrir. Así no se
    informan archivos a medio copiar.

    Si `incluir_existentes` es True, los archivos que ya están en el directorio al
    iniciar se informan en las primeras revisiones; si es False, se ignoran.
    """

    def __init__(self, directorio, al_detectar, intervalo=1.0, incluir_existentes=False):
        super().__init__(daemon=True)
        self.directorio = directorio
        self.al_detectar = al_detectar
        self.intervalo = intervalo
        self._detener = threading.Event()
        self._conocidos = set() if incluir_existentes else (listar_archivos(directorio) or set())
        # Archivos nuevos que todavía pueden estar copiándose: ruta -> firma vista.
        self._pendientes = {}

    def _listos(self, nuevos):
        """De los archivos nuevos, devuelve los que ya terminaron de escribirse."""
        listos = set()
        for ruta in nuevos:
            firma = _firma_archivo(ruta)
            if firma is not None and self._pendientes.get(ruta) == firma and _se_puede_abrir(ruta):
                listos.add(ruta)
                del self._pendientes[ruta]
            else:
                self._pendientes[ruta] = firma
        return listos

    def run(self):
        while not self._detener.wait(self.intervalo):
            actuales = listar_archivos(self.directorio)
            if actuales is None:
                continue
            nuevos = self._listos(actuales - self._conocidos)
            # Olvidar pendientes que se borraron antes de terminar de copiarse.
            for ruta in list(self._pendientes):
                if ruta not in actuales:
                    del self._pendientes[ruta]
            # Conocidos = los que siguen existiendo + los recién informados (si un
            # archivo se borra y vuelve a crearse, se detecta de nuevo como nuevo).
            self._conocidos = (self._conocidos & actuales) | nuevos
            if nuevos:
                try:
                    self.al_detectar(sorted(nuevos))
                except Exception as e:
                    print(f"Error al procesar archivos nuevos: {e}", file=sys.stderr)

    def detener(self):
        self._detener.set()
