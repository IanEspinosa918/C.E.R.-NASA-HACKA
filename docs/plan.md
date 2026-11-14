# Plan de trabajo

Regla de oro: **la Fase 3 funcionando de punta a punta antes de empezar los simuladores.**

## Roles
| Rol | Responsable |
|---|---|
| Datos | |
| Backend + IA | |
| Frontend | |
| Simuladores + presentación | |

## Fase 0 — Preparación
- [ ] Leer el reto, ver el video de ScienceCasts, hojear la Researcher's Guide
- [ ] Asignar roles
- [ ] Cuentas y claves: modelo de IA, Supabase/Neon (Postgres + pgvector)
- [ ] Revisar requisitos de entrega de Space Apps

## Fase 1 — Datos
- [ ] Descargar con `scripts/descargar_psi.py`
- [ ] Revisar cada CSV: columnas, unidades, faltantes (ver `trampas-datos.md`)
- [ ] Formato común: tablas `experimentos` y `pruebas`
- [ ] Convertir unidades (ej. ventilador de BASS-II → cm/s)
- [ ] Validación: rangos, unidades, valores raros
- [ ] Cargar en Postgres; guardar DOI
- [ ] Texto para la IA → embeddings en pgvector
- [ ] Buscar curvas de inflamabilidad en documentos de BASS/BASS-II

## Fase 2 — Backend + IA
- [ ] FastAPI: `/experimentos`, `/experimentos/{id}`, `/pruebas`, `/export.csv`, `/chat`
- [ ] Resúmenes por experimento generados de antemano
- [ ] Chat RAG que cita experimento + DOI y dice "no hay datos"
- [ ] Ordenamiento por hábitat

## Fase 3 — Dashboard (nivel 1)
- [ ] Tarjetas por experimento, filtros por pilar y equipo
- [ ] Filtro "¿Dónde vas a estar?"
- [ ] Gráficas con datos reales
- [ ] Exportar CSV
- [ ] Panel de chat
- [ ] **Revisión: funciona de punta a punta**

## Fase 4 — Simuladores (en este orden)
- [ ] Supresión (FLEX): CO₂/helio, extinción vs disrupción, llamas frías
- [ ] Comparador de entornos: Tierra, ISS, base lunar, Marte/traje + Saffire-II µg vs 1g
- [ ] Inflamabilidad: mapa oxígeno vs flujo, puntos reales, zona "sin datos"
- [ ] Detección (SAME/SAME-R): tipo de humo por material, detector en ventilación

## Fase 5 — IA ↔ simuladores
- [ ] Function calling: `set_simulador(...)`
- [ ] Estado del simulador → contexto del chat

## Fase 6 — Pulido
- [ ] Avisos: gravedad parcial, extrapolación, simulación cualitativa
- [ ] Comparador lado a lado de experimentos
- [ ] DOI visibles en todo el sitio
- [ ] Responsive y sin errores de consola

## Fase 7 — Entrega
- [ ] Deploy (Vercel + Render/Railway) y prueba desde otra red
- [ ] README con arquitectura, fuentes y limitaciones
- [ ] Presentación: accidente real → problema → demo → base lunar 30 %
- [ ] Video de la demo grabado con anticipación
- [ ] Enviar antes de la hora límite

## Ideas para después
- Modo "Reconstruir el accidente" (Apollo 1, Mir)
- Verificador de materiales
- Sección "En la Tierra" con fichas de Spinoff
- Ampliar el chat con NTRS
- Imágenes y videos de la NASA Image Library en los simuladores
- Modo estudiante / investigador
- Exportar citas en BibTeX
- Propagación en el hábitat (solo como escenario ilustrativo)
- Preparar la estructura para datos de gravedad parcial (LUCI, FM2)
