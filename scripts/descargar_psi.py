"""Descarga los experimentos de combustión de NASA PSI a data/raw/.

Baja, por cada experimento:
  - ficha.json            -> la ficha completa (objetivos, método, DOI, publicaciones...)
  - listado_archivos.json -> la lista completa de archivos que tiene PSI
  - los archivos de cada categoría (tabla CSV, documentos, presentaciones...)

NUNCA baja "Raw Data" (son terabytes de video e imágenes).

Uso (desde la carpeta del proyecto):
  python scripts/descargar_psi.py                  # fichas + tablas + documentos
  python scripts/descargar_psi.py --solo-tablas    # rápido: solo fichas y CSV
  python scripts/descargar_psi.py --todo           # además Analyzed Data, Reference Data, Calibration
  python scripts/descargar_psi.py --ids PSI-69 PSI-26
  python scripts/descargar_psi.py --max-mb 100     # saltar archivos de más de 100 MB
  python scripts/descargar_psi.py --solo-listar    # no descarga, solo muestra qué bajaría

Se puede correr varias veces: lo que ya está descargado completo no se vuelve a bajar.
Solo usa la librería estándar de Python (no hace falta pip install).

Nota: usa la API interna que alimenta la página de PSI (no es una API pública
documentada). Si PSI cambia su página, este script podría dejar de funcionar.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from investigaciones import TIERRA, TODAS  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

BASE = "https://psi.nasa.gov/geode-py/ws"
RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_REPORTES = RAIZ / "data" / "reportes"

USER_AGENT = "HackatonNASA-SpaceApps/1.0 (descarga de datos PSI para hackaton)"
TIMEOUT = 90
REINTENTOS = 3

CATEGORIA_EXCLUIDA = "raw data"
CATEGORIAS_EXTRA = {"analyzed data", "reference data", "calibration"}
CATEGORIAS_TABLAS = {"experimental table", "modeling table", "investigation metadata files", "read me", "readme"}


# --------------------------------------------------------------------------- red

def _peticion(url: str, datos: dict | None = None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    cuerpo = None
    if datos is not None:
        cuerpo = json.dumps(datos).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=cuerpo, headers=headers)


class NoDisponibleEnNasa(Exception):
    """PSI da el enlace, pero el archivo no existe en el servidor de la NASA."""


def _con_reintentos(funcion, descripcion: str):
    ultimo_error = None
    for intento in range(1, REINTENTOS + 1):
        try:
            return funcion()
        except urllib.error.HTTPError as e:
            ultimo_error = e
            if 400 <= e.code < 500 and e.code != 429:
                break  # error del lado del cliente: reintentar no sirve
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            ultimo_error = e
        time.sleep(2 * intento)
    raise RuntimeError(f"{descripcion}: {ultimo_error}") from ultimo_error


def obtener_json(url: str, datos: dict | None = None):
    def hacer():
        with urllib.request.urlopen(_peticion(url, datos), timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    return _con_reintentos(hacer, f"No se pudo leer {url}")


def obtener_texto(url: str) -> str:
    def hacer():
        with urllib.request.urlopen(_peticion(url), timeout=TIMEOUT) as r:
            return r.read().decode("utf-8")
    return _con_reintentos(hacer, f"No se pudo leer {url}")


def url_de_descarga(psi_id: str, nombre: str, version) -> str:
    """PSI regresa un enlace temporal (S3 firmado) para cada archivo."""
    consulta = urllib.parse.urlencode({"file": nombre, "version": version, "redirect": "false"})
    texto = obtener_texto(f"{BASE}/studies/{psi_id}/download?{consulta}").strip()
    if texto.startswith('"'):
        texto = json.loads(texto)
    if not texto.startswith("http"):
        raise RuntimeError(f"Respuesta inesperada al pedir {nombre}: {texto[:120]}")
    return texto


def descargar_a_disco(url: str, destino: Path) -> int:
    temporal = destino.with_name(destino.name + ".part")

    def hacer():
        total = 0
        with urllib.request.urlopen(_peticion(url), timeout=TIMEOUT) as r, open(temporal, "wb") as f:
            while True:
                bloque = r.read(1024 * 256)
                if not bloque:
                    break
                f.write(bloque)
                total += len(bloque)
        return total

    try:
        total = _con_reintentos(hacer, f"Falló la descarga de {destino.name}")
    except RuntimeError as e:
        if temporal.exists():
            temporal.unlink()
        if isinstance(e.__cause__, urllib.error.HTTPError) and e.__cause__.code in (403, 404):
            raise NoDisponibleEnNasa(str(e)) from e
        raise
    temporal.replace(destino)
    return total


# ---------------------------------------------------------------- nombres/rutas

_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def limpiar_nombre(nombre: str) -> str:
    """Quita caracteres que Windows no permite en nombres de archivo/carpeta."""
    limpio = _INVALIDOS.sub("_", nombre).strip().rstrip(". ")
    return limpio or "_"


def acortar_si_largo(ruta: Path, limite: int = 240) -> Path:
    """Windows tiene problemas con rutas muy largas: acorta el nombre si hace falta."""
    if len(str(ruta)) <= limite:
        return ruta
    extension = ruta.suffix
    huella = hashlib.md5(ruta.name.encode("utf-8")).hexdigest()[:8]
    sobra = len(str(ruta)) - limite
    base = ruta.stem[: max(10, len(ruta.stem) - sobra - 10)]
    return ruta.with_name(f"{base}_{huella}{extension}")


# ------------------------------------------------------------ listado de archivos

def aplanar(nodos: list, categoria: str, clave_padre: str) -> list[dict]:
    """El listado de PSI viene anidado por carpetas; lo convertimos en lista plana.

    Ojo: algunos nombres de archivo de PSI contienen "/" (ej. "... - ACME/CIR ....pdf"),
    así que el nombre se calcula respecto a la carpeta padre y no cortando en la última "/".
    """
    salida = []
    for nodo in nodos or []:
        hijos = nodo.get("files") or []
        clave = nodo.get("key") or ""
        if nodo.get("directory") or hijos:
            padre = clave if clave.endswith("/") else clave_padre
            salida.extend(aplanar(hijos, categoria, padre))
            continue
        if not clave or clave.endswith("/"):
            continue
        if clave_padre and clave.startswith(clave_padre):
            nombre = clave[len(clave_padre):]
        else:
            nombre = clave.rsplit("/", 1)[-1]
        salida.append({
            "categoria": categoria,
            "clave": clave,
            "carpeta_padre": clave_padre,
            "nombre": nombre,
            "bytes": int(float(nodo.get("bytes_size") or 0)),
            "version": nodo.get("version") or 1,
            "restringido": bool(nodo.get("restricted") or nodo.get("restrictedAccess")),
        })
    return salida


def decidir(archivo: dict, args) -> str | None:
    """Regresa None si se descarga, o el motivo por el que se salta."""
    cat = archivo["categoria"].strip().lower()
    if cat == CATEGORIA_EXCLUIDA:
        return "Raw Data (excluido siempre)"
    if archivo["restringido"]:
        return "acceso restringido"
    if args.solo_tablas and cat not in CATEGORIAS_TABLAS:
        return "modo --solo-tablas"
    if cat in CATEGORIAS_EXTRA and not args.todo:
        return "categoría extra (usar --todo)"
    if args.max_mb and archivo["bytes"] > args.max_mb * 1024 * 1024:
        return f"pesa más de {args.max_mb} MB"
    return None


def ruta_local(carpeta: Path, psi_id: str, archivo: dict) -> Path:
    """Respeta la estructura de carpetas de PSI dentro de la carpeta del experimento."""
    prefijo = f"psi-data/{psi_id}/"
    padre = archivo.get("carpeta_padre") or ""
    padre_rel = padre[len(prefijo):] if padre.startswith(prefijo) else limpiar_nombre(archivo["categoria"])
    partes = [limpiar_nombre(p) for p in padre_rel.split("/") if p]
    partes.append(limpiar_nombre(archivo["nombre"]))  # una "/" dentro del nombre se vuelve "_"
    return acortar_si_largo(carpeta.joinpath(*partes))


# ------------------------------------------------------------------- principal

def procesar_investigacion(psi_id: str, alias: str, args, log) -> tuple[dict, list]:
    print(f"\n== {psi_id} ({alias}) ==")
    ficha = obtener_json(f"{BASE}/repo/investigations/{psi_id}")
    acronimo = ficha.get("investigationAcronym") or alias
    carpeta = DIR_RAW / limpiar_nombre(f"{psi_id}_{acronimo}".replace(" ", "-").replace("/", "-"))
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "ficha.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")

    version = ficha.get("version")
    listado = obtener_json(f"{BASE}/files/v2", {
        "folder": "", "fileType": "study", "studyId": psi_id, "version": version,
    })
    (carpeta / "listado_archivos.json").write_text(json.dumps(listado, ensure_ascii=False, indent=2), encoding="utf-8")

    archivos = []
    for categoria in listado.get("files", []):
        nombre_cat = categoria.get("displayName") or "Sin categoría"
        clave_cat = categoria.get("key") or ""
        archivos.extend(aplanar(categoria.get("files"), nombre_cat, clave_cat))

    tareas, saltados = [], 0
    for a in archivos:
        motivo = decidir(a, args)
        if motivo:
            saltados += 1
            log.append([psi_id, a["categoria"], a["nombre"], a["bytes"], "saltado", motivo])
            continue
        tareas.append((psi_id, a, ruta_local(carpeta, psi_id, a)))

    mb = sum(t[1]["bytes"] for t in tareas) / 1e6
    print(f"   versión {version} | {len(archivos)} archivos en PSI | a descargar: {len(tareas)} ({mb:,.1f} MB) | saltados: {saltados}")

    resumen = {
        "id": psi_id,
        "acronimo": acronimo,
        "tipo": "tierra" if psi_id in TIERRA else "vuelo",
        "titulo": ficha.get("title", ""),
        "doi": ficha.get("doi", ""),
        "version": version,
        "area": ficha.get("researchArea", ""),
        "subarea": ficha.get("subResearchArea", ""),
        "equipo": ficha.get("experimentHardware", ""),
        "carpeta": carpeta.name,
        "archivos_en_psi": len(archivos),
        "archivos_a_descargar": len(tareas),
        "mb_a_descargar": round(mb, 1),
    }
    return resumen, tareas


MANIFIESTO = DIR_RAW / "_manifiesto.json"
_manifiesto: dict = {}
_candado = threading.Lock()


def cargar_manifiesto() -> None:
    """Registro de lo ya descargado: evita volver a bajar archivos cuyo tamaño
    real no coincide con el que reporta PSI (pasa con algunos archivos)."""
    global _manifiesto
    try:
        _manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        _manifiesto = {}


def guardar_manifiesto() -> None:
    with _candado:
        MANIFIESTO.write_text(json.dumps(_manifiesto, ensure_ascii=False, indent=1), encoding="utf-8")


def descargar_uno(tarea) -> tuple[str, str]:
    psi_id, archivo, destino = tarea
    clave_m = f"{archivo['clave']}@v{archivo['version']}"
    if destino.exists():
        tam = destino.stat().st_size
        if (archivo["bytes"] and tam == archivo["bytes"]) or _manifiesto.get(clave_m) == tam:
            return "ya existía", ""
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = url_de_descarga(psi_id, archivo["nombre"], archivo["version"])
    try:
        escritos = descargar_a_disco(url, destino)
    except NoDisponibleEnNasa:
        return "no disponible en NASA", "PSI da el enlace pero el archivo no existe en su servidor"
    with _candado:
        _manifiesto[clave_m] = escritos
    if archivo["bytes"] and escritos != archivo["bytes"]:
        return "descargado (tamaño distinto al que reporta PSI)", f"{escritos} vs {archivo['bytes']}"
    return "descargado", ""


def main() -> int:
    p = argparse.ArgumentParser(description="Descarga experimentos de combustión de NASA PSI.")
    p.add_argument("--ids", nargs="+", help="solo estos experimentos (ej. PSI-69 PSI-26)")
    p.add_argument("--solo-tablas", action="store_true", help="solo fichas, CSV y metadatos")
    p.add_argument("--todo", action="store_true", help="incluir Analyzed Data, Reference Data y Calibration")
    p.add_argument("--max-mb", type=float, default=300, help="saltar archivos más grandes que esto (0 = sin límite)")
    p.add_argument("--hilos", type=int, default=4, help="descargas simultáneas (default 4)")
    p.add_argument("--solo-listar", action="store_true", help="no descargar, solo mostrar qué se bajaría")
    args = p.parse_args()

    ids = args.ids or list(TODAS)
    desconocidos = [i for i in ids if i not in TODAS]
    if desconocidos:
        print(f"Aviso: {desconocidos} no están en scripts/investigaciones.py; se intentarán igual.")

    DIR_RAW.mkdir(parents=True, exist_ok=True)
    DIR_REPORTES.mkdir(parents=True, exist_ok=True)
    cargar_manifiesto()
    print(f"Destino: {DIR_RAW}")

    log: list[list] = []
    resumenes, todas_las_tareas, fallas_fichas = [], [], []
    for psi_id in ids:
        try:
            resumen, tareas = procesar_investigacion(psi_id, TODAS.get(psi_id, psi_id), args, log)
            resumenes.append(resumen)
            todas_las_tareas.extend(tareas)
        except Exception as e:  # seguir con los demás aunque uno falle
            print(f"   ERROR: {e}")
            fallas_fichas.append(psi_id)
            log.append([psi_id, "", "ficha/listado", 0, "error", str(e)])

    total_mb = sum(t[1]["bytes"] for t in todas_las_tareas) / 1e6
    print(f"\nTotal a descargar: {len(todas_las_tareas)} archivos, {total_mb:,.1f} MB")

    if not args.solo_listar and todas_las_tareas:
        hechos = 0
        with ThreadPoolExecutor(max_workers=max(1, args.hilos)) as pool:
            futuros = {pool.submit(descargar_uno, t): t for t in todas_las_tareas}
            for futuro in as_completed(futuros):
                psi_id, archivo, destino = futuros[futuro]
                hechos += 1
                try:
                    estado, detalle = futuro.result()
                except Exception as e:
                    estado, detalle = "error", str(e)
                log.append([psi_id, archivo["categoria"], archivo["nombre"], archivo["bytes"], estado, detalle])
                marca = {"error": "ERROR", "no disponible en NASA": "FALTA"}.get(estado, "ok")
                print(f"   [{hechos}/{len(todas_las_tareas)}] {marca:5} {psi_id} {archivo['nombre'][:70]}")
                if hechos % 25 == 0:
                    guardar_manifiesto()
        guardar_manifiesto()

    # Índice de experimentos (con DOI para las citas)
    if resumenes:
        with open(DIR_RAW / "indice.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(resumenes[0].keys()))
            w.writeheader()
            w.writerows(resumenes)

    # Reporte de la descarga
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    reporte = DIR_REPORTES / f"descarga_{sello}.csv"
    with open(reporte, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "categoria", "archivo", "bytes", "estado", "detalle"])
        w.writerows(log)

    errores = [r for r in log if r[4] == "error"]
    faltantes = [r for r in log if r[4] == "no disponible en NASA"]
    print("\n================ RESUMEN ================")
    print(f"Experimentos procesados: {len(resumenes)} de {len(ids)}")
    if fallas_fichas:
        print(f"Experimentos con error en la ficha: {', '.join(fallas_fichas)}")
    print(f"Archivos con error: {len(errores)}")
    if faltantes:
        print(f"Archivos que la NASA lista pero no existen en su servidor: {len(faltantes)}")
        print("   (no es un error del script; no se pueden descargar)")
        for r in faltantes:
            print(f"   - {r[0]}: {r[2]}")
    print(f"Índice de experimentos: {DIR_RAW / 'indice.csv'}")
    print(f"Reporte detallado:     {reporte}")
    if errores or fallas_fichas:
        print("Vuelve a correr el script para reintentar lo que falló.")
    return 1 if (errores or fallas_fichas) else 0


if __name__ == "__main__":
    sys.exit(main())
