# Trampas conocidas en los datos de PSI

No son trampas puestas a propósito: son problemas normales de datos científicos reales.
Revisar esta lista al limpiar los CSV (Fase 1).

## Selección
- La búsqueda "combustion" trae PSI-181 y PSI-108 (no son de fuego) y no trae DAFT (PSI-47).
- FLEX/FLEX-2 y SAME/SAME-R son continuaciones; los 5 estudios en tierra reutilizan datos
  de vuelo. No contarlos como evidencia independiente.
- Los estudios en tierra son **modelos**, no mediciones: marcarlos distinto.

## CSV
| Problema | Ejemplo |
|---|---|
| Unidades dentro de las celdas | Saffire-II: "29 cm", "80 W", "9.2 s" |
| Aproximados y rangos | "~ 21.5", "21.5 - 21.7" |
| Texto en columnas numéricas | "Insignificant", "Complete", "n/a", "none" |
| Unidades distintas | Presión en mmHg (FLEX), atm (CFI), psi (reto); oxígeno como fracción (FLEX) o como % |
| Valores no físicos | BASS-II: "Fan display" / "Air display" no son cm/s |
| Dos números de prueba | BASS: "Test #" (planeado) vs "As Run Test #" (real) |
| Fechas sin año | SAME-R: "21-Jul" |
| Abreviaturas | SAME-R: "Rt/R0" → buscar en Read Me / reportes |
| Encabezados dañados | Saffire-II: "?-g Burn Length" (µ perdida), "Samle Thickness" |
| Unidad sospechosa | FLEX: "Burning rate; mm" (lo normal es mm²/s) → verificar |
| Tablas sin resultados | Saffire-III solo trae configuración |
| Valores raros | BASS-II prueba B2: oxígeno final 1.6 % → revisar |

## Interpretación
- FLEX "Test end": **Extinction ≠ Disruption** (la gota se rompió o movió).
- Llamas frías: la flama visible desaparece pero la combustión sigue.
- **Sin datos ≠ seguro.** En los mapas, las zonas sin pruebas son "sin datos", no "verde".
- Microgravedad ≠ Luna. No hay datos de gravedad parcial en PSI.
- E-FIELD imita gravedad parcial; no es gravedad real.
- Saffire se hizo en Cygnus, no en la ISS; columnas "1-g" de Saffire-II son pruebas en tierra.
- Cohetes y propelentes: fuera de alcance.

## FLEX (revisado a fondo; ya lo resuelve `scripts/limpiar_flex.py`)
- El CSV viene en Windows-1252 y perdió los subíndices: "O", "N", "CO" son **O₂, N₂, CO₂**
  (las 4 fracciones suman 1 y "CO" llega a 0.70, sólo posible para CO₂).
- "Burning rate; mm" es la constante de quemado en **mm²/s**.
- Prueba 114: presión 0 (imposible). Pruebas 70 y 73: mismo identificador, fecha y hora
  con mediciones distintas. Pruebas 223 y 224: tiempos aproximados ("~6", "~9").
- "Test end" también puede ser **Completion** (se quemó toda la gota).

## Dónde están los datos buenos (no siempre en el CSV)
- **BASS**: el CSV solo trae el material; condiciones y notas en
  `Science Documents/..._As Run_Test Matrix.xlsx`.
- **BASS-II**: `Science Documents/..._Test.Matrices.xlsx`, una hoja por investigador.
  El oxígeno varía de ~17 % a 22 %.
- **CFI**: el CSV (87 filas) no tiene resultados; el Excel
  `CFI_DataSummary_Spreadsheet_Jan2021.xlsx` tiene 227 pruebas con resultados.
- **FLEX-2**: el CSV es la matriz de diseño (rangos planeados), **no resultados**.
- **ACME BRE, CLD, E-FIELD, s-Flame, SLICE, DAFT**: bitácoras (fechas y flamas
  encendidas), no resultados por prueba.

## Archivos rotos o raros en PSI (encontrados al descargar)
- 5 archivos de Saffire (PSI-98 y PSI-100) aparecen en PSI pero no existen en el servidor
  de la NASA (error 404): las presentaciones del ICES 45, 46 y 47 y "SAFFIRE Offgassing
  Testing Strategy" (repetido en PSI-98 y PSI-100). No se pueden descargar.
- Algunos nombres de archivo contienen "/" (ej. en PSI-22); el script los guarda con "_".
- PSI reporta mal el tamaño de algunos archivos (ej. un documento de ingeniería de PSI-20).

## Versiones y citas
- Los experimentos tienen versiones (ej. BASS v4). Guardar con qué versión se trabajó.
- El campo `added` de la ficha solo lista archivos de la última versión; el script usa
  el listado completo de archivos.
- Citar siempre el DOI.

## IA
- El chat puede inventar datos: debe responder solo con lo encontrado y decir
  "no hay datos" cuando no haya.
