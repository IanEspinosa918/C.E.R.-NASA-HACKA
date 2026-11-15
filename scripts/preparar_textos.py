"""Prepara los textos para el chat con IA (RAG): extrae y parte en fragmentos.

Lee, de cada experimento en data/raw/:
  - la ficha de PSI (objetivo, enfoque, hipótesis, impacto, publicaciones)
  - los documentos de Reports, Science Documents y Presentations (.pdf, .docx, .pptx)
y los parte en fragmentos cortos, cada uno con sus METADATOS: experimento, pilar, DOI,
tipo de documento, archivo y página. Así el chat puede citar de dónde sale cada respuesta.

Salida:   data/processed/fragmentos.jsonl          (un fragmento por línea)
Reporte:  data/reportes/textos_<fecha>.csv         (qué archivo se usó, cuál no y por qué)

Este paso NO necesita base de datos ni modelo de IA. Después se corre
scripts/cargar_fragmentos.py para calcular los vectores y subirlos a Postgres.

Qué NO se incluye (a propósito):
  - Engineering Documents (planos, procedimientos): meten ruido al chat. Usa --con-ingenieria
    si de verdad los necesitas.
  - .doc / .ppt / .xls antiguos, .zip, videos e imágenes: no se pueden leer con este script.
  - PDFs escaneados (sin texto) y fragmentos que son sólo números o símbolos.
  - Documentos repetidos: el mismo archivo aparece en varios experimentos (ej. los de ACME);
    se guarda una vez y los demás experimentos quedan anotados en `tambien_en`.

Requiere:  pip install pypdf
Uso:
  python scripts/preparar_textos.py
  python scripts/preparar_textos.py --ids PSI-69 PSI-39     # sólo algunos experimentos
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun_limpieza as cl  # noqa: E402
from investigaciones import CATALOGO, TODAS  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

CATEGORIAS = {
    "Reports": "reporte",
    "Science Documents": "documento_cientifico",
    "Presentations": "presentacion",
}
CATEGORIA_INGENIERIA = {"Engineering Documents": "ingenieria"}
SALIDA = cl.DIR_PROCESSED / "fragmentos.jsonl"

SECCIONES_FICHA = [
    ("objective", "objetivo"), ("approach", "enfoque"), ("hypothesis", "hipótesis"),
    ("researchImpacts", "impacto y beneficios"), ("description", "descripción"),
]


# ------------------------------------------------------------------ extracción

def texto_pdf(ruta: Path, max_paginas: int) -> tuple[list[tuple[int, str]], str]:
    """Regresa [(página, texto), ...] y una nota."""
    from pypdf import PdfReader
    lector = PdfReader(str(ruta))
    if lector.is_encrypted:
        try:
            lector.decrypt("")
        except Exception:
            return [], "PDF protegido con contraseña"
    total = len(lector.pages)
    paginas = []
    for i in range(min(total, max_paginas)):
        try:
            paginas.append((i + 1, lector.pages[i].extract_text() or ""))
        except Exception:
            continue  # una página dañada no detiene el documento
    nota = f"sólo las primeras {max_paginas} de {total} páginas" if total > max_paginas else ""
    return paginas, nota


def _xml_a_texto(xml: str, parrafo: str, texto: str) -> str:
    parrafos = []
    for p in re.findall(rf"<{parrafo}[ >].*?</{parrafo}>", xml, flags=re.S):
        partes = re.findall(rf"<{texto}(?: [^>]*)?>(.*?)</{texto}>", p, flags=re.S)
        linea = "".join(partes).strip()
        if linea:
            parrafos.append(linea)
    salida = "\n".join(parrafos)
    for entidad, caracter in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")):
        salida = salida.replace(entidad, caracter)
    return salida


def texto_docx(ruta: Path) -> list[tuple[None, str]]:
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return [(None, _xml_a_texto(xml, "w:p", "w:t"))]


def texto_pptx(ruta: Path) -> list[tuple[int, str]]:
    diapositivas = []
    with zipfile.ZipFile(ruta) as z:
        nombres = [n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        for nombre in sorted(nombres, key=lambda n: int(re.findall(r"\d+", n)[-1])):
            xml = z.read(nombre).decode("utf-8", "ignore")
            diapositivas.append((int(re.findall(r"\d+", nombre)[-1]), _xml_a_texto(xml, "a:p", "a:t")))
    return diapositivas


# ------------------------------------------------------------------ fragmentos

_INVALIDOS = re.compile(r"[\ud800-\udfff\x00-\x08\x0b\x0c\x0e-\x1f\x7f￾￿]")


def limpiar(texto: str) -> str:
    # Algunos PDF (sobre todo con fórmulas matemáticas) traen caracteres dañados
    # ("medios caracteres" \ud835, caracteres de control) que no se pueden guardar.
    texto = _INVALIDOS.sub(" ", texto)
    texto = texto.replace(" ", " ").replace("­", "")
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)       # palabras cortadas al final de línea
    texto = re.sub(r"[ \t\r\f\v]+", " ", texto)
    texto = re.sub(r"\s*\n\s*", " ", texto)
    return re.sub(r" {2,}", " ", texto).strip()


def es_util(fragmento: str) -> bool:
    """Descarta pedazos que son tablas de números, índices o texto dañado."""
    if len(fragmento) < 80:
        return False
    letras = sum(c.isalpha() or c == " " for c in fragmento)
    return letras / len(fragmento) >= 0.6 and len(re.findall(r"[A-Za-zÁ-ú]{3,}", fragmento)) >= 10


def partir(texto: str, maximo: int, traslape: int) -> list[str]:
    """Parte en fragmentos de hasta `maximo` caracteres, cortando entre oraciones."""
    texto = limpiar(texto)
    if not texto:
        return []
    oraciones = re.split(r"(?<=[.!?;:])\s+(?=[A-ZÁÉÍÓÚ0-9\"“(\[])", texto)
    piezas = []
    for o in oraciones:  # oraciones larguísimas: cortar en espacios
        while len(o) > maximo:
            corte = o.rfind(" ", 0, maximo)
            corte = corte if corte > maximo // 2 else maximo
            piezas.append(o[:corte].strip())
            o = o[corte:].strip()
        if o:
            piezas.append(o)

    fragmentos, actual = [], ""
    for pieza in piezas:
        if actual and len(actual) + 1 + len(pieza) > maximo:
            fragmentos.append(actual)
            cola = actual[-traslape:] if traslape else ""
            cola = cola[cola.find(" ") + 1:] if " " in cola else ""
            actual = (cola + " " + pieza).strip() if len(cola) + 1 + len(pieza) <= maximo else pieza
        else:
            actual = (actual + " " + pieza).strip()
    if actual:
        fragmentos.append(actual)
    return [f for f in fragmentos if es_util(f)]


def titulo_de(archivo: Path, psi_id: str, categoria: str) -> str:
    nombre = archivo.stem
    for prefijo in (f"{psi_id}_{categoria}_", f"{psi_id}_"):
        if nombre.startswith(prefijo):
            nombre = nombre[len(prefijo):]
            break
    return re.sub(r"[_\s]+", " ", nombre).strip()


# ------------------------------------------------------------------ principal

def fragmentos_de_ficha(psi_id: str, carpeta: Path, base: dict, args) -> list[dict]:
    ficha = json.loads((carpeta / "ficha.json").read_text(encoding="utf-8"))
    nombre = f"{base['experimento']} ({psi_id})"
    bloques = [("datos generales",
                f"{nombre}: {ficha.get('title', '')}. Research area: {ficha.get('researchArea', '')}; "
                f"{ficha.get('subResearchArea', '')}. Project type: {ficha.get('projectType', '')}. "
                f"Platform: {ficha.get('flightProgram', '')}. Hardware: {ficha.get('experimentHardware', '')}. "
                f"Dates: {ficha.get('investigationStartDate', '')} to {ficha.get('investigationEndDate', '')}. "
                f"Related investigations: {ficha.get('related_glds', '')}. DOI: {ficha.get('doi', '')}.")]
    for campo, etiqueta in SECCIONES_FICHA:
        if (ficha.get(campo) or "").strip():
            bloques.append((etiqueta, ficha[campo]))
    publicaciones = [f"{(p.get('title') or '').strip()} ({(p.get('authorList') or '').strip()})"
                     + (f", DOI {p['doi']}" if p.get("doi") else "")
                     for p in (ficha.get("publications") or []) if (p.get("title") or "").strip()]
    if publicaciones:
        bloques.append(("publicaciones", f"Publications of {nombre}: " + ". ".join(publicaciones) + "."))

    salida, orden = [], 0
    for etiqueta, texto in bloques:
        for pedazo in partir(texto, args.max_caracteres, args.traslape):
            salida.append({**base, "tipo_documento": "ficha", "titulo_documento": f"Ficha de PSI: {etiqueta}",
                           "archivo": f"{carpeta.name}/ficha.json", "pagina": None, "orden": orden,
                           "texto": pedazo, "tambien_en": []})
            orden += 1
    return salida


def main() -> int:
    p = argparse.ArgumentParser(description="Extrae y parte los textos para el chat (RAG).")
    p.add_argument("--ids", nargs="+", help="sólo estos experimentos (ej. PSI-69 PSI-39)")
    p.add_argument("--max-caracteres", type=int, default=500, help="tamaño máximo de cada fragmento (default 500)")
    p.add_argument("--traslape", type=int, default=80, help="caracteres repetidos entre fragmentos vecinos (default 80)")
    p.add_argument("--max-paginas", type=int, default=400, help="páginas máximas por PDF (default 400)")
    p.add_argument("--con-ingenieria", action="store_true", help="incluir también Engineering Documents")
    args = p.parse_args()

    try:
        import pypdf  # noqa: F401
    except ImportError:
        raise SystemExit("Falta pypdf. Instálalo con:  pip install -r requirements.txt")
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    categorias = {**CATEGORIAS, **(CATEGORIA_INGENIERIA if args.con_ingenieria else {})}
    ids = args.ids or list(TODAS)
    fragmentos, reporte = [], []
    por_hash: dict[str, dict] = {}       # hash del archivo -> {"experimento": id, "fragmentos": [...]}
    textos_vistos: set[str] = set()      # para no repetir el mismo fragmento

    for psi_id in ids:
        try:
            carpeta = cl.carpeta_experimento(psi_id)
        except FileNotFoundError as e:
            print(f"!! {psi_id}: {e}")
            continue
        pilar = CATALOGO.get(psi_id, ("", "", "", ""))[0]
        ficha = json.loads((carpeta / "ficha.json").read_text(encoding="utf-8"))
        base = {"experimento_id": psi_id,
                "experimento": (ficha.get("investigationAcronym") or TODAS.get(psi_id, psi_id)).strip(),
                "pilar": pilar, "doi": (ficha.get("doi") or "").strip()}
        propios = fragmentos_de_ficha(psi_id, carpeta, base, args)
        fragmentos.extend(propios)
        print(f"\n== {psi_id} ({base['experimento']}): ficha -> {len(propios)} fragmentos")

        for categoria, tipo in categorias.items():
            for archivo in sorted((carpeta / categoria).rglob("*")) if (carpeta / categoria).is_dir() else []:
                if not archivo.is_file():
                    continue
                relativo = archivo.relative_to(cl.DIR_RAW).as_posix()
                extension = archivo.suffix.lower()
                fila = {"experimento": psi_id, "archivo": relativo, "tipo": tipo, "paginas": "", "fragmentos": 0,
                        "estado": "", "detalle": ""}
                reporte.append(fila)
                if extension not in (".pdf", ".docx", ".pptx"):
                    fila["estado"] = "omitido"
                    fila["detalle"] = f"formato {extension or '(sin extensión)'} no soportado"
                    continue

                huella = hashlib.sha1(archivo.read_bytes()).hexdigest()
                if huella in por_hash:
                    original = por_hash[huella]
                    if original["experimento"] != psi_id:
                        for f in original["fragmentos"]:
                            if psi_id not in f["tambien_en"]:
                                f["tambien_en"].append(psi_id)
                    fila["estado"] = "duplicado"
                    fila["detalle"] = f"mismo archivo que {original['archivo']}"
                    continue

                try:
                    nota = ""
                    if extension == ".pdf":
                        paginas, nota = texto_pdf(archivo, args.max_paginas)
                    elif extension == ".docx":
                        paginas = texto_docx(archivo)
                    else:
                        paginas = texto_pptx(archivo)
                except Exception as e:
                    fila["estado"], fila["detalle"] = "error", f"{type(e).__name__}: {e}"[:200]
                    print(f"   ERROR {archivo.name[:70]}: {type(e).__name__}")
                    continue

                titulo = titulo_de(archivo, psi_id, categoria)
                del_archivo, orden, claves = [], 0, set()
                try:
                    for pagina, texto in paginas:
                        for pedazo in partir(texto, args.max_caracteres, args.traslape):
                            clave = hashlib.md5(pedazo.lower().encode("utf-8", "replace")).hexdigest()
                            if clave in textos_vistos or clave in claves:
                                continue
                            claves.add(clave)
                            del_archivo.append({**base, "tipo_documento": tipo, "titulo_documento": titulo,
                                                "archivo": relativo, "pagina": pagina, "orden": orden,
                                                "texto": pedazo, "tambien_en": []})
                            orden += 1
                except Exception as e:  # un archivo raro no detiene todo el proceso
                    fila["estado"], fila["detalle"] = "error", f"{type(e).__name__}: {e}"[:200]
                    print(f"   ERROR {archivo.name[:70]}: {type(e).__name__}")
                    continue
                textos_vistos.update(claves)
                por_hash[huella] = {"experimento": psi_id, "archivo": relativo, "fragmentos": del_archivo}
                fragmentos.extend(del_archivo)
                fila["paginas"] = len(paginas)
                fila["fragmentos"] = len(del_archivo)
                fila["estado"] = "procesado" if del_archivo else "sin texto"
                fila["detalle"] = nota or ("" if del_archivo else "sin texto útil (¿PDF escaneado o sólo imágenes?)")
                print(f"   {fila['estado']:9} {len(del_archivo):5} fragmentos  {archivo.name[:75]}")

    cl.DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    cl.DIR_REPORTES.mkdir(parents=True, exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        for fragmento in fragmentos:
            f.write(json.dumps(fragmento, ensure_ascii=False) + "\n")
    archivo_reporte = cl.DIR_REPORTES / f"textos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(archivo_reporte, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["experimento", "archivo", "tipo", "paginas", "fragmentos", "estado", "detalle"])
        w.writeheader()
        w.writerows(reporte)

    from collections import Counter
    estados = Counter(r["estado"] for r in reporte)
    por_tipo = Counter(f["tipo_documento"] for f in fragmentos)
    print("\n================ RESUMEN ================")
    print(f"Fragmentos: {len(fragmentos)}  ->  {SALIDA}")
    print("   por tipo:", ", ".join(f"{k}={v}" for k, v in por_tipo.most_common()))
    print("Archivos:  ", ", ".join(f"{k}={v}" for k, v in estados.most_common()))
    print(f"Reporte:    {archivo_reporte}")
    print("Siguiente paso:  python scripts/cargar_fragmentos.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
