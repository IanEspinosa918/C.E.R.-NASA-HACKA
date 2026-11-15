# Frontend

`index.html` es el tablero (prototipo del equipo, antes `artemis_psi_fire_safety_mission_control.html`
en la raíz) conectado al backend. **De aquí en adelante se edita este archivo.**

Se abre a través del backend, que lo sirve:

```
python backend\app.py
```
y luego <http://127.0.0.1:8000>.

## Cómo está organizada (pestañas)
La página tiene 4 pestañas arriba; se ve una sola a la vez:

| # | Pestaña | Qué contiene |
|---|---------|--------------|
| 1 | Simulación | Izquierda: visor 3D de la Luna, los 4 hábitats y, debajo, la llama animada. Derecha: los deslizadores (gravedad, O₂, presión, flujo, combustible) y la Tarjeta A (índice de riesgo y avisos) |
| 2 | Detección y supresión | Tarjeta C (detección de humo) y Tarjeta D (extinción y spin-off) |
| 3 | Experimentos PSI | Tarjeta B (Top 3 experimentos) y la gráfica de la prueba ACME 17319A3 |
| 4 | Co-Piloto IA | Chat con los documentos de NASA PSI |

En pantallas anchas, la columna de los deslizadores se queda fija al bajar (si cabe completa en
la pantalla), para poder moverlos mientras se ve la llama.

## Visor 3D: Luna, Marte y Tierra (Three.js)
El cuerpo que se ve depende de la **gravedad** elegida (botones o deslizador "Gravedad libre"):

| Gravedad | Se ve | Detalle |
|----------|-------|---------|
| 0 g | **Tierra con la Estación Espacial Internacional** | Donde se hicieron los experimentos de PSI. La EEI está en su **posición real en vivo** (SGP4 con su TLE de CelesTrak vía `/api/iss`); la vista la sigue hasta que arrastras. HUD: latitud, longitud, altura y si está iluminada o en la sombra de la Tierra |
| 0 g con el hábitat **Gateway** | Luna con la órbita NRHO | Órbita esquemática, no a escala; la Luna como se ve desde la Tierra (fase real) |
| ≈ 1/6 g (0.08–0.27) | **Luna** | Mapa LRO + relieve LOLA, sitios del Polo Sur en coordenadas reales, elevación del Sol en el sitio |
| ≈ 3/8 g (0.27–0.69) | **Marte** | Mosaico de color Viking (NASA/USGS), bruma de la atmósfera; sitio de ejemplo: cráter Jezero (rover Perseverance) con la elevación real del Sol allí. Si en Jezero es de noche, la cámara enfoca el lado iluminado |
| ≈ 1 g | **Tierra** (referencia) | La misma Tierra con la EEI |

- **Luz solar de este momento en los tres cuerpos**: `vendor/astronomy.browser.min.js`
  (astronomy-engine, MIT) calcula el punto donde el Sol está en el cenit (modelo de rotación IAU
  para la Luna y Marte; tiempo sidéreo para la Tierra) y se actualiza cada minuto.
- **Tierra**: día (Blue Marble), noche con luces de ciudades (Black Marble 2016), brillo del Sol
  en el mar, franja del atardecer, nubes (composición histórica, no el clima de hoy) y halo azul
  de la atmósfera.
- **Luna**: sombreado del regolito (la luna llena se ve "plana") y luz cenicienta en el lado
  nocturno. **Marte**: atmósfera delgada color durazno en el borde.
- Mapas en `frontend/texturas/` (funcionan sin internet; créditos en `texturas/CREDITOS.md`).
  Si abres `index.html` como archivo sin el backend, los cuerpos se ven simplificados y la EEI
  usa una órbita esquemática (el HUD lo dice).
- Los tres cuerpos se dibujan del mismo tamaño (no a escala entre sí).

## Idioma (español / inglés)
Botones **ES / EN** en el encabezado (🌐). La elección se guarda en el navegador.
- **Textos fijos del HTML**: diccionario `TEXTOS_EN` (texto en español tal cual aparece → inglés) y
  `ATRIBUTOS_EN` (placeholders, títulos). Si agregas un texto fijo nuevo, agrega su par ahí; si no,
  se queda en español.
- **Textos que genera el código**: `tr("español", "english")` en el mismo lugar del código.
- **Datos del tablero** (hábitats, hallazgos de los experimentos, bitácora ACME): `DATOS_EN`.
- **La IA** responde en el idioma de la pregunta: si escribes en inglés (o pides "in English")
  responde en inglés aunque la página esté en español, y al revés. El botón "Interpretar este
  escenario" arma la pregunta en el idioma de la página.

## Rendimiento (para que los controles nunca se congelen)
El planeta y la llama se dibujan con la tarjeta de video. Si ella se satura, Chrome detiene la
página y los deslizadores dejan de responder. Para evitarlo:
- el planeta se dibuja a máximo 30 cuadros/s, y a ~12 mientras arrastras cualquier deslizador
  (la llama sigue fluida);
- el planeta y la llama se pausan cuando no están en pantalla;
- **calidad automática**: si la página va a menos de ~30 cuadros/s, baja la resolución de los
  dibujos 3D; si sobra margen, la vuelve a subir (`rendimiento.calidad`: 2 alta, 1 media, 0 baja);
- se pide la tarjeta de video dedicada en laptops que tienen dos;
- los deslizadores muestran su número al instante y el recálculo se hace una vez por cuadro.

## Gravedad libre (experimentación)
Bajo los botones de gravedad hay un deslizador de **0 a 1 g**. Se "pega" a Órbita (0), Luna
(1/6), Marte (3/8) y Tierra (1) al pasar cerca. Con cualquier otro valor:
- el índice de riesgo interpola el factor de gravedad entre los regímenes;
- la llama cambia de forma y de parpadeo de forma continua (flotabilidad ∝ √g);
- la Tarjeta A muestra el aviso **"Gravedad experimental"**: PSI no tiene ensayos en gravedad
  parcial, así que es una exploración, no un resultado medido;
- el chat recibe la gravedad exacta ("gravedad personalizada de 0.25 g").

## La llama (WebGL)
Se dibuja con un shader (código `LLAMA_FRAGMENTOS` en `index.html`) que reacciona en vivo a:
- **Gravedad:** la flotabilidad la estira hacia arriba y la hace parpadear; el parpadeo es más
  lento con menos gravedad (crece con √g) y no existe en órbita.
- **Flujo de aire:** la inclina y alarga aguas abajo (hacia la derecha); las líneas de flujo se
  mueven a esa velocidad.
- **O₂:** más grande y brillante; con mucho O₂ el hollín incandescente se ve casi blanco.
  Con poco O₂ es pequeña y débil.
- **Presión:** con menos presión, un poco más grande y con menos hollín.
- **Combustible:** muestra sólida que se va carbonizando (tipo BASS-II/Saffire), gota en una
  fibra (tipo FLEX) o quemador de gas (tipo ACME).
- Sin flotabilidad ni ventilación (0g, 0 cm/s) la llama queda esférica, tenue y azul.

Es una **ilustración cualitativa**, no un modelo de combustión ni imágenes de PSI (así lo dice
la página). Si el navegador no tiene WebGL, se usa la llama 2D anterior.

- Bajo las pestañas hay una barra con el **escenario actual** (hábitat, gravedad, O₂, presión,
  flujo, combustible), visible en todas. Dice "· modificado" si moviste algún deslizador.
  El botón **✨ Interpretar con IA** de esa barra abre la pestaña 4 (Co-Piloto IA) y pide el dictamen.
- La pestaña activa queda en la dirección: `http://127.0.0.1:8000/#ia` abre directo
  esa pestaña (sirve para la presentación). Nombres: `#simulacion`, `#seguridad`,
  `#experimentos`, `#ia` (el viejo `#escenario` lleva a `#simulacion`).
- Con el teclado: flechas ← → (o Inicio/Fin) sobre las pestañas.
- Cada pestaña termina con un botón "Siguiente" para recorrerlas en orden durante la demo.
- **Para agregar una sección nueva:** ponla dentro del `<section id="tab-...">` que le
  corresponda. Si necesitas otra pestaña: agrega su botón en `#pestanas`, su `<section>` y
  su nombre en la lista `PESTANAS` del JavaScript.
- El visor 3D y la llama no se dibujan mientras su pestaña está oculta (ahorra GPU) y se
  ajustan de tamaño al mostrarse.

## Qué está conectado
- **Co-piloto de IA:**
  - El botón "Interpretar este escenario con IA" manda el escenario (gravedad, O₂, presión,
    flujo, combustible y Top 3) a `/api/chat`.
  - La caja "Preguntar" manda preguntas libres.
  - Las respuestas salen de los documentos de NASA PSI, con citas `[n]` y la lista de
    fuentes con enlace al DOI.
- Indicador de conexión: dice si el backend y la IA (Groq o Gemini) están listos.
- **Opciones de búsqueda y modelo** (panel plegable ⚙ bajo la caja de preguntas). Se guardan
  en el navegador:
  - filtrar por experimento o por pilar;
  - "Responder por pilares" también en preguntas libres;
  - número de fragmentos (4 a 10);
  - modelo que redacta (los que tengan clave en `.env`).
- Botón **Copiar** en cada respuesta: copia el texto con sus fuentes y enlaces DOI.

## Qué sigue siendo simulado (hay que cambiarlo antes de presentar)
- Los datos de los experimentos están escritos dentro del HTML (`PSI_MASTER_DATA`). Se pueden
  cargar de `/api/experimentos` y `/api/pruebas`.
- El "índice de riesgo" y la similitud del Top 3 son fórmulas propias, no de la NASA. Hay que
  decirlo en la página.
- La "telemetría" es generada, no son datos reales.
- Usa Tailwind, Three.js y fuentes desde internet (CDN): sin internet la página se ve mal.
