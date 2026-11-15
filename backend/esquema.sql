-- Esquema de la base de datos (Postgres + pgvector).
-- Lo aplican scripts/cargar_bd.py y scripts/cargar_fragmentos.py; no hace falta correrlo a mano.
-- Las líneas "-- == seccion: X ==" separan lo que crea cada script.
--
-- Seguridad: las tres tablas tienen RLS activado con una política de SOLO LECTURA.
-- En Supabase eso evita que alguien con la clave pública (anon) modifique o borre datos.
-- El backend y estos scripts se conectan como dueños de las tablas, así que sí pueden escribir.

-- == seccion: experimentos ==
CREATE TABLE IF NOT EXISTS experimentos (
    id                text PRIMARY KEY,        -- PSI-69
    acronimo          text NOT NULL,           -- FLEX
    titulo            text,
    tipo              text,                    -- vuelo | tierra (los de tierra son modelos, no mediciones nuevas)
    pilar             text,                    -- prevencion | deteccion | supresion | contexto
    tipo_combustible  text,                    -- solido | gota | gas | humo | polvo
    familia_equipo    text,                    -- experimentos que comparten equipo
    resumen_es        text,                    -- una línea en español (escrita por el equipo)
    hardware          text,                    -- equipo según PSI
    plataforma        text,
    centro_nasa       text,
    tipo_proyecto     text,
    fecha_inicio      date,
    fecha_fin         date,
    doi               text,                    -- para citar (obligatorio según PSI)
    version           integer,
    area              text,
    subarea           text,
    objetivo          text,
    enfoque           text,
    hipotesis         text,
    impacto           text,
    relacionados      text[],                  -- otros experimentos relacionados según PSI
    publicaciones     jsonb,                   -- [{titulo, autores, doi}]
    url               text,
    licencia          text
);
ALTER TABLE experimentos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lectura_publica ON experimentos;
CREATE POLICY lectura_publica ON experimentos FOR SELECT USING (true);

-- == seccion: pruebas ==
-- Mismas columnas que data/processed/pruebas.csv (ver docs/formato-datos.md).
CREATE TABLE IF NOT EXISTS pruebas (
    id                          bigserial PRIMARY KEY,
    experimento_id              text NOT NULL REFERENCES experimentos(id),
    experimento                 text NOT NULL,
    prueba_id                   text NOT NULL,
    fecha                       date,
    gravedad                    text,
    tipo_combustible            text,
    combustible                 text,
    descripcion_muestra         text,
    geometria                   text,
    espesor_mm                  double precision,
    ancho_mm                    double precision,
    largo_mm                    double precision,
    presion_atm                 double precision,
    o2                          double precision,
    n2                          double precision,
    co2                         double precision,
    he                          double precision,
    flujo_aire_cm_s             double precision,
    flujo_aire_min_cm_s         double precision,
    flujo_aire_max_cm_s         double precision,
    diametro_inicial_mm         double precision,
    diametro_extincion_mm       double precision,
    k_quemado_mm2_s             double precision,
    k_quemado_fria_mm2_s        double precision,
    diametro_extincion_fria_mm  double precision,
    tiempo_quemado_s            double precision,
    longitud_quemada_mm         double precision,
    velocidad_propagacion_mm_s  double precision,
    calentamiento_rt_r0         double precision,
    tiempo_calentamiento_s      double precision,
    tiempo_envejecimiento_s     double precision,
    perdida_masa_mg_min         double precision,
    resultado                   text,
    resultado_original          text,
    aproximado                  boolean,
    banderas                    text,
    notas                       text,
    doi                         text,
    archivo_origen              text,
    fila_origen                 integer
);
CREATE INDEX IF NOT EXISTS pruebas_experimento_idx ON pruebas (experimento_id);
CREATE INDEX IF NOT EXISTS pruebas_combustible_idx ON pruebas (tipo_combustible, combustible);
CREATE INDEX IF NOT EXISTS pruebas_resultado_idx ON pruebas (resultado);
ALTER TABLE pruebas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lectura_publica ON pruebas;
CREATE POLICY lectura_publica ON pruebas FOR SELECT USING (true);

CREATE OR REPLACE VIEW experimentos_resumen WITH (security_invoker = true) AS
SELECT e.id, e.acronimo, e.titulo, e.tipo, e.pilar, e.tipo_combustible, e.familia_equipo,
       e.resumen_es, e.doi, e.url,
       count(p.id)                                   AS num_pruebas,
       count(p.id) FILTER (WHERE p.resultado <> '')  AS num_pruebas_con_resultado,
       min(p.o2) AS o2_min, max(p.o2) AS o2_max,
       min(p.presion_atm) AS presion_min_atm, max(p.presion_atm) AS presion_max_atm
FROM experimentos e LEFT JOIN pruebas p ON p.experimento_id = e.id
GROUP BY e.id;

-- == seccion: fragmentos ==
-- Pedazos de texto de las fichas y documentos, con su vector (para el chat con RAG).
-- vector(384) corresponde al modelo por defecto; scripts/cargar_fragmentos.py lo ajusta
-- si se usa otro modelo.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS fragmentos (
    id                bigserial PRIMARY KEY,
    experimento_id    text NOT NULL REFERENCES experimentos(id),
    experimento       text NOT NULL,
    pilar             text,
    doi               text,                    -- para citar
    tipo_documento    text,                    -- ficha | reporte | documento_cientifico | presentacion | ingenieria
    titulo_documento  text,
    archivo           text NOT NULL,           -- ruta dentro de data/raw/
    pagina            integer,                 -- página (PDF) o diapositiva (pptx); NULL en fichas y docx
    orden             integer NOT NULL,        -- posición del fragmento dentro del documento
    texto             text NOT NULL,
    tambien_en        text[],                  -- otros experimentos que traen el mismo documento
    fuente_general    text,                    -- etiqueta si es una guía/hoja general (ver scripts/fuentes_generales.py)
    modelo_embedding  text NOT NULL,
    embedding         vector(384) NOT NULL,
    UNIQUE (archivo, orden)
);
CREATE INDEX IF NOT EXISTS fragmentos_experimento_idx ON fragmentos (experimento_id);
CREATE INDEX IF NOT EXISTS fragmentos_embedding_idx ON fragmentos USING hnsw (embedding vector_cosine_ops);
ALTER TABLE fragmentos ADD COLUMN IF NOT EXISTS fuente_general text;  -- para bases creadas antes
-- Búsqueda por palabras clave (parte "híbrida" del RAG). scripts/buscar.py también lo crea si falta.
CREATE INDEX IF NOT EXISTS fragmentos_texto_idx ON fragmentos USING gin (to_tsvector('english', texto));
ALTER TABLE fragmentos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lectura_publica ON fragmentos;
CREATE POLICY lectura_publica ON fragmentos FOR SELECT USING (true);
