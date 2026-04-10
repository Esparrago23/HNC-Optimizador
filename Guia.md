# HNC-Optimizador — Guía del Proyecto

Sistema de optimización del programa **Hoy No Circula (HNC)** de CDMX usando un Algoritmo Genético. Calcula el esquema de restricción vehicular óptimo minimizando emisiones de CO₂ y costo económico.

---

## Cómo encender el proyecto

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

> Requiere **Python 3.10 o superior**.

### 2. Iniciar el servidor

```bash
cd backend
python hnc_server.py
```

El servidor queda corriendo en: **http://127.0.0.1:8000**

### 3. Abrir la interfaz

Abre tu navegador y entra a:

```
http://127.0.0.1:8000
```

Listo. La UI carga automáticamente y detecta si el backend está activo.

---

## Estructura de carpetas

```
Datasets/
│
├── 1.Factores de Emisión/
│   ├── verificacion_automotriz.csv     # Datos de verificación vehicular (SEMOVI)
│   └── ias_calidad_aire.csv            # Datos de calidad del aire IAS-SIMAT CDMX
│
├── 2.Composición del Parque Vehicular/
│   └── vmrc_parque_vehicular.csv       # Registro vehicular por tipo y combustible
│
├── 3.Curvas de Demanda y Tráfico/
│   ├── contaminantes.csv               # Series históricas de contaminantes
│   ├── eod_entre_semana.xlsx           # Encuesta Origen-Destino entre semana
│   ├── eod_entre_semana.csv            # Versión CSV del EOD entre semana
│   └── eod_sabado.xlsx                 # Encuesta Origen-Destino sábado
│
├── backend/                            # Lógica del servidor y el AG
│   ├── hnc_server.py                   # Servidor Flask — API REST y rutas
│   ├── ag_evolutivo_hnc2.py            # Algoritmo Genético principal
│   └── etl_datos.py                    # Pipeline ETL — carga y valida archivos
│
├── frontend/                           # Interfaz web
│   ├── hnc_ui.html                     # Página principal de la app
│   ├── hnc_ui.js                       # Lógica de la UI (gráficas, resultados, ETL)
│   └── hnc_ui.css                      # Estilos visuales
│
├── data/                               # Datos de entorno y resultados
│   ├── entorno_cdmx.json               # Parámetros del entorno CDMX (flota, IMECA, etc.)
│   └── resultado_ag_hnc.json           # Último resultado guardado del AG
│
├── graficas/                           # Exportaciones de gráficas generadas
│
├── requirements.txt                    # Dependencias Python (este archivo)
└── LEEME.md                            # Esta guía
```

---

## Descripción de archivos clave

### `backend/hnc_server.py`
El servidor web. Expone todos los endpoints de la API:

| Endpoint | Método | Qué hace |
|---|---|---|
| `/` | GET | Sirve la interfaz web |
| `/api/config-inicial` | GET | Devuelve parámetros por defecto del AG |
| `/api/archivos` | GET | Muestra qué archivos de datos están cargados |
| `/api/validar-archivo` | POST | Valida un CSV/XLSX sin guardarlo |
| `/api/subir-archivo` | POST | Valida y guarda un archivo con nombre canónico |
| `/api/etl-ias` | POST | Procesa el CSV de calidad del aire y actualiza el entorno |
| `/api/run` | POST | Ejecuta el Algoritmo Genético y devuelve resultados |
| `/api/ultimo-resultado` | GET | Devuelve el último resultado del AG guardado |

### `backend/ag_evolutivo_hnc2.py`
El cerebro del proyecto. Implementa el Algoritmo Genético con:
- **Cromosoma de 11 genes**: días H0, H1 y H2, fases de hologramas, y asignación de color→día
- **Modelo BPR de velocidad vehicular** para estimar flujo de tráfico
- **Función `imeca_mensual()`**: usa datos IMECA reales de IAS_2024 cuando están disponibles
- **Penalizaciones blandas** (AG libre): permite soluciones fuera de reglas HNC pero las penaliza
- **Métricas de costo-beneficio**: CO₂ evitado, autos restringidos/día, costo económico en MXN

### `backend/etl_datos.py`
Pipeline de datos. Gestiona todos los archivos de entrada:
- **Valida** cada tipo de archivo antes de aceptarlo (columnas, estructura de cabecera)
- **Renombra** los archivos subidos al nombre canónico (sin importar el año del nombre original)
- **Hace backup** del archivo anterior antes de sobreescribir
- **Procesa el CSV IAS-SIMAT** y extrae promedios IMECA por mes para actualizar `entorno_cdmx.json`
- **Rutas canónicas fijas**: los archivos siempre se guardan en las mismas rutas, independientemente del año o nombre del archivo subido

### `data/entorno_cdmx.json`
El archivo de configuración del entorno CDMX. Contiene:
- Tamaño de la flota vehicular por holograma (H0, H1, H2, H00)
- Parámetros base de contaminación (IMECA) por mes
- **`imeca_promedio_real`**: datos IMECA reales extraídos del CSV IAS-SIMAT 2024
- Factores de demanda por día de la semana
- Parámetros del modelo de tráfico (BPR)

### `frontend/hnc_ui.js`
Toda la lógica de la interfaz. Incluye:
- **Panel ETL dinámico**: sube y valida cada archivo de datos individualmente con feedback visual
- **Panel IAS**: importa el CSV de calidad del aire y muestra una tabla con IMECA por mes
- **Calendarios interactivos**: visualiza el esquema de restricción día por día
- **Analytics en 5 pestañas**: evolución de aptitud, variables del AG, esquema óptimo, costo-beneficio CO₂, y detalle del mejor individuo
- **Descarga de gráficas** en PNG

---

## Cómo subir los datos de entrada

Desde la UI, sección **"Datos de Entrada"** (pestaña Avanzado):

1. Cada archivo tiene un botón **"Subir"**
2. Al seleccionar tu archivo (sin importar el nombre o año), el sistema lo valida y lo guarda con el nombre canónico correcto
3. Si el archivo tiene estructura incorrecta, se muestra el error específico
4. Para el archivo IAS de calidad del aire: después de subirlo, se procesa automáticamente y actualiza los datos IMECA reales en el entorno

---

## Flujo típico de uso

```
1. Instalar dependencias    →  pip install -r requirements.txt
2. Iniciar servidor         →  cd backend && python hnc_server.py
3. Abrir UI                 →  http://127.0.0.1:8000
4. Subir archivos de datos  →  Panel "Datos de Entrada" (opcional)
5. Configurar parámetros    →  Pestaña "Avanzado"
6. Ejecutar optimización    →  Botón "Optimizar"
7. Ver resultados           →  Calendario + gráficas de análisis
8. Exportar                 →  Botón "Exportar JSON" o descargar PNGs
```
