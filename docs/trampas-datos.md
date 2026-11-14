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
| Valores no físicos | BASS-II: "Fan display" es voltaje del ventilador x10 (no velocidad); "Air display" SÍ es cm/s |
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

## BASS-II (ya lo resuelve `scripts/limpiar_bass2.py`)
- "Air display" = velocidad del aire en cm/s (según el ReadMe). "Fan display" = voltaje x10.
- El flujo se cambiaba durante la prueba: "5 3 2 1 ext" = se bajó hasta que se apagó.
  En el CSV se perdieron las comas ("10, 5, 3" → "10   5   3").
- Mezcla valores de perilla del ventilador ("pots 0.4 0.36", "(0.36)") que NO son cm/s.
- **No hay columna de resultado**: sólo 21 de 129 pruebas lo dicen en el texto
  ("ext", "blowoff", "no ign"). El resto hay que buscarlo en videos o publicaciones.
- Oxígeno de 13.6 % a 22.2 % (calibrado con un ajuste por día).
- Pruebas B2, P22a y T28a terminan con O2 cercano a 1 %: se marcan, no se interpretan.
- La fecha del video es un día después de la real (error de año bisiesto a bordo).

## CFI (ya lo resuelve `scripts/limpiar_cfi.py`)
- Los datos buenos están en el Excel `CFI_DataSummary_Spreadsheet_Jan2021.xlsx`
  (227 pruebas, hojas Master Sheet + DATA + Comments), no en el CSV (87 filas sin resultados).
- 79 pruebas no tienen análisis numérico ("Completed Analysis? = No"), pero su comentario
  sí describe lo que pasó: sirve para la IA, no para gráficas.
- "Extrap CF? = 1" (34 pruebas): los valores de la llama fría fueron extrapolados.
- "Dext,cool = 0" (49 pruebas): la llama fría consumió toda la gota.
- Constantes de quemado muy bajas (khot hasta 0.001): no son error, son llamas calientes
  que se apagaron casi de inmediato (la gota casi no cambió de tamaño).
- 4 pruebas con O2 0.21 + N2 0.76 = 0.97 (no suman 1) y 2 pruebas (1274A, 1328) con
  diámetro de extinción mayor que el inicial: se marcan.

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
