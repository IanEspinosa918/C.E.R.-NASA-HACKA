# Frontend

`index.html` es el tablero (prototipo del equipo, antes `artemis_psi_fire_safety_mission_control.html`
en la raíz) conectado al backend. **De aquí en adelante se edita este archivo.**

Se abre a través del backend, que lo sirve:

```
python backend\app.py
```
y luego <http://127.0.0.1:8000>.

## Qué está conectado
- **Co-piloto de IA:**
  - El botón "Interpretar este escenario con IA" manda el escenario (gravedad, O₂, presión,
    flujo, combustible y Top 3) a `/api/chat`.
  - La caja "Preguntar" manda preguntas libres.
  - Las respuestas salen de los documentos de NASA PSI, con citas `[n]` y la lista de
    fuentes con enlace al DOI.
- Indicador de conexión: dice si el backend y Gemini están listos.

## Qué sigue siendo simulado (hay que cambiarlo antes de presentar)
- Los datos de los experimentos están escritos dentro del HTML (`PSI_MASTER_DATA`). Se pueden
  cargar de `/api/experimentos` y `/api/pruebas`.
- El "índice de riesgo" y la similitud del Top 3 son fórmulas propias, no de la NASA. Hay que
  decirlo en la página.
- La "telemetría" es generada, no son datos reales.
- Usa Tailwind, Three.js y fuentes desde internet (CDN): sin internet la página se ve mal.
