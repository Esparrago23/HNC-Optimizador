import json
import itertools
import math
import random
from calendar import monthcalendar, monthrange
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# CONFIGURACIÓN BASE
# ============================================================================
GENES            = 16
DEFAULT_POP_SIZE = 100
DEFAULT_GENERATIONS = 120

DEFAULT_PARAMS = {
    "pop_size": 100, "generaciones": 120, "mutacion": 0.05, "elitismo": 2,
    "peso_equidad": 1, "peso_ambiental_critico": 2.2, "peso_economico": 1.55,
    "nivel_imeca": 150, "start_month": "2026-04", "meses": 6,
}

GRUPOS_PLACA = {"Amarillo": [5, 6], "Rosa": [7, 8], "Rojo": [3, 4], "Verde": [1, 2], "Azul": [9, 0]}
HOLOGRAMAS   = ["H00", "H0", "H1", "H2"]
COLOR_ORDER  = ["Verde", "Amarillo", "Rosa", "Rojo", "Azul"]

# ── Días: una sola fuente de verdad ─────────────────────────────────────────
_LOWER  = ["lunes", "martes", "miercoles", "jueves", "viernes"]
_TITULO = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
DIAS_SEMANA_LOWER = _LOWER
WEEKDAY_INDEX     = {d: i for i, d in enumerate(_LOWER)}
LOWER_TO_TITULO   = dict(zip(_LOWER, _TITULO))
LOWER_DIA         = dict(zip(_TITULO, _LOWER))

# ── Factores de contaminación → fitness ─────────────────────────────────────
CONTAMINATION_FACTORS: Dict[str, float] = {
    "buena": 0.35, "aceptable": 0.90, "mala": 1.45, "muy_mala": 2.20, "extrema": 2.90,
}

# ── Límites de política por nivel ────────────────────────────────────────────
# El AG decide DENTRO de estos rangos; la fitness function lo guía.
#
# Zona y horario para H1 y H2 son decididos libremente por el AG en todas
# las combinaciones válidas:  (total|centro) × (5-22|5-16)
# La fitness los pondera vía cov_h1 / cov_h2_avg — mayor contaminación →
# mayor cobertura premiada → el AG converge a total+5-22.
#
# Campos:
#   h2_total   : True solo en extrema (restriccion_total estructural)
#   h0_wd_max  : máximo días de restricción semanal para H0
#   h1_sab     : (min, max) sábados H1  —  None = total_sab
#   h2_sab_max : techo de sábados H2    —  None = total_sab
#   extras     : (min, max) días extra en H2  (máx absoluto = 2)
_CCONFIG: Dict[str, Any] = {
    "buena":    {"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(0, 1),    "h2_sab_max":3,    "extras":(0, 0)},
    "aceptable":{"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(0, 2),    "h2_sab_max":3,    "extras":(0, 0)},
    "mala":     {"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(3, None), "h2_sab_max":None, "extras":(0, 2)},
    "muy_mala": {"h2_total":False, "h0_wd_max":1,
                 "h1_sab":(3, None), "h2_sab_max":None, "extras":(1, 2)},
    "extrema":  {"h2_total":True,  "h0_wd_max":2,
                 "h1_sab":(3, None), "h2_sab_max":None, "extras":(1, 2)},
}

def _to_lower_zona(raw: Any) -> str:
    """Normaliza zona a minúsculas ('total' | 'centro')."""
    return "centro" if "entro" in str(raw) else "total"

PROJECT_ROOT   = Path(__file__).resolve().parent.parent
ENTORNO_PATH   = PROJECT_ROOT / "data" / "entorno_cdmx.json"
RESULTADO_PATH = PROJECT_ROOT / "data" / "resultado_ag_hnc.json"


# ============================================================================
# UTILIDADES GENERALES
# ============================================================================
def contamination_to_factor(c: str) -> float:
    return CONTAMINATION_FACTORS.get(c, 1.0)

def dia_base_por_defecto(color: str) -> str:
    return _LOWER[COLOR_ORDER.index(color)]

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def parse_year_month(value: str) -> Tuple[int, int]:
    y, m = value.split("-")
    return int(y), int(m)

def add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    t = year * 12 + (month - 1) + delta
    return t // 12, t % 12 + 1

def days_in_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]

def total_saturdays(year: int, month: int) -> int:
    return sum(1 for w in monthcalendar(year, month) if w[5] != 0)

def nth_weekday_dates(year: int, month: int, weekday: int, count: int) -> List[str]:
    return all_weekday_dates(year, month, weekday)[:max(0, count)]

def all_weekday_dates(year: int, month: int, weekday: int) -> List[str]:
    if not 0 <= weekday <= 6:
        return []
    return [
        date(year, month, day_num).isoformat()
        for week in monthcalendar(year, month)
        for day_num in [week[weekday]] if day_num
    ]

def weekly_restriction_dates(year: int, month: int, base_wd: int, days_per_week: int) -> List[str]:
    if days_per_week <= 0:
        return []
    dates = list(all_weekday_dates(year, month, base_wd))
    for offset in range(1, min(days_per_week, 3)):
        dates.extend(all_weekday_dates(year, month, (base_wd + offset) % 5))
    return sorted(set(dates))

def color_month_salt(year: int, month: int, color: str) -> int:
    ci = COLOR_ORDER.index(color) if color in COLOR_ORDER else 0
    cw = sum((i + 1) * ord(ch) for i, ch in enumerate(color))
    return year * 97 + month * 31 + (ci + 1) * 53 + cw

def spread_weekday_dates(year: int, month: int, weekday: int, count: int,
                         salt: int = 0, phase_bias: int = 0) -> List[str]:
    if count <= 0:
        return []
    all_d = all_weekday_dates(year, month, weekday)
    if not all_d or count >= len(all_d):
        return all_d[:count]
    mixed = salt ^ (salt >> 11) ^ (salt >> 19)
    max_s = len(all_d) - count
    if count == 1:
        return [all_d[(mixed + phase_bias + month + weekday) % len(all_d)]]
    start = (mixed + phase_bias) % (max_s + 1)
    return all_d[start:start + count]

def contamination_for_month(month: int, nivel_imeca: float) -> str:
    _ = month
    i = float(nivel_imeca)
    if i <= 50:   return "buena"
    if i <= 100:  return "aceptable"
    if i <= 150:  return "mala"
    if i <= 200:  return "muy_mala"
    return "extrema"

def h0_limits_from_imeca(nivel_imeca: float) -> Tuple[int, int]:
    if nivel_imeca > 200: return 2, 0
    if nivel_imeca > 150: return 1, 0
    return 0, 0

def sat_list(total_sab: int, wanted: int) -> List[int]:
    return list(range(1, min(total_sab, wanted) + 1))

def cargar_entorno_cdmx() -> Dict[str, Any]:
    if not ENTORNO_PATH.exists():
        return {}
    try:
        with ENTORNO_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def resumen_probabilidad_sabado(entorno: Dict[str, Any]) -> float:
    sabado = entorno.get("probabilidad_laboral_sabado_horaria", {}) if isinstance(entorno, dict) else {}
    if not isinstance(sabado, dict) or not sabado:
        return 1.0
    valores = [
        float(v["probabilidad_laboral"])
        for v in sabado.values()
        if isinstance(v, dict) and isinstance(v.get("probabilidad_laboral"), (int, float))
    ]
    return clamp01(sum(valores) / len(valores) / 0.5) if valores else 1.0

def reparar_asignacion_colores_dias(propuesta: Dict[str, str]) -> Dict[str, str]:
    usados, resultado, disponibles = set(), {}, set(_LOWER)
    for color in COLOR_ORDER:
        dia = propuesta.get(color, dia_base_por_defecto(color))
        if dia not in _LOWER:
            dia = dia_base_por_defecto(color)
        if dia not in usados:
            resultado[color] = dia; usados.add(dia); disponibles.discard(dia)
        else:
            default = dia_base_por_defecto(color)
            nuevo   = default if default in disponibles else sorted(disponibles)[0]
            resultado[color] = nuevo; usados.add(nuevo); disponibles.discard(nuevo)
    return resultado

def generar_asignaciones_mensuales_desde_base(
    base_map: Dict[str, str], meses_count: int, semilla: int,
) -> List[Dict[str, str]]:
    dias       = _LOWER[:]
    base_tuple = tuple(base_map[c] for c in COLOR_ORDER)
    todas      = list(itertools.permutations(dias, len(COLOR_ORDER)))
    rng        = random.Random(semilla)
    rng.shuffle(todas)
    seleccion: List[Tuple[str, ...]] = [base_tuple]
    usadas = {base_tuple}
    for perm in todas:
        if perm in usadas or all(perm[i] == seleccion[-1][i] for i in range(len(COLOR_ORDER))):
            continue
        seleccion.append(perm); usadas.add(perm)
        if len(seleccion) >= meses_count:
            break
    while len(seleccion) < meses_count:
        idx  = len(seleccion) % len(COLOR_ORDER)
        rot  = tuple(dias[idx:] + dias[:idx])
        cand = rot if rot not in usadas else next((p for p in todas if p not in usadas), rot)
        seleccion.append(cand); usadas.add(cand)
    return [{c: perm[i] for i, c in enumerate(COLOR_ORDER)} for perm in seleccion[:meses_count]]


# ============================================================================
# CONSTRUCCIÓN DE REGLAS POR MES
# ============================================================================
def construir_reglas_mes(
    year: int, month: int, contaminacion: str,
    color_to_day_lower: Dict[str, str],
    ag_decisions: Optional[Dict[str, Any]] = None,
    nivel_imeca: float = 150.0,
) -> Dict[str, Any]:
    ts  = total_saturdays(year, month)
    cfg = _CCONFIG.get(contaminacion, _CCONFIG["extrema"])

    # Valores estructurales fijos
    h2_total  = cfg["h2_total"]
    h0_wd_max = cfg["h0_wd_max"]

    # Topes numéricos del nivel
    h1_min, h1_max_cfg = cfg["h1_sab"]
    h1_max = ts if h1_max_cfg is None else min(ts, h1_max_cfg)
    h2_max = ts if cfg["h2_sab_max"] is None else min(ts, cfg["h2_sab_max"])
    ex_min, ex_max = cfg["extras"]

    # ── Decisiones del AG ────────────────────────────────────────────────────
    # Números: sábados, extras, días H0
    if ag_decisions:
        ag_h1 = int(ag_decisions.get("sabados_h1",       h1_max))
        ag_h2 = int(ag_decisions.get("sabados_h2",       h2_max))
        ag_ex = int(ag_decisions.get("dias_extra_h2",    ex_max))
        ag_h0 = int(ag_decisions.get("h0_weekday_count", h0_wd_max))
    else:
        ag_h1, ag_h2, ag_ex, ag_h0 = h1_max, h2_max, ex_max, h0_wd_max

    h1_sab           = max(h1_min, min(h1_max, ag_h1))
    h2_sab           = max(3,      min(h2_max, ag_h2))
    extras_per_color = max(ex_min, min(ex_max, ag_ex))
    h0_weekday_count = min(h0_wd_max, h0_limits_from_imeca(nivel_imeca)[0], ag_h0)

    # Zona y horario: el AG elige entre las 4 combinaciones válidas
    #   H1  → una zona y un horario uniformes para todos los colores
    #   H2  → por color (el AG puede diferenciar)
    #   H0/H00 → siempre total + 5-22 (contingencias, no se suavizan)
    if ag_decisions:
        h1_hora = int(ag_decisions.get("hora_fin_h1", 22))
        h1_zona = _to_lower_zona(ag_decisions.get("zona_h1", "Total"))
        h2_hora_map: Dict[str, int] = ag_decisions.get("h2_hora_por_color", {})
        h2_zona_map: Dict[str, str] = ag_decisions.get("h2_zona_por_color", {})
    else:
        h1_hora, h1_zona = 22, "total"
        h2_hora_map, h2_zona_map = {}, {}

    h00_por_color: Dict[str, Any] = {}
    h0_por_color:  Dict[str, Any] = {}
    h1_por_color:  Dict[str, Any] = {}
    h2_por_color:  Dict[str, Any] = {}

    for color in COLOR_ORDER:
        dia  = color_to_day_lower.get(color, dia_base_por_defecto(color))
        wd   = WEEKDAY_INDEX[dia]
        bias = COLOR_ORDER.index(color)

        h0_dates = spread_weekday_dates(year, month, wd, h0_weekday_count,
                                         salt=color_month_salt(year, month, f"h0-{color}"),
                                         phase_bias=bias)

        # H00 siempre limpio y sin restricción de horario/zona variable
        h00_por_color[color] = {"dia_base": dia, "horario": [5, 22], "zona": "total",
                                 "fechas_restriccion": [], "sabados": []}
        # H0: contingencia — siempre total + 5-22
        h0_por_color[color]  = {"dia_base": dia, "horario": [5, 22], "zona": "total",
                                 "fechas_restriccion": h0_dates, "sabados": []}
        # H1: zona y hora decididas por el AG (uniforme para todos los colores)
        h1_por_color[color]  = {"dia_base": dia, "sabados": sat_list(ts, h1_sab),
                                 "horario": [5, h1_hora], "zona": h1_zona}

        # H2: zona y hora decididas por el AG por color
        h2_hora_c = h2_hora_map.get(color, 22)
        h2_zona_c = _to_lower_zona(h2_zona_map.get(color, "Total"))
        h2_item: Dict[str, Any] = {"dia_base": dia, "sabados": sat_list(ts, h2_sab),
                                    "horario": [5, h2_hora_c], "zona": h2_zona_c}
        if h2_total:
            # restriccion_total → siempre total + 5-22 (define "restricción total")
            # fechas_restriccion solo aparece si hay extras (máx 2 días adicionales)
            h2_item.update({
                "restriccion_total": True,
                "sabados": sat_list(ts, ts),
                "horario": [5, 22],
                "zona":    "total",
            })
        if extras_per_color > 0:
            # fechas_restriccion = los días extra fuera del patrón base (máx 2)
            h2_item["fechas_restriccion"] = spread_weekday_dates(
                year, month, (wd + 1) % 5, extras_per_color,
                salt=color_month_salt(year, month, color), phase_bias=bias,
            )
        h2_por_color[color] = h2_item

    # Normalizar fechas_restriccion de H2: asegura que no caigan en el día base
    if extras_per_color > 0:
        for color in COLOR_ORDER:
            dia   = color_to_day_lower.get(color, dia_base_por_defecto(color))
            wd    = WEEKDAY_INDEX[dia]
            bias  = COLOR_ORDER.index(color)
            salt  = color_month_salt(year, month, color)
            cfg_c = h2_por_color[color]

            candidatos = list(cfg_c.get("fechas_restriccion", []))
            if len(candidatos) < extras_per_color:
                candidatos = (candidatos + spread_weekday_dates(
                    year, month, (wd + 1) % 5, extras_per_color, salt=salt, phase_bias=bias,
                ))[:extras_per_color]

            # Filtrar: los extras no deben coincidir con el día base del color
            filtradas = [
                iso for iso in candidatos
                if _LOWER[date(*(int(x) for x in iso.split("-"))).weekday()] != dia
            ]
            while len(filtradas) < extras_per_color:
                for c in all_weekday_dates(year, month, (wd + 1) % 5):
                    if c not in filtradas:
                        filtradas.append(c)
                    if len(filtradas) >= extras_per_color:
                        break

            # Máximo 2 fechas extra en H2
            cfg_c["fechas_restriccion"] = filtradas[:min(extras_per_color, 2)]

    return {
        "mes": month, "year": year, "contaminacion": contaminacion,
        "h00": {"por_color": h00_por_color},
        "h0":  {"por_color": h0_por_color},
        "h1":  {"por_color": h1_por_color},
        "h2":  {"por_color": h2_por_color},
    }


# ============================================================================
# DECODIFICACIÓN DEL ADN
# ============================================================================
def generar_individuo() -> List[float]:
    return [random.random() for _ in range(GENES)]

def decodificar_individuo(
    individuo: List[float],
    total_sabados_mes: int = 4,
    nivel_imeca: float = 150.0,
) -> Dict[str, Any]:
    """Decodifica el cromosoma en decisiones concretas de restricción."""
    r_h00, r_h0, r_h1, r_h2 = sorted(float(g) for g in individuo[0:4])
    ts = total_sabados_mes

    hora_fin_h1   = 16 if individuo[4] > 0.85 else 22
    n_16h_h2      = min(5, int(individuo[5] * 6))
    zona_h1       = "Centro" if individuo[6] > 0.82 else "Total"
    n_cen_h2      = min(5, int(individuo[7] * 6))
    sabados_h1    = min(ts, int(individuo[8] * (ts + 1)))
    rango_h2      = max(0, ts - 3)
    sabados_h2    = max(3, min(ts, 3 + min(rango_h2, int(individuo[9] * (rango_h2 + 1)))))
    dias_extra_h2 = min(2, int((individuo[10] if len(individuo) > 10 else 0.0) * 3))

    h0_wd_max, h0_sat_max = h0_limits_from_imeca(nivel_imeca)
    h0_weekday_count  = min(h0_wd_max,  int(individuo[0] * (h0_wd_max + 1)))
    h0_saturday_count = min(h0_sat_max, int(individuo[1] * (h0_sat_max + 1)))

    propuesta = {
        color: _LOWER[min(4, int(float(individuo[11 + idx]) * 5.0))]
        for idx, color in enumerate(COLOR_ORDER)
    }
    repetidos           = len(propuesta.values()) - len(set(propuesta.values()))
    asignacion_reparada = reparar_asignacion_colores_dias(propuesta)

    colors_asc        = [c for c, _ in sorted([(COLOR_ORDER[i], individuo[11 + i]) for i in range(5)], key=lambda x: x[1])]
    h2_hora_por_color = {c: (16 if i < n_16h_h2 else 22)          for i, c in enumerate(colors_asc)}
    h2_zona_por_color = {c: ("Centro" if i < n_cen_h2 else "Total") for i, c in enumerate(colors_asc)}

    cov_h2_avg = sum(
        (1.0 if h2_zona_por_color[c] == "Total" else 0.5) *
        (1.0 if h2_hora_por_color[c] == 22 else 11.0 / 17.0)
        for c in COLOR_ORDER
    ) / 5.0

    return {
        "R_H00": r_h00, "R_H0": r_h0, "R_H1": r_h1, "R_H2": r_h2,
        "color_dia_propuesta": propuesta,
        "color_dia_final":     asignacion_reparada,
        "violaciones_pre_reparacion": {"dias_repetidos": max(0, repetidos)},
        "h2_hora_por_color": h2_hora_por_color,
        "h2_zona_por_color": h2_zona_por_color,
        "cov_h2_avg":        cov_h2_avg,
        "decisiones_ag": {
            "hora_fin_h1": hora_fin_h1, "zona_h1": zona_h1,
            "sabados_h1": sabados_h1, "sabados_h2": sabados_h2,
            "dias_extra_h2": dias_extra_h2,
            "h0_weekday_count": h0_weekday_count, "h0_saturday_count": h0_saturday_count,
            "h0_weekday_max": h0_wd_max, "h0_saturday_max": h0_sat_max,
            "h2_hora_por_color": h2_hora_por_color,
            "h2_zona_por_color": h2_zona_por_color,
            "n_16h_h2": n_16h_h2, "n_cen_h2": n_cen_h2,
        },
    }


# ============================================================================
# FUNCIÓN DE FITNESS
# ============================================================================
def funcion_objetivo(
    individuo: List[float],
    factor_mensual: float,
    factor_sabado: float = 1.0,
    total_sabados: int = 4,
    nivel_imeca: float = 150.0,
) -> float:
    """
    Evalúa el cromosoma con el contexto real del mes.

    beneficio = nivel_restriccion × factor_mensual  → sube con contaminación
    costo     = cuadrático                          → penaliza el exceso
    factor_costo mayor cuando contaminación baja    → inhibir restricciones innecesarias
    """
    sol  = decodificar_individuo(individuo, total_sabados, nivel_imeca)
    d_ag = sol["decisiones_ag"]

    sab_h1, sab_h2, extras = d_ag["sabados_h1"], d_ag["sabados_h2"], d_ag["dias_extra_h2"]
    h0_weekdays  = d_ag.get("h0_weekday_count", 0)
    h0_sats      = d_ag.get("h0_saturday_count", 0)
    h0_wd_max    = max(1, d_ag.get("h0_weekday_max", 0))
    h0_sat_max   = max(1, d_ag.get("h0_saturday_max", 0))

    zf_h1  = 1.0 if "otal" in str(d_ag.get("zona_h1", "Total")) else 0.5
    hf_h1  = 1.0 if int(d_ag.get("hora_fin_h1", 22)) == 22 else 11.0 / 17.0
    cov_h1 = zf_h1 * hf_h1
    cov_h2 = sol.get("cov_h2_avg", 1.0)

    h2_extra_sats = sab_h2 - 3
    h2_max_extra  = max(1, total_sabados - 3)
    h1_max_sats   = max(1, total_sabados)

    W_H0_WD, W_H0_SAT, W_H1, W_H2, W_EX = 0.07, 0.04, 0.28, 0.32, 0.29
    nivel_restriccion = (
          (h0_weekdays   / h0_wd_max)    * W_H0_WD
        + (h0_sats       / h0_sat_max)   * W_H0_SAT
        + (sab_h1        / h1_max_sats)  * W_H1 * cov_h1
        + (h2_extra_sats / h2_max_extra) * W_H2 * cov_h2
        + (extras        / 2.0)          * W_EX * cov_h2
    )
    beneficio = nivel_restriccion * factor_mensual * 2.5

    costo = (
          (h0_weekdays   ** 1.3) * 0.14
        + (h0_sats       ** 1.3) * 0.18
        + (sab_h1        ** 1.5) * 0.08 * cov_h1
        + (h2_extra_sats ** 1.5) * 0.40 * cov_h2
        + (extras        ** 1.5) * 0.35 * cov_h2
    ) * (1.0 + (factor_sabado - 1.0) * 0.40)

    factor_costo  = 2.0 - clamp01(factor_mensual / 1.8)
    factor_alivio = max(0.0, 1.0 - clamp01(factor_mensual / 1.8)) ** 2

    MAX_LIGHTER = 1.0 - 0.5 * 11.0 / 17.0
    lighter     = clamp01((1.0 - cov_h2) / MAX_LIGHTER)
    alivio_h2   = factor_alivio * 4.0 * lighter * (1.0 - lighter) * 0.35
    alivio_h1   = factor_alivio * (1.0 - cov_h1) * 0.28
    beneficio_alivio = (alivio_h1 + alivio_h2) * 2.5

    fitness = (beneficio + beneficio_alivio - costo * factor_costo) * 1000.0

    dias_repetidos = int(sol.get("violaciones_pre_reparacion", {}).get("dias_repetidos", 0))
    if dias_repetidos:
        fitness -= 500.0 * dias_repetidos
    return float(fitness)


def aptitud(individuo, factor_mensual, factor_sabado=1.0, total_sabados=4, nivel_imeca=150.0) -> float:
    return funcion_objetivo(individuo, factor_mensual, factor_sabado, total_sabados, nivel_imeca)


# ============================================================================
# OPERADORES GENÉTICOS
# ============================================================================
def seleccionar_padre_ruleta(poblacion: List[List[float]], aptitudes: List[float]) -> List[float]:
    minimo    = min(aptitudes)
    offset    = abs(minimo) + 1e-9 if minimo < 0 else 0.0
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

def cruza_un_punto(p1: List[float], p2: List[float], prob: float) -> Tuple[List[float], List[float]]:
    if random.random() >= prob:
        return p1[:], p2[:]
    punto = random.randint(1, GENES - 1)
    return p1[:punto] + p2[punto:], p2[:punto] + p1[punto:]

def mutar(individuo: List[float], prob: float) -> List[float]:
    return [clamp01(g + random.uniform(-0.1, 0.1)) if random.random() < prob else g for g in individuo]

def poda(poblacion, factor_mensual, factor_sabado, total_sabados, tam, nivel_imeca) -> List[List[float]]:
    return [ind[:] for ind in sorted(
        poblacion,
        key=lambda i: aptitud(i, factor_mensual, factor_sabado, total_sabados, nivel_imeca),
        reverse=True
    )[:tam]]


# ============================================================================
# MOTOR EVOLUTIVO
# ============================================================================
def ejecutar_algoritmo_genetico(
    factor_mensual: float,
    factor_sabado: float = 1.0,
    total_sabados: int = 4,
    nivel_imeca: float = 150.0,
    pop_size: int = DEFAULT_POP_SIZE,
    generaciones: int = DEFAULT_GENERATIONS,
    prob_cruza: float = 0.85,
    prob_mutacion: float = 0.05,
    elitismo: int = 2,
) -> Dict[str, Any]:
    poblacion  = [generar_individuo() for _ in range(pop_size)]
    best_fit   = -math.inf
    best_ind: List[float] = []
    historial: List[float] = []

    for _ in range(generaciones):
        aptitudes_lista = [aptitud(ind, factor_mensual, factor_sabado, total_sabados, nivel_imeca)
                           for ind in poblacion]
        ranking = sorted(zip(poblacion, aptitudes_lista), key=lambda x: x[1], reverse=True)
        mejor_ind_gen, mejor_fit_gen = ranking[0]
        historial.append(float(mejor_fit_gen))
        if mejor_fit_gen > best_fit:
            best_fit, best_ind = float(mejor_fit_gen), mejor_ind_gen[:]

        nueva = [ind[:] for ind, _ in ranking[:max(1, elitismo)]]
        while len(nueva) < pop_size:
            h1, h2 = cruza_un_punto(
                seleccionar_padre_ruleta(poblacion, aptitudes_lista),
                seleccionar_padre_ruleta(poblacion, aptitudes_lista),
                prob_cruza,
            )
            nueva.append(mutar(h1, prob_mutacion))
            if len(nueva) < pop_size:
                nueva.append(mutar(h2, prob_mutacion))
        poblacion = poda(nueva, factor_mensual, factor_sabado, total_sabados, pop_size, nivel_imeca)

    return {"mejor_fitness": float(best_fit), "mejor_individuo": best_ind, "historial_fitness": historial}


def evolucionar(factor_mensual: float, params: Optional[Dict[str, Any]] = None,
                total_sabados: int = 4, nivel_imeca: float = 150.0) -> Dict[str, Any]:
    """Wrapper de compatibilidad."""
    cfg     = params or {}
    entorno = cargar_entorno_cdmx()
    return ejecutar_algoritmo_genetico(
        factor_mensual=factor_mensual,
        factor_sabado=resumen_probabilidad_sabado(entorno),
        total_sabados=total_sabados,
        nivel_imeca=nivel_imeca,
        pop_size=int(cfg.get("pop_size", DEFAULT_POP_SIZE)),
        generaciones=int(cfg.get("generaciones", DEFAULT_GENERATIONS)),
        prob_cruza=0.85,
        prob_mutacion=float(cfg.get("mutacion", 0.05)),
        elitismo=int(cfg.get("elitismo", 2)),
    )


# ============================================================================
# GENERACIÓN DEL JSON FINAL
# ============================================================================
def generar_json_final(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Genera el calendario óptimo de restricciones HNC.
    El AG se ejecuta de forma independiente para cada mes usando su nivel
    de contaminación real. Las asignaciones color→día se diversifican por mes.
    """
    merged        = {**DEFAULT_PARAMS, **(params or {})}
    entorno       = cargar_entorno_cdmx()
    factor_sabado = resumen_probabilidad_sabado(entorno)

    start_year, start_month = parse_year_month(str(merged["start_month"]))
    meses_count   = max(1, int(merged["meses"]))
    nivel_imeca   = float(merged["nivel_imeca"])
    pop_size      = int(merged["pop_size"])
    generaciones  = int(merged["generaciones"])
    prob_mutacion = float(merged["mutacion"])
    elitismo      = int(merged["elitismo"])

    meses_out: List[Dict[str, Any]] = []
    fitness_acumulado: List[float] = []
    used_color_day_tuples: set = set()

    for i in range(meses_count):
        year_i, month_i = add_months(start_year, start_month, i)
        total_sab_i     = total_saturdays(year_i, month_i)
        contaminacion_i = contamination_for_month(month_i, nivel_imeca)
        factor_i        = contamination_to_factor(contaminacion_i)

        ag_result = ejecutar_algoritmo_genetico(
            factor_mensual=factor_i, factor_sabado=factor_sabado,
            total_sabados=total_sab_i, nivel_imeca=nivel_imeca,
            pop_size=pop_size, generaciones=generaciones,
            prob_cruza=0.85, prob_mutacion=prob_mutacion, elitismo=elitismo,
        )
        fitness_acumulado.append(ag_result["mejor_fitness"])
        mejor_ind    = ag_result["mejor_individuo"]
        decoded      = decodificar_individuo(mejor_ind, total_sab_i, nivel_imeca)
        color_to_day = decoded["color_dia_final"]

        # Garantiza diversidad de rotaciones entre meses
        color_tuple = tuple(color_to_day[c] for c in COLOR_ORDER)
        if color_tuple in used_color_day_tuples:
            alts = generar_asignaciones_mensuales_desde_base(
                color_to_day, 2, year_i * 1000 + month_i
            )
            color_to_day = alts[1] if len(alts) > 1 else color_to_day
            color_tuple  = tuple(color_to_day[c] for c in COLOR_ORDER)
        used_color_day_tuples.add(color_tuple)

        meses_out.append(construir_reglas_mes(
            year_i, month_i, contaminacion_i, color_to_day,
            ag_decisions=decoded["decisiones_ag"],
            nivel_imeca=nivel_imeca,
        ))

    resultado = {
        "timestamp": str(date.today()),
        "parametros": {k: merged[k] for k in [
            "pop_size", "generaciones", "mutacion", "elitismo",
            "peso_equidad", "peso_ambiental_critico", "peso_economico",
            "nivel_imeca", "start_month", "meses",
        ]},
        "contexto_entorno": {"factor_sabado": factor_sabado, "usa_entorno_etl": bool(entorno)},
        "mejor_fitness": sum(fitness_acumulado) / len(fitness_acumulado) if fitness_acumulado else 0.0,
        "mejor_solucion": {"meses": meses_out},
    }

    RESULTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTADO_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=4)

    return resultado


if __name__ == "__main__":
    resultado = generar_json_final()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
