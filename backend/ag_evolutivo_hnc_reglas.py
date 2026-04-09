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
 1. Reglas Inmutables (La Ley Base)

Estas reglas no las puede romper el algoritmo. Son la base legal para que el programa sea reconocible por los ciudadanos.





Día Base Obligatorio: Los Hologramas 1 y 2 tienen que descansar un día a la semana obligatoriamente, determinado por el color de su engomado y su último dígito de placa los cuales son emparejados por el AG el decide que dia va con que color y no pueden repetirse:





Lunes: Verde (1 y 2)



Martes: Amarillo (5 y 6)



Miércoles: Rosa (7 y 8)



Jueves: Rojo (3 y 4)



Viernes: Azul (9 y 0)



Exención de Ecológicos: Los Hologramas 0 y 00 circulan libremente todos los días, a menos que se declare una Contingencia Ambiental.



El Domingo es Libre: Por defecto, los domingos no hay restricción para ningún holograma, salvo en contingencias.

 2. Reglas de Escalabilidad (La Inteligencia del AG)

Aquí es donde entran los "diales" o genes de tu Algoritmo Genético. El AG decide la severidad del castigo basándose en el balance de Emisiones y Economía. 4. Horarios Dinámicos: El AG puede decidir si el castigo dura el día completo (05:00 a 22:00) o si premia a los ciudadanos recortándolo a la tarde (05:00 a 16:00). 5. Zonas Dinámicas: El AG decide si la restricción aplica a toda la ciudad (Total) o solo al núcleo de mayor tráfico (Centro). 6. Castigo de Sábados (Holograma 1): El AG puede decidir castigar al H1 desde 1 hasta todos los sábados del mes. 7. Progresión Estricta del Holograma 2: El castigo para los autos más viejos (H2) siempre escala en este orden lógico sin saltarse pasos:





Nivel 1: 3 Sábados.



Nivel 2: 4 Sábados.



Nivel 3: Todos los sábados del mes (sean 4 o 5).



Nivel 4: Todos los sábados + 1 día extra entre semana.

Nivel 5: Todos los sábados + 2 días extra entre semana.



Buena pregunta. Sí, definitivamente deberían ser dinámicos y sí, la misma lógica aplica:

Baja contaminación → [5,16] y "centro" (menos horas, menos zona)
Alta contaminación → [5,22] y "total" (máximas horas, toda la ciudad)

El cromosoma ya tiene los genes para esto (4, 5, 6, 7). El problema es que la funcion_objetivo no los toma en cuenta — solo evalúa sábados y extras. La solución es incorporar zona y horario como factores de cobertura efectiva que escalan el beneficio ambiental y el costo económico.
"""