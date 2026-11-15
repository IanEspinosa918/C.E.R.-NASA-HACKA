# Mapas de los cuerpos del visor 3D

Todos son mapas globales en proyección equirectangular (longitud -180° a 180°, centrados en 0°,
norte arriba). Los JPG se generaron a partir de los originales: solo cambio de formato y tamaño,
sin cambiar colores.

## Luna (régimen 1/6 g)
| Archivo | Qué es | Tamaño |
|---------|--------|--------|
| `luna_color_4k.jpg` | Mosaico de color LROC WAC del Lunar Reconnaissance Orbiter, con relleno polar | 4096×2048 |
| `luna_color_2k.jpg` | El mismo, reducido | 2048×1024 |
| `luna_relieve_1k.jpg` | Elevación del altímetro LOLA (8 bits), para el relieve en el terminador | 1024×512 |

Fuente: NASA's Scientific Visualization Studio, *CGI Moon Kit* (`lroc_color_poles_4k`, `ldem_3_8bit`).
Dominio público; crédito: "NASA's Scientific Visualization Studio".

## Marte (régimen 3/8 g)
| Archivo | Qué es | Tamaño |
|---------|--------|--------|
| `marte_color_2k.jpg` | *Mars Viking Global Color Mosaic* (USGS Astrogeology), armado con ~1,000 imágenes de los orbitadores Viking | 2048×1024 |

Fuente: USGS Astrogeology Science Center / NASA / JPL. Dominio público ("use constraints: none").

## Tierra (régimen 0 g en órbita y referencia de 1 g)
| Archivo | Qué es | Tamaño |
|---------|--------|--------|
| `tierra_dia_4k.jpg`, `tierra_dia_2k.jpg` | *Blue Marble: Next Generation* con topografía y batimetría, diciembre de 2004 (`world.topo.bathy.200412.3x5400x2700.jpg`) | 4096×2048 / 2048×1024 |
| `tierra_noche_2k.jpg` | *Black Marble* 2016 (luces nocturnas, VIIRS) | 2048×1024 |
| `tierra_nubes_2k.jpg` | *Blue Marble: Clouds* (`cloud_combined_2048.jpg`), sin modificar (SHA-256 `daddaad84d7a33bbbc86cdda3f591099f57cee8607b7bcf3b67eb7e4f7a1c793`) | 2048×1024 |

Fuente: NASA Earth Observatory (Reto Stöckli; Black Marble: NASA/NOAA). Imágenes de NASA,
dominio público en EE. UU.; se da crédito a NASA sin implicar respaldo. Las nubes son una
composición histórica: **no** son el clima de hoy.

# Librerías de cálculo (carpeta `../vendor/`)
- `astronomy.browser.min.js`: **astronomy-engine** 2.1.19, Don Cross (MIT). Posición del Sol para
  la iluminación de la Luna, Marte y la Tierra.
- `satellite.min.js`: **satellite.js** 5.0.0 (MIT). Propaga la órbita de la Estación Espacial
  Internacional (modelo SGP4) a partir de sus elementos orbitales (TLE), que el backend baja de
  CelesTrak en `/api/iss`.
