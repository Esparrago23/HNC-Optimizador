"""
Días extra:

❌ NO para H1
✅ SOLO para H2
✅ Son fechas específicas (no recurrentes)
✅ Cantidad: 0 a 3 días por color
🧬 1. REPRESENTACIÓN DEL INDIVIDUO
{
  "meses": [ {mes1}, {mes2}, {mes3}, {mes4}, {mes5}, {mes6} ]
}
🧩 2. ESTRUCTURA FINAL DE CADA MES
{
  "mes": 1,
  "year": 2026,
  "contaminacion": "baja | normal | alta",

  "h00": "libre",
  "h0": "libre",

  "h1": {
    "por_color": {
      "amarillo": {
        "dia_base": "jueves",
        "sabados": [1, 2],
        "horario": [5,22],
        "zona": "total"
      }
    }
  },

  "h2": {
    "por_color": {
      "amarillo": {
        "dia_base": "jueves",
        "sabados": [1,2,3,4],
        "extras": ["2026-01-13", "2026-01-27"],
        "horario": [5,22],
        "zona": "total"
      }
    }
  }
}
🧠 🔑 REGLAS DEFINITIVAS
🔹 Holograma 00 y 0
Siempre libres
🔹 Holograma 1 (H1)
1 día base semanal (por color)
Sábados:
baja → 1–2
normal → 2
alta → 2–3
❌ SIN días extra
Horario:
normal → (5,22)
baja → puede reducir a (5,16)
Zona:
puede ser "centro" ocasionalmente
🔹 Holograma 2 (H2)
1 día base semanal (por color)
Sábados:
baja → 3
normal → 4
alta:
si hay 5 sábados → 5
si no → 4
🔥 DÍAS EXTRA (SOLO H2)
Cantidad: 0 a 3
Tipo: fechas específicas del mes
Ejemplo:
"extras": ["2026-01-13", "2026-01-27"]
📌 Cómo se usan

Para un color:

Restricción total del mes =
- todos los "dia_base"
- sábados seleccionados
- días "extras"
🎯 3. DECISIONES DEL AG

Para cada:

👉 mes
👉 holograma (H1, H2)
👉 color

El AG decide:

H1
dia_base
sabados
horario
zona
H2
dia_base
sabados
extras (0–3 fechas)
horario
zona
🧪 4. FITNESS

El AG evalúa cada individuo:

Paso 1: Expandir calendario real

Convierte:

dia_base → todas las fechas reales
sabados → fechas reales del mes
extras → ya están listas
Paso 2: Simular
autos restringidos por día
emisiones
tráfico
impacto económico
Paso 3: función objetivo
fitness = (
    w1 * emisiones +
    w2 * congestion +
    w3 * impacto_economico +
    w4 * penalizacion_cambios_bruscos
)
🔁 5. MUTACIÓN (FINAL)

Ahora sí bien definido:

cambiar dia_base
cambiar número o índice de sábados
🔥 agregar/eliminar día en extras (solo H2)
cambiar horario
cambiar zona
🔀 6. CRUCE
intercambiar meses completos
o colores dentro del mismo mes
📊 7. SALIDA FINAL (LO QUE QUIERES)
{
  "mejor_fitness": 0.17,

  "mejor_individuo": { ... },

  "historial_fitness": [1.2, 0.9, 0.6, 0.3, 0.17],

  "calendario_6_meses": [
    {
      "mes": 1,
      "h1": {...},
      "h2": {...}
    }
  ]
}
"""