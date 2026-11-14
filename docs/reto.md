# El reto: Flame in Freefall

Fuente: https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=details

## En una línea

Construir un **dashboard web con IA** que **resuma, ordene e interprete** los experimentos de
combustión en microgravedad de la NASA (repositorio PSI) para dar información de
**seguridad contra incendios** en la exploración humana.

## Puntos clave

- **Problema:** hay demasiados datos; son difíciles de encontrar, comparar e interpretar.
- **Fuego en microgravedad:** sin flotación el aire caliente no sube; la flama se vuelve
  una esfera azul y depende de la difusión para recibir oxígeno.
- **Tres pilares de la NASA:** prevención (materiales, límites de inflamabilidad),
  detección (humo: SAME, SAME-R), supresión (FLEX: dilución con CO₂ y helio).
- **Base lunar:** se espera ≥ 30 % de oxígeno a ≤ 10.2 psi (Tierra: 21 % a 14.7 psi).
  Es más de 40 % más oxígeno → materiales mucho más inflamables.
- **Traje espacial:** 100 % oxígeno a 4.3 psi.
- **Sin datos de gravedad parcial** en PSI (Luna, Marte). Llegarán con LUCI y FM2.
  Microgravedad y gravedad normal sirven como límites. E-FIELD imita gravedad parcial
  con campos eléctricos.
- **Fuera de alcance:** cohetes y propelentes.
- **Público:** profesores, estudiantes, investigadores e ingenieros aeroespaciales.

## Checklist

### Obligatorio
- [ ] Herramienta web
- [ ] Usa datos de PSI (combustión)
- [ ] IA que resume, ordena e interpreta
- [ ] Enfoque en seguridad contra incendios para exploración humana

### Objetivos sugeridos por el reto
- [ ] Encontrar experimentos relevantes por hábitat (nave, estación, base lunar/marciana, rover)
- [ ] Extraer datos para modelado predictivo (exportar CSV)
- [ ] Destacar investigación útil para nuevos equipos de seguridad

### Consideraciones (dan puntos)
- [ ] Mostrar objetivos, combustible (forma y tamaño), condiciones (oxígeno, flujo), variables, sensores
- [ ] Similitudes y diferencias entre experimentos (comparador)
- [ ] Agrupar por familia de equipo (ACME/CIR, MDCA/CIR, ducto del MSG)
- [ ] Incluir DAFT, BRE y otros experimentos relacionados
- [ ] Avisar que no hay datos de gravedad parcial
- [ ] Aplicaciones en la Tierra (opcional)
- [ ] Citar DOI de cada experimento
