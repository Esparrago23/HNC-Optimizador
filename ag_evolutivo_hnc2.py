"""
ag_evolutivo_hnc2.py — HNC-Optimizador v3
Motor evolutivo para el esquema "Hoy No Circula" (CDMX)

FILOSOFÍA: AG LIBRE con penalizaciones blandas.
  El cromosoma puede codificar cualquier combinación de restricciones.
  Las reglas del HNC no se imponen como límites duros: se penalizan
  proporcionalmente en la función de aptitud. Esto permite al AG explorar
  el espacio de soluciones con libertad y converger al óptimo por sí solo.

Estructura del AG (según especificación del proyecto):
  §1  FuncionAptitud           — Evalúa cada individuo
  §2  FuncionInicializacion    — Genera la población inicial
  §3  FuncionGeneracionParejas — Selección de padres
  §4  FuncionCruza             — Operador de recombinación
  §5  FuncionMutacion          — Operador de perturbación
  §6  FuncionPoda              — Selección de supervivientes

Cromosoma (13 genes reales en [0, 1]):
  Gen 0     : Días H0 por mes (0–2 semanas)
  Gen 1     : Sábados H1 (0 – total_sábs)
  Gen 2     : Sábados H2 (0 – total_sábs)
  Gen 3     : Días extra H2 (0–4; penalizado si > 2 o inconsistente)
  Gen 4     : Colores con horario reducido en H1 (0–5)
  Gen 5     : Colores con horario reducido en H2 (0–5)
  Gen 6     : Fase de distribución de sábados H1 (qué sábados del mes)
  Gen 7     : Fase de distribución de sábados H2
  Gens 8–12 : Día de la semana asignado por color (Verde, Amarillo, Rosa, Rojo, Azul)

Variables a optimizar (fórmulas del proyecto):
  E  = Σ Total_i · (1 − Ri) · EFi · D          → MINIMIZAR (emisiones g/día)
  IE = Σ Ri · Total_i · PL,i · Ci               → MINIMIZAR (impacto económico)
  v  = vf / (1 + α·(M/C)^β)                    → MAXIMIZAR (velocidad BPR km/h)

Función de aptitud global:
  Aptitud = v / ((E + ε)(IE + ε)) × escala · factor_penalización
"""

import json
import heapq
import math
import random
from calendar import monthcalendar, monthrange
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ════════════════════════════════════════════════════════════════════════════
# CONSTANTES GLOBALES
# ════════════════════════════════════════════════════════════════════════════

GENES = 13

DEFAULT_PARAMS: Dict[str, Any] = {
    "pop_size":               100,
    "generaciones":           150,
    "mutacion":               0.06,
    "elitismo":               2,
    "peso_equidad":           1.0,
    "peso_ambiental_critico": 2.2,
    "peso_economico":         1.55,
    "nivel_imeca":            150,
    "start_month":            "2026-04",
    "meses":                  6,
    "prob_cruza":             0.65,
    "estrategia_seleccion":   "torneo",
    "estrategia_cruza":       "uniforme",
    "estrategia_mutacion":    "gaussiana",
}

DEFAULT_POP_SIZE   = DEFAULT_PARAMS["pop_size"]
DEFAULT_GENERATIONS = DEFAULT_PARAMS["generaciones"]

HOLOGRAMAS   = ["H00", "H0", "H1", "H2"]
COLOR_ORDER  = ["Verde", "Amarillo", "Rosa", "Rojo", "Azul"]
GRUPOS_PLACA = {"Amarillo": [5, 6], "Rosa": [7, 8], "Rojo": [3, 4], "Verde": [1, 2], "Azul": [9, 0]}
DIAS_SEMANA  = ["lunes", "martes", "miercoles", "jueves", "viernes"]
WEEKDAY_IDX  = {d: i for i, d in enumerate(DIAS_SEMANA)}

# Asignación fija de días por color (días base por defecto del HNC actual)
DIA_POR_COLOR = {
    "Verde":    "jueves",
    "Amarillo": "lunes",
    "Rosa":     "martes",
    "Rojo":     "miercoles",
    "Azul":     "viernes",
}

CONT_LEVELS  = ["buena", "aceptable", "mala", "muy_mala", "extrema"]
CONT_FACTORS = {
    "buena":    0.35,
    "aceptable":0.90,
    "mala":     1.45,
    "muy_mala": 2.21,
    "extrema":  2.90,
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTORNO_PATH = PROJECT_ROOT / "data" / "entorno_cdmx.json"
RESULT_PATH  = PROJECT_ROOT / "data" / "resultado_ag_hnc.json"
EPS          = 1e-9


# ════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ════════════════════════════════════════════════════════════════════════════

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def imeca_level(nivel: float) -> str:
    """Clasifica el nivel IMECA según los umbrales del proyecto."""
    if nivel <= 50:  return "buena"
    if nivel <= 100: return "aceptable"
    if nivel <= 150: return "mala"
    if nivel <= 200: return "muy_mala"
    return "extrema"



def obtener_metas_imeca(total_sabs: int, nivel: float) -> Dict[str, Any]:
    """
    Rangos y metas ideales por nivel IMECA — usados SOLO en penalizaciones
    blandas. El AG es libre de proponer cualquier valor; las metas lo guían.

    Resultado ideal buscado:
    ┌──────────────────┬───────────┬───────────────┬────────────────────────────┬───────────┐
    │ Nivel            │ H0 días   │ H1 sábados    │ H2 sábados + extras        │ n_light   │
    ├──────────────────┼───────────┼───────────────┼────────────────────────────┼───────────┤
    │ Buena   (0–50)   │ 0         │ 0             │ exactamente 3, 0 extras    │ 0         │
    │ Aceptable(51–100)│ 0         │ 1–3           │ todos los sábs, 0 extras   │ 0–1       │
    │ Mala   (101–150) │ 0         │ 2–4           │ 4-todos + 0-1 extra*       │ 0–2       │
    │ Muy mala(151–200)│ 0–2       │ 3–4           │ todos + 0–2 extras         │ 0–3       │
    │ Extrema  (201+)  │ 1–2       │ 4             │ todos + exactamente 2 ext. │ 0–4       │
    └──────────────────┴───────────┴───────────────┴────────────────────────────┴───────────┘
    (*) extras solo cuando h2_sabs == total_sabs (sábados ya completos)
    """
    ts  = total_sabs
    niv = imeca_level(nivel)

    if niv == "buena":
        return {
            "h1_lo": 0, "h1_hi": 0,          "h1_target": 0,
            "h2_lo": min(3, ts),
            "h2_hi": min(3, ts),              "h2_target": min(3, ts),
            "ex_lo": 0, "ex_hi": 0,           "ex_target": 0,
            "ex_req_full": False,
            "h0_lo": 0, "h0_hi": 0,
            "nlight_hi": 0,
        }
    elif niv == "aceptable":
        return {
            "h1_lo": 1, "h1_hi": min(3, ts),  "h1_target": min(2, ts),
            "h2_lo": min(3, ts),
            "h2_hi": ts,                       "h2_target": ts,
            "ex_lo": 0, "ex_hi": 0,            "ex_target": 0,
            "ex_req_full": False,
            "h0_lo": 0, "h0_hi": 0,
            "nlight_hi": 1,
        }
    elif niv == "mala":
        return {
            "h1_lo": 2, "h1_hi": min(4, ts),  "h1_target": min(3, ts),
            "h2_lo": min(4, ts),
            "h2_hi": ts,                       "h2_target": ts,
            "ex_lo": 0, "ex_hi": 1,            "ex_target": 0,
            "ex_req_full": True,   # extras solo si h2_sabs == total_sabs
            "h0_lo": 0, "h0_hi": 0,
            "nlight_hi": 2,
        }
    elif niv == "muy_mala":
        return {
            "h1_lo": 3, "h1_hi": min(4, ts),  "h1_target": min(4, ts),
            "h2_lo": ts, "h2_hi": ts,          "h2_target": ts,
            "ex_lo": 0,  "ex_hi": 2,           "ex_target": 1,
            "ex_req_full": True,
            "h0_lo": 0,  "h0_hi": 2,
            "nlight_hi": 3,
        }
    else:  # extrema
        return {
            "h1_lo": min(4, ts), "h1_hi": min(4, ts), "h1_target": min(4, ts),
            "h2_lo": ts,         "h2_hi": ts,          "h2_target": ts,
            "ex_lo": 2,          "ex_hi": 2,           "ex_target": 2,
            "ex_req_full": True,
            "h0_lo": 1,          "h0_hi": 2,
            "nlight_hi": 4,
        }


def parse_ym(value: str) -> Tuple[int, int]:
    y, m = value.split("-")
    return int(y), int(m)


def add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    t = year * 12 + (month - 1) + delta
    return t // 12, t % 12 + 1


def days_in_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def total_saturdays(year: int, month: int) -> int:
    return sum(1 for w in monthcalendar(year, month) if w[5] != 0)


def dates_for_weekday(year: int, month: int, wd: int) -> List[str]:
    """Todas las fechas ISO del mes para un día de la semana dado (0=lunes)."""
    return [
        date(year, month, day).isoformat()
        for week in monthcalendar(year, month)
        for day in [week[wd]] if day
    ]


def pick_dates(year: int, month: int, wd: int, count: int, offset: int = 0) -> List[str]:
    """Selecciona `count` fechas de un weekday, usando `offset` como fase."""
    all_d = dates_for_weekday(year, month, wd)
    if not all_d or count <= 0:
        return []
    count = min(count, len(all_d))
    start = offset % max(1, len(all_d) - count + 1)
    return all_d[start: start + count]


def reparar_dias(propuesta: Dict[str, str]) -> Dict[str, str]:
    """
    Garantiza permutación válida color→día: cada color tiene un día único.
    Si dos colores proponen el mismo día, el segundo recibe el primer día
    disponible restante. Esto es la parte Lamarckiana del AG.
    """
    usados: set = set()
    resultado: Dict[str, str] = {}
    disponibles = list(DIAS_SEMANA)

    for color in COLOR_ORDER:
        dia = propuesta.get(color, DIA_POR_COLOR[color])
        if dia not in DIAS_SEMANA:
            dia = DIA_POR_COLOR[color]
        if dia not in usados:
            resultado[color] = dia
            usados.add(dia)
            if dia in disponibles:
                disponibles.remove(dia)
        else:
            nuevo = disponibles[0] if disponibles else DIAS_SEMANA[0]
            resultado[color] = nuevo
            usados.add(nuevo)
            if nuevo in disponibles:
                disponibles.remove(nuevo)

    return resultado


def cargar_entorno() -> Dict[str, Any]:
    """Carga entorno_cdmx.json. Devuelve {} si no existe o hay error."""
    if not ENTORNO_PATH.exists():
        return {}
    try:
        with ENTORNO_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def factor_mensual(entorno: Dict[str, Any], month: int) -> float:
    """Factor de contaminación mensual desde entorno_cdmx.json."""
    ajustes = entorno.get("ajustes_mensuales", {})
    aj = ajustes.get(f"{month:02d}", {})
    try:
        return clamp(float(aj.get("factor_contaminacion", 1.0)), 0.70, 1.50)
    except Exception:
        return 1.0


# ════════════════════════════════════════════════════════════════════════════
# DECODIFICADOR  — SIN RESTRICCIONES DURAS
# ════════════════════════════════════════════════════════════════════════════

def decodificar(ind: List[float], total_sabs: int) -> Dict[str, Any]:
    """
    Convierte el cromosoma real [0,1]^13 a decisiones concretas de restricción.

    No aplica ningún límite duro: el AG puede proponer 0 sábados H1 con IMECA
    extrema, o 4 días extra con sábados incompletos. Las penalizaciones en
    FuncionAptitud guían al AG lejos de estas soluciones inconsistentes.

    Corrección Lamarckiana: la asignación color→día se repara antes de
    devolverse, y los genes del cromosoma se actualizan en el motor evolutivo
    para que la reparación se herede (ver ejecutar_ag).
    """
    h0_count = int(ind[0] * 3)                               # 0, 1 o 2
    h1_sabs  = min(total_sabs, int(ind[1] * (total_sabs + 1)))
    h2_sabs  = min(total_sabs, int(ind[2] * (total_sabs + 1)))
    h2_extra = int(ind[3] * 5)                               # 0–4 (libre; penalizado si > 2)
    n_lh1    = min(5, int(ind[4] * 6))                       # 0–5 colores horario reducido H1
    n_lh2    = min(5, int(ind[5] * 6))                       # 0–5 colores horario reducido H2
    phase_h1 = int(ind[6] * 5)
    phase_h2 = int(ind[7] * 5)

    propuesta = {
        color: DIAS_SEMANA[min(4, int(ind[8 + i] * 5))]
        for i, color in enumerate(COLOR_ORDER)
    }
    color_dia = reparar_dias(propuesta)

    return {
        "h0_weekday_count": h0_count,
        "sabados_h1":       h1_sabs,
        "sabados_h2":       h2_sabs,
        "dias_extra_h2":    h2_extra,
        "n_light_h1":       n_lh1,
        "n_light_h2":       n_lh2,
        "phase_h1":         phase_h1,
        "phase_h2":         phase_h2,
        "color_dia":        color_dia,
    }


# ════════════════════════════════════════════════════════════════════════════
# §1 — FUNCIÓN DE APTITUD
# ════════════════════════════════════════════════════════════════════════════

def FuncionAptitud(
    ind: List[float],
    entorno: Dict[str, Any],
    total_sabs: int,
    nivel_imeca: float,
    peso_ambiental: float = 2.2,
    peso_economico: float = 1.55,
) -> float:
    """
    Calcula la aptitud de un individuo.

    Fórmula base (PDF del proyecto):
        Aptitud = v / ((E + ε)(IE + ε)) × escala

    Penalizaciones blandas (AG libre):
        - Lejanía a la escalera H2 esperada según IMECA
        - H2 con menos sábados que H1
        - Días extra con sábados incompletos (inconsistencia)
        - Días extra > 2 (fuera del rango práctico)
        - H1 por debajo del mínimo esperado
        - Uso excesivo de H0 (reservado para contingencias)

    Las penalizaciones reducen el fitness multiplicativamente,
    nunca lo anulan del todo (mínimo 1% del fitness base).
    """
    sol = decodificar(ind, total_sabs)

    # ── Tasas de restricción Ri ──────────────────────────────────────────
    cum      = float(entorno.get("cumplimiento_ciudadano", 0.85))
    dias_mes = 30
    dias_hab = max(1, dias_mes - total_sabs)

    extra_efectivo = min(sol["dias_extra_h2"], 2)  # máx. 2 extra en el cálculo de R
    R = {
        "H00": 0.0,
        "H0" : cum * (sol["h0_weekday_count"] * 4 / dias_mes),
        "H1" : cum * (dias_hab / 5 + sol["sabados_h1"]) / dias_mes,
        "H2" : cum * (dias_hab / 5 + sol["sabados_h2"] + extra_efectivo) / dias_mes,
    }
    R = {k: clamp(v) for k, v in R.items()}

    veh = entorno.get("vehiculos", {})
    D   = float(entorno.get("distancia_promedio_km", 24.0))

    # ── E: Emisiones Totales [g/día] ──────────────────────────────────
    E = sum(
        float(v.get("total", 0)) * (1.0 - R.get(h, 0.0))
        * float(v.get("ef", 1.0)) * D
        for h, v in veh.items()
    ) or EPS

    # ── IE: Impacto Económico Social ──────────────────────────────────
    IE = sum(
        R.get(h, 0.0) * float(v.get("total", 0))
        * float(v.get("p_l", 0.3)) * float(v.get("costo", 1.0))
        for h, v in veh.items()
    ) or EPS

    # ── v: Velocidad Promedio BPR [km/h] ──────────────────────────────
    M     = sum(float(v.get("total", 0)) * (1.0 - R.get(h, 0.0)) for h, v in veh.items())
    trf   = entorno.get("trafico", {})
    vf    = float(trf.get("v_f", 45.0))
    C     = float(trf.get("capacidad_c", 3_500_000))
    alpha = float(trf.get("alpha", 0.15))
    beta  = float(trf.get("beta", 4.0))
    v_bpr = vf / (1.0 + alpha * (M / max(C, 1.0)) ** beta)

    # ── Fitness base — fórmula del PDF ───────────────────────────────
    # Amplificamos el peso ambiental según el IMECA del mes
    f_amb = 1.0 + max(0.0, (nivel_imeca - 100) / 100.0) * (peso_ambiental - 1.0)
    fitness_base = v_bpr / ((E * f_amb + EPS) * (IE * peso_economico + EPS)) * 1e12

    # ── Penalizaciones blandas ────────────────────────────────────────
    mts      = obtener_metas_imeca(total_sabs, nivel_imeca)
    imeca_w  = max(1.0, nivel_imeca / 100.0)
    h1_sabs  = sol["sabados_h1"]
    h2_sabs  = sol["sabados_h2"]
    h2_ex    = sol["dias_extra_h2"]
    h0_cnt   = sol["h0_weekday_count"]
    n_lh1    = sol["n_light_h1"]
    n_lh2    = sol["n_light_h2"]
    pen      = 0.0
    ts       = total_sabs

    # ── P1: H1 sábados ───────────────────────────────────────────────
    # Pull suave hacia el target (siempre activo)
    pen += abs(h1_sabs - mts["h1_target"]) / max(1, ts) * 3.5 * imeca_w
    # Penalización adicional si está fuera del rango [lo, hi]
    if h1_sabs < mts["h1_lo"]:
        pen += (mts["h1_lo"] - h1_sabs) / max(1, ts) * 7.0 * imeca_w
    if h1_sabs > mts["h1_hi"]:
        pen += (h1_sabs - mts["h1_hi"]) / max(1, ts) * 7.0 * imeca_w

    # ── P2: H2 sábados ───────────────────────────────────────────────
    pen += abs(h2_sabs - mts["h2_target"]) / max(1, ts) * 4.0 * imeca_w
    if h2_sabs < mts["h2_lo"]:
        pen += (mts["h2_lo"] - h2_sabs) / max(1, ts) * 8.0 * imeca_w
    if h2_sabs > mts["h2_hi"]:
        pen += (h2_sabs - mts["h2_hi"]) / max(1, ts) * 6.0 * imeca_w

    # ── P3: H2 días extra ────────────────────────────────────────────
    if mts["ex_req_full"] and h2_sabs < ts and h2_ex > 0:
        # Extras sin tener todos los sábados: inconsistencia grave
        pen += h2_ex * 10.0 * imeca_w
    else:
        # Dentro de la lógica permitida: pull + rango
        pen += abs(h2_ex - mts["ex_target"]) / 2.0 * 3.0 * imeca_w
        if h2_ex < mts["ex_lo"]:
            pen += (mts["ex_lo"] - h2_ex) / 2.0 * 7.0 * imeca_w
        if h2_ex > mts["ex_hi"]:
            pen += (h2_ex - mts["ex_hi"]) / 2.0 * 8.0 * imeca_w

    # ── P4: H2 siempre >= H1 en sábados (regla invariante) ───────────
    if h2_sabs < h1_sabs:
        pen += (h1_sabs - h2_sabs) / max(1, ts) * 9.0

    # ── P5: H0 días fijos ────────────────────────────────────────────
    # Debajo del mínimo (extrema requiere al menos 1)
    if h0_cnt < mts["h0_lo"]:
        pen += (mts["h0_lo"] - h0_cnt) * 5.0 * imeca_w
    # Por encima del máximo: cuadrático (uso excesivo de medida excepcional)
    if h0_cnt > mts["h0_hi"]:
        pen += (h0_cnt - mts["h0_hi"]) ** 2 * 4.0

    # ── P6: Horario/zona reducido — deben ser pocos ───────────────────
    # (5–16, centro) y (5–16, total) son escasos; aumentan con la contaminación.
    # nlight_hi es el máximo de grupos de color que pueden tener horario reducido.
    nh_hi = mts["nlight_hi"]
    if n_lh1 > nh_hi:
        pen += (n_lh1 - nh_hi) * 2.5
    if n_lh2 > nh_hi:
        pen += (n_lh2 - nh_hi) * 2.5
    # Nunca todos los 5 grupos con horario reducido (el mes entero no circula)
    if n_lh1 == 5:
        pen += 5.0
    if n_lh2 == 5:
        pen += 5.0

    # Factor de penalización: reduce el fitness entre 1% y 100%
    factor_pen = clamp(1.0 - pen * 0.07, 0.01, 1.0)
    return fitness_base * factor_pen


# ════════════════════════════════════════════════════════════════════════════
# §2 — INICIALIZACIÓN
# ════════════════════════════════════════════════════════════════════════════

def FuncionInicializacion(pop_size: int) -> List[List[float]]:
    """
    Genera la población inicial con valores aleatorios uniformes en [0, 1].
    Se usa representación real (en lugar de binaria) porque las variables
    de decisión del HNC son continuas o de rango amplio.
    """
    return [[random.random() for _ in range(GENES)] for _ in range(pop_size)]


# ════════════════════════════════════════════════════════════════════════════
# §3 — GENERACIÓN DE PAREJAS (Selección)
# ════════════════════════════════════════════════════════════════════════════

def FuncionGeneracionParejas(
    poblacion: List[List[float]],
    aptitudes: List[float],
    estrategia: str = "torneo",
) -> List[float]:
    """
    Selecciona un padre de la población según la estrategia indicada.
    Llamar dos veces para obtener la pareja completa (padre1, padre2).

    ruleta  — Selección proporcional a la aptitud (ajustada para negativos).
    torneo  — El mejor de k=3 candidatos aleatorios. Más robusto con escalas extremas.
    ranking — Proporcional al rango en el ranking de aptitud.
    """
    if estrategia == "ruleta":
        offset    = abs(min(aptitudes)) + EPS if min(aptitudes) < 0 else 0.0
        ajustadas = [a + offset for a in aptitudes]
        total     = sum(ajustadas)
        if total <= 0:
            return random.choice(poblacion)[:]
        r, acum = random.uniform(0.0, total), 0.0
        for ind, fit in zip(poblacion, ajustadas):
            acum += fit
            if acum >= r:
                return ind[:]
        return poblacion[-1][:]

    if estrategia == "torneo":
        idxs   = random.sample(range(len(poblacion)), min(3, len(poblacion)))
        ganador = max(idxs, key=lambda i: aptitudes[i])
        return poblacion[ganador][:]

    # ranking lineal
    orden = sorted(range(len(poblacion)), key=lambda i: aptitudes[i])
    pesos = list(range(1, len(poblacion) + 1))
    total = sum(pesos)
    r, acum = random.uniform(0, total), 0.0
    for pos, idx in enumerate(orden):
        acum += pesos[pos]
        if acum >= r:
            return poblacion[idx][:]
    return poblacion[orden[-1]][:]


# ════════════════════════════════════════════════════════════════════════════
# §4 — CRUZA
# ════════════════════════════════════════════════════════════════════════════

def FuncionCruza(
    padre1: List[float],
    padre2: List[float],
    prob_cruza: float = 0.65,
    estrategia: str   = "uniforme",
) -> Tuple[List[float], List[float]]:
    """
    Recombina dos padres para producir dos hijos.
    Si random() ≥ prob_cruza, los padres se copian sin cambios.

    un_punto  — Un punto de corte aleatorio p ∈ [1, GENES−1].
    dos_puntos — Dos puntos a < b; el segmento central se intercambia.
    uniforme  — Cada gen se intercambia con P=0.5 (mayor exploración).
    """
    if random.random() >= prob_cruza:
        return padre1[:], padre2[:]

    if estrategia == "un_punto":
        pt = random.randint(1, GENES - 1)
        return padre1[:pt] + padre2[pt:], padre2[:pt] + padre1[pt:]

    if estrategia == "dos_puntos":
        a, b = sorted(random.sample(range(1, GENES), 2))
        h1 = padre1[:a] + padre2[a:b] + padre1[b:]
        h2 = padre2[:a] + padre1[a:b] + padre2[b:]
        return h1, h2

    # uniforme (por defecto)
    h1 = [padre2[i] if random.random() < 0.5 else padre1[i] for i in range(GENES)]
    h2 = [padre1[i] if h1[i] == padre2[i] else padre2[i] for i in range(GENES)]
    return h1, h2


# ════════════════════════════════════════════════════════════════════════════
# §5 — MUTACIÓN
# ════════════════════════════════════════════════════════════════════════════

def FuncionMutacion(
    individuo: List[float],
    prob: float      = 0.06,
    estrategia: str  = "gaussiana",
) -> List[float]:
    """
    Muta gen a gen con probabilidad `prob`. Todos los valores se mantienen en [0, 1].

    uniforme  — Perturbación ε ~ U(−0.1, 0.1). Cambios de magnitud constante.
    gaussiana — Perturbación ε ~ N(0, 0.08). Favorece ajuste fino; σ=0.08
                para escapar mesetas con más facilidad que el σ=0.05 clásico.
    reset     — El gen se reemplaza por un valor aleatorio en [0, 1].
                Exploración global; útil cuando el AG está estancado.
    """
    mutado = individuo[:]
    for i in range(GENES):
        if random.random() < prob:
            if estrategia == "gaussiana":
                mutado[i] = clamp(individuo[i] + random.gauss(0, 0.08))
            elif estrategia == "reset":
                mutado[i] = random.random()
            else:  # uniforme
                mutado[i] = clamp(individuo[i] + random.uniform(-0.1, 0.1))
    return mutado


# ════════════════════════════════════════════════════════════════════════════
# §6 — PODA
# ════════════════════════════════════════════════════════════════════════════

def FuncionPoda(
    poblacion: List[List[float]],
    aptitudes: List[float],
    tam: int,
    elitismo: int = 2,
) -> Tuple[List[List[float]], float]:
    """
    Reduce la población al tamaño objetivo `tam` con elitismo.

    Estrategia: reemplazo generacional.
      1. Se ordenan todos los individuos de mayor a menor aptitud.
      2. Los primeros `elitismo` pasan directamente (monotonía garantizada).
      3. Se conservan los primeros `tam` en total.

    Retorna además la diversidad genética (desviación estándar promedio
    por gen): 0 = clones, ~0.29 = máximo aleatorio.
    """
    ranking   = sorted(zip(poblacion, aptitudes), key=lambda x: x[1], reverse=True)
    nueva_gen = [ind[:] for ind, _ in ranking[:tam]]

    diversidad = 0.0
    if len(nueva_gen) >= 2:
        for g in range(GENES):
            vals  = [ind[g] for ind in nueva_gen]
            media = sum(vals) / len(vals)
            var   = sum((v - media) ** 2 for v in vals) / len(vals)
            diversidad += var ** 0.5
        diversidad /= GENES

    return nueva_gen, diversidad


# ════════════════════════════════════════════════════════════════════════════
# CONSTRUCCIÓN DE REGLAS DEL MES  (JSON de salida → frontend)
# ════════════════════════════════════════════════════════════════════════════

def construir_reglas_mes(
    year: int,
    month: int,
    contaminacion: str,
    sol: Dict[str, Any],
    nivel_imeca: float,
) -> Dict[str, Any]:
    """
    Traduce la solución del AG a la estructura JSON que consume el frontend.

    Para H0 : usa 'fechas_restriccion' (fechas ISO concretas).
    Para H1 : usa 'sabados' (números de sábado, base 1).
    Para H2 : usa 'sabados' + 'extras' (fechas ISO extra) +
              'fechas_restriccion' = extras (para compatibilidad con la tabla
              del esquema que lee este campo directamente del JSON crudo).
    """
    ts       = total_saturdays(year, month)
    color_dia = sol["color_dia"]

    # Clampear aquí solo para el output final (el AG es libre de proponer más)
    h1_sabs  = min(ts, sol["sabados_h1"])
    h2_sabs  = min(ts, sol["sabados_h2"])
    h2_extra = min(2, sol["dias_extra_h2"])
    h0_cnt   = min(2, sol["h0_weekday_count"])
    n_lh1    = sol["n_light_h1"]
    n_lh2    = sol["n_light_h2"]

    # Orden de prioridad para asignar horario reducido (5–16h / zona Centro)
    # Los colores con día más temprano en la semana tienen prioridad
    colors_sorted = sorted(COLOR_ORDER, key=lambda c: WEEKDAY_IDX.get(color_dia.get(c, "lunes"), 0))
    lh1_set = set(colors_sorted[:n_lh1])
    lh2_set = set(colors_sorted[:n_lh2])

    h00_col: Dict[str, Any] = {}
    h0_col:  Dict[str, Any] = {}
    h1_col:  Dict[str, Any] = {}
    h2_col:  Dict[str, Any] = {}

    for color in COLOR_ORDER:
        dia = color_dia.get(color, DIA_POR_COLOR[color])
        wd  = WEEKDAY_IDX.get(dia, 0)
        idx = COLOR_ORDER.index(color)  # offset para diversificar fechas

        # ── H00: libre, sin restricción ────────────────────────────────
        h00_col[color] = {
            "dia_base":           dia,
            "horario":            [5, 22],
            "zona":               "total",
            "fechas_restriccion": [],
            "sabados":            [],
        }

        # ── H0: restricción excepcional en días fijos (solo si IMECA alto)
        #   Las fechas deben ser contiguas dentro del mes.
        h0_fechas = pick_dates(year, month, wd, h0_cnt, offset=0)
        h0_col[color] = {
            "dia_base":           dia,
            "horario":            [5, 22],
            "zona":               "total",
            "fechas_restriccion": h0_fechas,
            "sabados":            [],
        }

        # ── H1: día fijo todo el mes + sábados variables ───────────────
        h1_hora = 16 if color in lh1_set else 22
        h1_zona = "centro" if color in lh1_set else "total"
        h1_col[color] = {
            "dia_base": dia,
            "sabados":  list(range(1, h1_sabs + 1)),
            "horario":  [5, h1_hora],
            "zona":     h1_zona,
        }

        # ── H2: día fijo + sábados + días extra ───────────────────────
        h2_hora = 16 if color in lh2_set else 22
        h2_zona = "centro" if color in lh2_set else "total"

        # Día extra: siguiente al fijo del color en la semana laboral.
        # Garantiza que cada color tenga un extra diferente (ya que los
        # días fijos son todos distintos tras la reparación).
        extra_wd = (wd + 1) % 5
        extras   = pick_dates(year, month, extra_wd, h2_extra, offset=idx)

        h2_col[color] = {
            "dia_base":           dia,
            "sabados":            list(range(1, h2_sabs + 1)),
            "horario":            [5, h2_hora],
            "zona":               h2_zona,
            "extras":             extras,             # el frontend (calendario) lo lee aquí
            "fechas_restriccion": extras,             # la tabla de esquema lo lee aquí
        }

    return {
        "mes":          month,
        "year":         year,
        "contaminacion":contaminacion,
        "h00": {"por_color": h00_col},
        "h0":  {"por_color": h0_col},
        "h1":  {"por_color": h1_col},
        "h2":  {"por_color": h2_col},
    }


# ════════════════════════════════════════════════════════════════════════════
# MOTOR EVOLUTIVO
# ════════════════════════════════════════════════════════════════════════════

def ejecutar_ag(
    entorno: Dict[str, Any],
    total_sabs: int,
    nivel_imeca: float,
    pop_size: int     = 100,
    generaciones: int = 150,
    prob_cruza: float = 0.65,
    prob_mut: float   = 0.06,
    elitismo: int     = 2,
    est_sel: str      = "torneo",
    est_cruz: str     = "uniforme",
    est_mut: str      = "gaussiana",
    peso_amb: float   = 2.2,
    peso_eco: float   = 1.55,
    stagnacion: int   = 15,
    mut_max: float    = 0.35,
    inject_pct: float = 0.10,
    div_min: float    = 0.04,
) -> Dict[str, Any]:
    """
    Motor evolutivo con estrategias configurables y mecanismo anti-convergencia.

    Características:
      - Selección: ruleta | torneo | ranking
      - Cruzamiento: un_punto | dos_puntos | uniforme
      - Mutación: uniforme | gaussiana | reset
      - Mutación adaptativa: la tasa sube si el AG se estanca
      - Inyección de diversidad: individuos aleatorios al detectar estancamiento
        o baja diversidad genética
      - Corrección Lamarckiana: los genes de color→día se actualizan en el
        cromosoma al decodificar (el AG hereda la reparación)
    """
    def evaluar(ind: List[float]) -> float:
        return FuncionAptitud(ind, entorno, total_sabs, nivel_imeca, peso_amb, peso_eco)

    def evaluar_y_reparar(ind: List[float]) -> Tuple[float, List[float]]:
        """Evalúa y aplica la corrección Lamarckiana al cromosoma."""
        sol = decodificar(ind, total_sabs)
        # Escribir de vuelta los genes de color→día reparados
        for i, color in enumerate(COLOR_ORDER):
            dia = sol["color_dia"].get(color, DIA_POR_COLOR[color])
            ind[8 + i] = (WEEKDAY_IDX.get(dia, 0) + 0.5) / 5.0
        return evaluar(ind), ind

    poblacion = FuncionInicializacion(pop_size)
    best_fit  = -math.inf
    best_ind: List[float] = []

    hist_mejor: List[float] = []
    hist_peor:  List[float] = []
    hist_prom:  List[float] = []
    hist_vars:  List[Dict[str, Any]] = []

    stag_cnt  = 0
    prev_best = -math.inf
    div_act   = 1.0

    for _ in range(generaciones):
        # Evaluación y reparación Lamarckiana
        pares = [evaluar_y_reparar(ind) for ind in poblacion]
        apts  = [a for a, _ in pares]
        poblacion = [ind for _, ind in pares]

        best_idx  = max(range(len(poblacion)), key=lambda i: apts[i])
        hist_mejor.append(float(apts[best_idx]))
        hist_peor.append(float(min(apts)))
        hist_prom.append(float(sum(apts) / len(apts)))

        sol_gen = decodificar(poblacion[best_idx], total_sabs)
        hist_vars.append({
            "sabados_h1":       sol_gen["sabados_h1"],
            "sabados_h2":       sol_gen["sabados_h2"],
            "dias_extra_h2":    sol_gen["dias_extra_h2"],
            "h0_weekday_count": sol_gen["h0_weekday_count"],
            "n_light_h1":       sol_gen["n_light_h1"],
            "n_light_h2":       sol_gen["n_light_h2"],
        })

        if apts[best_idx] > best_fit:
            best_fit, best_ind = float(apts[best_idx]), poblacion[best_idx][:]

        stag_cnt  = 0 if apts[best_idx] > prev_best + 1e-8 else stag_cnt + 1
        prev_best = max(prev_best, float(apts[best_idx]))

        # Mutación adaptativa: sube gradualmente al estancarse
        prob_mut_act = prob_mut + (mut_max - prob_mut) * min(1.0, stag_cnt / max(1, stagnacion))

        # Elitismo: los mejores pasan directamente
        elite_n = min(len(poblacion), max(1, elitismo))
        elite   = [poblacion[i][:] for i in heapq.nlargest(elite_n, range(len(poblacion)), key=apts.__getitem__)]
        nueva   = list(elite)

        # Inyección de diversidad si hay estancamiento o poca diversidad
        if stag_cnt >= stagnacion or div_act < div_min:
            n_inject = max(1, int(pop_size * inject_pct))
            nueva.extend(FuncionInicializacion(n_inject))

        # Generación de nueva población con cruza y mutación
        while len(nueva) < pop_size:
            p1 = FuncionGeneracionParejas(poblacion, apts, est_sel)
            p2 = FuncionGeneracionParejas(poblacion, apts, est_sel)
            h1, h2 = FuncionCruza(p1, p2, prob_cruza, est_cruz)
            nueva.append(FuncionMutacion(h1, prob_mut_act, est_mut))
            if len(nueva) < pop_size:
                nueva.append(FuncionMutacion(h2, prob_mut_act, est_mut))

        # Poda: selección de supervivientes
        apts_nueva    = [evaluar(ind) for ind in nueva]
        poblacion, div_act = FuncionPoda(nueva, apts_nueva, pop_size, elitismo)

    return {
        "mejor_fitness":      best_fit,
        "mejor_individuo":    best_ind,
        "historial_fitness":  hist_mejor,
        "historial_peor":     hist_peor,
        "historial_promedio": hist_prom,
        "historial_vars":     hist_vars,
    }


# ════════════════════════════════════════════════════════════════════════════
# GENERADOR PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

def generar_json_final(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Ejecuta el AG para cada mes del horizonte y genera resultado_ag_hnc.json.

    Proceso por mes:
      1. Lee el factor de contaminación mensual desde entorno_cdmx.json.
      2. Ajusta el nivel IMECA con ese factor.
      3. Ejecuta el AG con el IMECA ajustado.
      4. Decodifica la mejor solución.
      5. Construye las reglas del mes y las guarda en el JSON de salida.
    """
    cfg     = {**DEFAULT_PARAMS, **(params or {})}
    entorno = cargar_entorno()

    start_y, start_m = parse_ym(str(cfg["start_month"]))
    n_meses   = max(1, int(cfg["meses"]))
    imeca     = float(cfg["nivel_imeca"])
    pop_size  = int(cfg["pop_size"])
    gens      = int(cfg["generaciones"])
    prob_cru  = float(cfg.get("prob_cruza", 0.65))
    prob_mut  = float(cfg["mutacion"])
    elit      = int(cfg["elitismo"])
    est_sel   = str(cfg.get("estrategia_seleccion",  "torneo"))
    est_cruz  = str(cfg.get("estrategia_cruza",      "uniforme"))
    est_mut   = str(cfg.get("estrategia_mutacion",   "gaussiana"))
    peso_amb  = float(cfg.get("peso_ambiental_critico", 2.2))
    peso_eco  = float(cfg.get("peso_economico", 1.55))

    meses_out:    List[Dict[str, Any]] = []
    analytics:    List[Dict[str, Any]] = []
    fitness_list: List[float]          = []

    # Constantes para estimados de CO2 y autos
    FLOTA       = 6_000_000
    CO2_KG      = 4.2
    EFECTIVIDAD = 0.60

    for i in range(n_meses):
        year_i, month_i = add_months(start_y, start_m, i)
        ts_i     = total_saturdays(year_i, month_i)
        f_mes    = factor_mensual(entorno, month_i)
        imeca_i  = imeca * f_mes          # IMECA ajustado al mes
        cont_i   = imeca_level(imeca_i)

        ag = ejecutar_ag(
            entorno      = entorno,
            total_sabs   = ts_i,
            nivel_imeca  = imeca_i,
            pop_size     = pop_size,
            generaciones = gens,
            prob_cruza   = prob_cru,
            prob_mut     = prob_mut,
            elitismo     = elit,
            est_sel      = est_sel,
            est_cruz     = est_cruz,
            est_mut      = est_mut,
            peso_amb     = peso_amb,
            peso_eco     = peso_eco,
        )

        fitness_list.append(ag["mejor_fitness"])
        sol = decodificar(ag["mejor_individuo"], ts_i)

        # Estimados rápidos de CO2 evitado y autos detenidos
        dias_mes_i = days_in_month(year_i, month_i)
        dias_hab_i = sum(1 for w in monthcalendar(year_i, month_i) for d in w[:5] if d)
        h2_cd = FLOTA * 0.55 / 5 * dias_hab_i
        h1_cd = FLOTA * 0.40 / 5 * dias_hab_i
        co2   = (h2_cd + h1_cd) * CO2_KG * EFECTIVIDAD / 1000
        autos = (h2_cd + h1_cd) / dias_mes_i / 1e6

        meses_out.append(
            construir_reglas_mes(year_i, month_i, cont_i, sol, imeca_i)
        )
        analytics.append({
            "mes":                  month_i,
            "year":                 year_i,
            "contaminacion":        cont_i,
            "factor_mensual":       round(f_mes, 4),
            "nivel_imeca_efectivo": round(imeca_i, 1),
            "historial_mejor":      ag["historial_fitness"],
            "historial_peor":       ag["historial_peor"],
            "historial_promedio":   ag["historial_promedio"],
            "historial_vars":       ag["historial_vars"],
            "variables_optimas":    {k: sol[k] for k in [
                "sabados_h1", "sabados_h2", "dias_extra_h2",
                "h0_weekday_count", "n_light_h1", "n_light_h2",
            ]},
            "co2_evitado_ton":    round(co2, 1),
            "autos_dia_millones": round(autos, 3),
        })

    resultado = {
        "timestamp":   str(date.today()),
        "parametros":  {k: cfg[k] for k in [
            "pop_size", "generaciones", "mutacion", "elitismo",
            "peso_equidad", "peso_ambiental_critico", "peso_economico",
            "nivel_imeca", "start_month", "meses", "prob_cruza",
        ]},
        "mejor_fitness": sum(fitness_list) / max(1, len(fitness_list)),
        "estrategias_usadas": {
            "seleccion": est_sel,
            "cruza":     est_cruz,
            "mutacion":  est_mut,
        },
        "mejor_solucion": {"meses": meses_out},
        "analytics":      {"por_mes": analytics},
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULT_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=4)

    return resultado


if __name__ == "__main__":
    res = generar_json_final()
    print(json.dumps({
        "mejor_fitness": round(res["mejor_fitness"], 4),
        "meses_generados": len(res["mejor_solucion"]["meses"]),
        "primer_mes": res["mejor_solucion"]["meses"][0]["contaminacion"],
    }, ensure_ascii=False, indent=2))
