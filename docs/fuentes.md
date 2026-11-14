# Fuentes de datos

## Repositorio principal: NASA PSI (Physical Sciences Informatics)

- Búsqueda: https://psi.nasa.gov/physci/repo/search?q=combustion
- Ficha de cada experimento: `https://psi.nasa.gov/physci/repo/data/investigations/PSI-XX`
- Licencia: CC0-1.0. **Hay que citar el DOI de cada experimento.**
  Los DOI quedan en `data/raw/indice.csv` después de correr el script de descarga.

### Los 24 experimentos

> La búsqueda "combustion" trae 26 resultados, pero PSI-181 (soldaduras) y PSI-108
> (fluidos) no son de fuego, y le falta DAFT (PSI-47). Esta lista ya está corregida.

**En el espacio (19)**

| ID | Experimento | Pilar / uso | Equipo |
|---|---|---|---|
| PSI-26 | BASS | Prevención (sólidos) | MSG, ducto SPICE |
| PSI-25 | BASS-II | Prevención (sólidos) | MSG, ducto SPICE |
| PSI-98 | Saffire-I | Prevención (gran escala) | Cygnus |
| PSI-99 | Saffire-II | Prevención (µg vs 1g) | Cygnus |
| PSI-100 | Saffire-III | Prevención (gran escala) | Cygnus |
| PSI-102 | SAME | Detección (humo) | Glovebox |
| PSI-101 | SAME-R | Detección (humo) | Glovebox |
| PSI-47 | DAFT / DAFT-2 | Detección (polvo, mismo instrumento) | — |
| PSI-69 | FLEX | Supresión (gotas, CO₂/He) | CIR, MDCA |
| PSI-68 | FLEX-2 | Supresión (gotas) | CIR, MDCA |
| PSI-39 | CFI | Llamas frías | CIR, MDCA |
| PSI-20 | ACME BRE | Prevención (emula sólidos con gas) | CIR, ACME |
| PSI-21 | ACME CLD Flame | Contexto (flamas de gas) | CIR, ACME |
| PSI-22 | ACME E-FIELD | Imita gravedad parcial | CIR, ACME |
| PSI-23 | ACME s-Flame | Contexto | CIR, ACME |
| PSI-10 | ACME Flame Design | Contexto (hollín) | CIR, ACME |
| PSI-159 | ACME CFI-G | Oxígeno alto (hasta 85 %) | CIR, ACME |
| PSI-106 | SLICE | Contexto (flamas de gas) | MSG, ducto SPICE |
| PSI-107 | SPICE | Contexto (hollín, humo) | MSG, ducto SPICE |

**Estudios en tierra con datos de vuelo (5)** — son modelos/simulaciones, no mediciones nuevas

| ID | Usa datos de | Tema |
|---|---|---|
| PSI-117 | FLEX | Llamas frías, CFD |
| PSI-142 | FLEX | Extinción de llamas frías |
| PSI-62 | BASS | Propagación de flama, modelado |
| PSI-60 | SPICE | Hollín |
| PSI-115 | SAME | Simulación de humo |

## Documentación complementaria (pestaña Resources del reto)

- NASA Combustion Science: https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/
- A Researcher's Guide to ISS Combustion Science: https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/
- ScienceCasts (video): https://www.youtube.com/watch?v=W1oXykoz9zg
- Apollo 1: https://sma.nasa.gov/sma-disciplines/accllp/apollo-1
- Apollo 13: https://sma.nasa.gov/sma-disciplines/accllp/apollo-13
- Incendio en la Mir: https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/
- Spinoff – tanques de aire: https://spinoff.nasa.gov/node/9582
- Spinoff – detector de humo: https://spinoff.nasa.gov/node/9407
- Spinoff – ropa de bomberos: https://spinoff.nasa.gov/node/9918

## Otras fuentes posibles

- NASA-STD-6001 (prueba de inflamabilidad de materiales en la Tierra)
- NTRS, API de reportes técnicos: https://ntrs.nasa.gov/api/openapi/
- NASA Image and Video Library: https://images-api.nasa.gov/search?q=microgravity%20flame
