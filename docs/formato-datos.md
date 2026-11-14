# Formato común de datos

Todas las pruebas de todos los experimentos se convierten a una sola tabla con las
mismas columnas y unidades: `data/processed/pruebas.csv`.
Así el backend, las gráficas, los simuladores y la IA leen todo igual.

## Columnas de `pruebas.csv`

| Columna | Unidad / valores | Ejemplo |
|---|---|---|
| `experimento_id` | ID de PSI | PSI-69 |
| `experimento` | nombre corto | FLEX |
| `prueba_id` | ID de la prueba dentro del experimento | 2-20CAL10 |
| `fecha` | AAAA-MM-DD | 2009-03-05 |
| `gravedad` | `microgravedad` / `gravedad_normal` | microgravedad |
| `tipo_combustible` | `gota` / `gas` / `solido` / `humo` | gota |
| `combustible` | texto | Methanol |
| `presion_atm` | atm | 1.0026 |
| `o2`, `n2`, `co2`, `he` | fracción molar (0 a 1) | 0.21 |
| `flujo_aire_cm_s` | cm/s (vacío = aire quieto o sin dato) | |
| `diametro_inicial_mm` | mm (gotas) | 1.86 |
| `diametro_extincion_mm` | mm (llama visible) | 0.94 |
| `k_quemado_mm2_s` | mm²/s, constante de la ley d² | 0.6 |
| `tiempo_quemado_s` | s | 5 |
| `resultado` | ver abajo | extincion |
| `resultado_original` | texto tal cual venía | Extinction |
| `aproximado` | `si` si algún valor era "~6", un rango, etc. | no |
| `banderas` | problemas detectados, separados por `;` | |
| `notas` | información extra | |
| `doi` | DOI del experimento (para citar) | 10.60555/mbq8-0451 |
| `archivo_origen`, `fila_origen` | de dónde salió exactamente el dato | |

### Valores de `resultado`

| Valor | Significado |
|---|---|
| `extincion` | la llama se apagó antes de consumir el combustible |
| `disrupcion` | la gota se rompió o se movió (**no** es extinción) |
| `combustion_completa` | se consumió todo el combustible |
| `no_encendio` | no encendió |
| `autoextincion` | se apagó sola |
| `corte_de_flujo` | la prueba terminó cortando el flujo |
| `llama_fria` | combustión de llama fría |
| `encendio` | encendió, sin más detalle |
| (vacío) | sin dato |

## Reglas

- **Nunca se borra una prueba**: si un valor es imposible (ej. presión 0) se deja vacío
  y la prueba queda marcada en `banderas`.
- Cada prueba guarda `archivo_origen` y `fila_origen` para poder verificarla.
- Cada limpieza genera un reporte en `data/reportes/validacion_<nombre>.csv`.

## Estado

| Experimento | Script | Pruebas | Notas |
|---|---|---|---|
| FLEX (PSI-69) | `limpiar_flex.py` | 274 | Listo |
| CFI (PSI-39) | pendiente | ~227 | Usar el Excel de Science Documents, no el CSV |
| CFI-G (PSI-159) | pendiente | 333 | Dos CSV: normal e inversa |
| BASS-II (PSI-25) | pendiente | 129 | Excel por investigador; ventilador → cm/s |
| BASS (PSI-26) | pendiente | ~130 | Usar `As Run_Test Matrix.xlsx` |
| Saffire I/II/III | pendiente | 4/15/2 | Unidades dentro de las celdas |
| SAME / SAME-R | pendiente | 8/109 | |
