import json
import itertools
import heapq
import math
import random
from calendar import monthcalendar, monthrange
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GENES            = 16
DEFAULT_POP_SIZE = 100
DEFAULT_GENERATIONS = 120

DEFAULT_PARAMS = {
    "pop_size": 100, "generaciones": 120, "mutacion": 0.05, "elitismo": 1,
    "peso_equidad": 1, "peso_ambiental_critico": 2.2, "peso_economico": 1.55,
    "nivel_imeca": 150, "start_month": "2026-04", "meses": 6,
    "prob_cruza": 0.60,
    "estrategia_seleccion": "ruleta",
    "estrategia_cruza":     "uniforme",
    "estrategia_mutacion":  "uniforme",
}

GRUPOS_PLACA = {"Amarillo": [5, 6], "Rosa": [7, 8], "Rojo": [3, 4], "Verde": [1, 2], "Azul": [9, 0]}
HOLOGRAMAS   = ["H00", "H0", "H1", "H2"]
COLOR_ORDER  = ["Verde", "Amarillo", "Rosa", "Rojo", "Azul"]

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes"]
WEEKDAY_INDEX = {d: i for i, d in enumerate(DIAS_SEMANA)}
DIA_BASE_POR_COLOR = dict(zip(COLOR_ORDER, DIAS_SEMANA))

CONTAMINATION_FACTORS: Dict[str, float] = {
    "buena": 0.35, "aceptable": 0.90, "mala": 1.45, "muy_mala": 2.21, "extrema": 2.90,
}

IMECA_LEVELS = ["buena", "aceptable", "mala", "muy_mala", "extrema"]


def imeca_level_index(nivel_imeca: float) -> int:
    i = float(nivel_imeca)
    if i <= 50:
        return 0
    if i <= 100:
        return 1
    if i <= 150:
        return 2
    if i <= 200:
        return 3
    return 4

def h1_ladder_range(total_sabados: int, nivel_imeca: float) -> Tuple[int, int]:
    lvl = imeca_level_index(nivel_imeca)
    if total_sabados >= 5:
        ranges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    else:
        ranges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 4)]
    lo, hi = ranges[min(lvl, len(ranges) - 1)]
    hi = min(hi, total_sabados)
    lo = min(lo, hi)
    return lo, hi


def h2_ladder_target(total_sabados: int, nivel_imeca: float) -> Tuple[int, int]:
    lvl = imeca_level_index(nivel_imeca)
    if total_sabados >= 5:
        ladder = [(3, 0), (4, 0), (5, 0), (5, 1), (5, 2)]
    else:
        ladder = [(3, 0), (4, 0), (4, 1), (4, 2), (4, 2)]
    sab, extra = ladder[min(lvl, len(ladder) - 1)]
    return min(total_sabados, sab), max(0, min(2, extra))


def h2_ladder_distance(total_sabados: int, nivel_imeca: float, h2_sab: int, h2_extra: int) -> float:
    target_sab, target_extra = h2_ladder_target(total_sabados, nivel_imeca)
    ds = abs(float(h2_sab - target_sab)) / max(1.0, float(total_sabados))
    de = abs(float(h2_extra - target_extra)) / 2.0
    return ds + de

_CCONFIG: Dict[str, Any] = {
    "buena":    {"h0_wd_max": 0, "h1_light_max": 2, "h2_light_max": 3},
    "aceptable":{"h0_wd_max": 0, "h1_light_max": 2, "h2_light_max": 3},
    "mala":     {"h0_wd_max": 0, "h1_light_max": 1, "h2_light_max": 2},
    "muy_mala": {"h0_wd_max": 1, "h1_light_max": 1, "h2_light_max": 1},
    "extrema":  {"h0_wd_max": 2, "h1_light_max": 0, "h2_light_max": 0},
}

PROJECT_ROOT   = Path(__file__).resolve().parent.parent
ENTORNO_PATH   = PROJECT_ROOT / "data" / "entorno_cdmx.json"
RESULTADO_PATH = PROJECT_ROOT / "data" / "resultado_ag_hnc.json"
EPSILON        = 1e-6


def contamination_to_factor(c: str) -> float:
    return CONTAMINATION_FACTORS.get(c, 1.0)

def dia_base_por_defecto(color: str) -> str:
    return DIA_BASE_POR_COLOR.get(color, DIAS_SEMANA[0])

def gene_value_for_weekday(dia_lower: str) -> float:
    """Mapea un día válido a un valor de gen que decodifica de forma estable a ese día."""
    idx = WEEKDAY_INDEX.get(dia_lower, 0)
    return (idx + 0.5) / 5.0

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

def all_weekday_dates(year: int, month: int, weekday: int) -> List[str]:
    if not 0 <= weekday <= 6:
        return []
    return [
        date(year, month, day_num).isoformat()
        for week in monthcalendar(year, month)
        for day_num in [week[weekday]] if day_num
    ]

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
    return IMECA_LEVELS[imeca_level_index(nivel_imeca)]

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


def obtener_factor_mensual(entorno: Dict[str, Any], year: int, month: int) -> float:
    ajustes = entorno.get("ajustes_mensuales", {}) if isinstance(entorno, dict) else {}
    if not isinstance(ajustes, dict) or not ajustes:
        return 1.0
    ajuste = ajustes.get(f"{month:02d}", {})
    if not isinstance(ajuste, dict):
        return 1.0
    valor = ajuste.get("factor_contaminacion", 1.0)
    try:
        return max(0.80, min(1.35, float(valor)))
    except Exception:
        return 1.0

def reparar_asignacion_colores_dias(propuesta: Dict[str, str]) -> Dict[str, str]:
    usados, resultado, disponibles = set(), {}, set(DIAS_SEMANA)
    for color in COLOR_ORDER:
        dia = propuesta.get(color, dia_base_por_defecto(color))
        if dia not in DIAS_SEMANA:
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
    dias       = DIAS_SEMANA[:]
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


def construir_reglas_mes(
    year: int, month: int, contaminacion: str,
    color_to_day_lower: Dict[str, str],
    ag_decisions: Optional[Dict[str, Any]] = None,
    nivel_imeca: float = 150.0,
) -> Dict[str, Any]:
    def _normalizar_ligeras(d_ag: Dict[str, Any]) -> Dict[str, Any]:
        """Resuelve cuántos colores aplican horario/zona reducida según el nivel de contaminación."""
        cfg_l = _CCONFIG.get(contaminacion, _CCONFIG["extrema"])
        h1_cap, h2_cap = int(cfg_l.get("h1_light_max", 0)), int(cfg_l.get("h2_light_max", 0))
        def clean(raw: Any) -> List[str]:
            cl = [c for c in raw if c in COLOR_ORDER] if isinstance(raw, list) else []
            return cl if len(cl) == len(COLOR_ORDER) else COLOR_ORDER[:]
        o1 = clean(d_ag.get("orden_prioridad_ligero_h1", COLOR_ORDER))
        o2 = clean(d_ag.get("orden_prioridad_ligero_h2", COLOR_ORDER))
        a1 = min(h1_cap, max(0, min(5, int(d_ag.get("n_light_h1", 0)))))
        a2 = min(h2_cap, max(0, min(5, int(d_ag.get("n_light_h2", 0)))))
        s1, s2 = set(o1[:a1]), set(o2[:a2])
        return {
            "h1_hora_por_color": {c: (16 if c in s1 else 22) for c in COLOR_ORDER},
            "h1_zona_por_color": {c: ("Centro" if c in s1 else "Total") for c in COLOR_ORDER},
            "h2_hora_por_color": {c: (16 if c in s2 else 22) for c in COLOR_ORDER},
            "h2_zona_por_color": {c: ("Centro" if c in s2 else "Total") for c in COLOR_ORDER},
        }

    ts  = total_saturdays(year, month)
    cfg = _CCONFIG.get(contaminacion, _CCONFIG["extrema"])
    h1_lo, h1_hi = h1_ladder_range(ts, nivel_imeca)
    h2_target_sab, h2_target_extra = h2_ladder_target(ts, nivel_imeca)

    h0_wd_max = cfg["h0_wd_max"]

    if ag_decisions:
        ag_h1 = int(ag_decisions.get("sabados_h1", h1_hi))
        ag_h0 = int(ag_decisions.get("h0_weekday_count", h0_wd_max))
    else:
        ag_h1, ag_h0 = h1_hi, h0_wd_max

    h1_sab           = min(h1_hi, max(h1_lo, ag_h1))
    # Se prioriza la escalera H2 por severidad; el AG sigue libre durante la optimización.
    h2_sab           = max(3, min(ts, h2_target_sab))
    extras_per_color = max(0, min(2, h2_target_extra))
    h0_weekday_count = min(h0_wd_max, h0_limits_from_imeca(nivel_imeca)[0], ag_h0)

    if ag_decisions:
        norm_light = _normalizar_ligeras(ag_decisions)
        h1_hora_map: Dict[str, int] = norm_light["h1_hora_por_color"]
        h1_zona_map: Dict[str, str] = norm_light["h1_zona_por_color"]
        h2_hora_map: Dict[str, int] = norm_light["h2_hora_por_color"]
        h2_zona_map: Dict[str, str] = norm_light["h2_zona_por_color"]
    else:
        h1_hora_map = {c: 22 for c in COLOR_ORDER}
        h1_zona_map = {c: "Total" for c in COLOR_ORDER}
        h2_hora_map = {c: 22 for c in COLOR_ORDER}
        h2_zona_map = {c: "Total" for c in COLOR_ORDER}

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

        h00_por_color[color] = {"dia_base": dia, "horario": [5, 22], "zona": "total",
                                 "fechas_restriccion": [], "sabados": []}
        h0_por_color[color]  = {"dia_base": dia, "horario": [5, 22], "zona": "total",
                                 "fechas_restriccion": h0_dates, "sabados": []}
        h1_por_color[color]  = {"dia_base": dia, "sabados": sat_list(ts, h1_sab),
                     "horario": [5, int(h1_hora_map.get(color, 22))],
                     "zona": "centro" if "entro" in str(h1_zona_map.get(color, "Total")) else "total"}

        h2_hora_c = h2_hora_map.get(color, 22)
        h2_zona_c = "centro" if "entro" in str(h2_zona_map.get(color, "Total")) else "total"
        h2_item: Dict[str, Any] = {"dia_base": dia, "sabados": sat_list(ts, h2_sab),
                                    "horario": [5, h2_hora_c], "zona": h2_zona_c}
        if extras_per_color > 0:
            h2_item["fechas_restriccion"] = spread_weekday_dates(
                year, month, (wd + 1) % 5, extras_per_color,
                salt=color_month_salt(year, month, color), phase_bias=bias,
            )
        h2_por_color[color] = h2_item

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

            filtradas = [
                iso for iso in candidatos
                if DIAS_SEMANA[date(*(int(x) for x in iso.split("-"))).weekday()] != dia
            ]
            while len(filtradas) < extras_per_color:
                for c in all_weekday_dates(year, month, (wd + 1) % 5):
                    if c not in filtradas:
                        filtradas.append(c)
                    if len(filtradas) >= extras_per_color:
                        break

            cfg_c["fechas_restriccion"] = filtradas[:min(extras_per_color, 2)]

    return {
        "mes": month, "year": year, "contaminacion": contaminacion,
        "h00": {"por_color": h00_por_color},
        "h0":  {"por_color": h0_por_color},
        "h1":  {"por_color": h1_por_color},
        "h2":  {"por_color": h2_por_color},
    }


def decodificar_individuo(
    individuo: List[float],
    total_sabados_mes: int = 4,
    nivel_imeca: float = 150.0,
) -> Dict[str, Any]:
    """Decodifica el cromosoma en decisiones concretas de restricción (Lamarckiano)."""
    def _cov(hora: Dict[str, int], zona: Dict[str, str]) -> float:
        """Cobertura promedio: zona total=1.0/centro=0.5 × horario 5-22=1.0/5-16=11/17."""
        return sum(
            (1.0 if "entro" not in str(zona.get(c, "Total")) else 0.5) *
            (1.0 if int(hora.get(c, 22)) == 22 else 11.0 / 17.0)
            for c in COLOR_ORDER
        ) / len(COLOR_ORDER)

    r_h00, r_h0, r_h1, r_h2 = sorted(float(g) for g in individuo[0:4])
    ts = total_sabados_mes

    n_light_h1    = min(5, int(individuo[4] * 6))
    n_light_h2    = min(5, int(individuo[5] * 6))
    phase_h1      = min(4, int(individuo[6] * 5))
    phase_h2      = min(4, int(individuo[7] * 5))
    sabados_h1    = min(ts, int(individuo[8] * (ts + 1)))
    sabados_h2    = min(ts, int(individuo[9] * (ts + 1)))
    dias_extra_h2 = min(4, int((individuo[10] if len(individuo) > 10 else 0.0) * 5))

    h0_wd_max, h0_sat_max = h0_limits_from_imeca(nivel_imeca)
    h0_weekday_count  = min(h0_wd_max,  int(individuo[0] * (h0_wd_max + 1)))
    h0_saturday_count = min(h0_sat_max, int(individuo[1] * (h0_sat_max + 1)))

    propuesta = {
        color: DIAS_SEMANA[min(4, int(float(individuo[11 + idx]) * 5.0))]
        for idx, color in enumerate(COLOR_ORDER)
    }
    repetidos           = len(propuesta.values()) - len(set(propuesta.values()))
    asignacion_reparada = reparar_asignacion_colores_dias(propuesta)

    for idx, color in enumerate(COLOR_ORDER):
        individuo[11 + idx] = gene_value_for_weekday(asignacion_reparada[color])

    colors_asc = [c for c, _ in sorted([(COLOR_ORDER[i], individuo[11 + i]) for i in range(5)], key=lambda x: x[1])]
    k1 = phase_h1 % len(colors_asc); prio_h1 = colors_asc[k1:] + colors_asc[:k1]
    k2 = phase_h2 % len(colors_asc); prio_h2 = colors_asc[k2:] + colors_asc[:k2]

    h1_hora_por_color = {c: (16 if i < n_light_h1 else 22) for i, c in enumerate(prio_h1)}
    h1_zona_por_color = {c: ("Centro" if i < n_light_h1 else "Total") for i, c in enumerate(prio_h1)}
    h2_hora_por_color = {c: (16 if i < n_light_h2 else 22) for i, c in enumerate(prio_h2)}
    h2_zona_por_color = {c: ("Centro" if i < n_light_h2 else "Total") for i, c in enumerate(prio_h2)}

    cov_h1_avg = _cov(h1_hora_por_color, h1_zona_por_color)
    cov_h2_avg = _cov(h2_hora_por_color, h2_zona_por_color)

    return {
        "R_H00": r_h00, "R_H0": r_h0, "R_H1": r_h1, "R_H2": r_h2,
        "color_dia_propuesta": propuesta,
        "color_dia_final":     asignacion_reparada,
        "violaciones_pre_reparacion": {"dias_repetidos": max(0, repetidos)},
        "h2_hora_por_color": h2_hora_por_color,
        "h2_zona_por_color": h2_zona_por_color,
        "cov_h2_avg":        cov_h2_avg,
        "h1_hora_por_color": h1_hora_por_color,
        "h1_zona_por_color": h1_zona_por_color,
        "cov_h1_avg":        cov_h1_avg,
        "decisiones_ag": {
            "hora_fin_h1": 16 if n_light_h1 >= 3 else 22,
            "zona_h1": "Centro" if n_light_h1 >= 3 else "Total",
            "sabados_h1": sabados_h1, "sabados_h2": sabados_h2,
            "dias_extra_h2": dias_extra_h2,
            "h0_weekday_count": h0_weekday_count, "h0_saturday_count": h0_saturday_count,
            "h0_weekday_max": h0_wd_max, "h0_saturday_max": h0_sat_max,
            "h1_hora_por_color": h1_hora_por_color,
            "h1_zona_por_color": h1_zona_por_color,
            "h2_hora_por_color": h2_hora_por_color,
            "h2_zona_por_color": h2_zona_por_color,
            "n_light_h1": n_light_h1, "n_light_h2": n_light_h2,
            "orden_prioridad_ligero_h1": prio_h1,
            "orden_prioridad_ligero_h2": prio_h2,
            "phase_h1": phase_h1, "phase_h2": phase_h2,
        },
    }



# §1.4.2
def FuncionInicializacion(pop_size: int) -> List[List[float]]:
    return [[random.random() for _ in range(GENES)] for _ in range(pop_size)]


# §1.4.1
def FuncionAptitud(
    individuo: List[float],
    entorno: Dict[str, Any],
    total_sabados: int,
    nivel_imeca: float,
    factor_mensual: float = 1.0,
    peso_ambiental: float = 2.2,
    peso_economico: float = 1.55,
    peso_equidad: float = 1.0,
) -> float:
    sol  = decodificar_individuo(individuo, total_sabados, nivel_imeca)
    d_ag = sol["decisiones_ag"]
    d_ag["cov_h1_avg"] = sol.get("cov_h1_avg", 1.0)
    d_ag["cov_h2_avg"] = sol.get("cov_h2_avg", 1.0)

    dias_mes  = 30
    cum       = float(entorno.get("cumplimiento_ciudadano", 0.85))
    h0_wd     = int(d_ag.get("h0_weekday_count", 0))
    h1_sabs   = int(d_ag.get("sabados_h1", 0))
    h2_sabs   = int(d_ag.get("sabados_h2", 0))
    h2_ex     = int(d_ag.get("dias_extra_h2", 0))
    cov_h1    = float(d_ag.get("cov_h1_avg", 1.0))
    cov_h2    = float(d_ag.get("cov_h2_avg", 1.0))
    dias_hab  = max(1, dias_mes - total_sabados)

    R: Dict[str, float] = {
        "H00": 0.0,
        "H0" : cum * (h0_wd / max(1, dias_mes)),
        "H1" : cum * ((dias_hab / 5 + h1_sabs) / dias_mes) * cov_h1,
        "H2" : cum * ((dias_hab / 5 + h2_sabs + h2_ex) / dias_mes) * cov_h2,
    }
    R = {k: max(0.0, min(1.0, v)) for k, v in R.items()}

    vehiculos = entorno.get("vehiculos", {})
    D         = float(entorno.get("distancia_promedio_km", 24.0))

    E = sum(
        float(v.get("total", 0)) * (1.0 - R.get(h, 0.0))
        * float(v.get("ef", 1.0)) * D
        for h, v in vehiculos.items()
    ) or EPSILON

    IE = sum(
        R.get(h, 0.0) * float(v.get("total", 0))
        * float(v.get("p_l", 0.3)) * float(v.get("costo", 1.0))
        for h, v in vehiculos.items()
    ) or EPSILON


    eq = max(0.0, float(peso_equidad))
    tasa_h2 = R.get("H2", 0.0)
    tasa_h1 = R.get("H1", 0.0)

    factor_mensual = max(0.80, float(factor_mensual))
    nivel_imeca_efectivo = max(0.0, float(nivel_imeca) * factor_mensual)
    tolerancia_ambiental = max(0.0, min(1.0, (250.0 - nivel_imeca_efectivo) / 200.0))

    penal_h2 = (tasa_h2 ** 2.5) * 15.0 * eq * tolerancia_ambiental
    penal_extra = (h2_ex ** 2.0) * 0.8 * eq * (tolerancia_ambiental ** 0.5)
    penal_h1 = (tasa_h1 ** 2.0) * 4.0 * eq * tolerancia_ambiental

    h1_lo, h1_hi = h1_ladder_range(total_sabados, nivel_imeca_efectivo)
    if h1_sabs < h1_lo:
        h1_gap = (h1_lo - h1_sabs) / max(1.0, float(total_sabados))
    elif h1_sabs > h1_hi:
        h1_gap = (h1_sabs - h1_hi) / max(1.0, float(total_sabados))
    else:
        h1_gap = 0.0
    penal_h1_ladder = (h1_gap ** 2.2) * 8.5 * eq * (0.7 + 0.3 * tolerancia_ambiental)

    h2_gap = h2_ladder_distance(total_sabados, nivel_imeca_efectivo, h2_sabs, h2_ex)
    penal_h2_ladder = (h2_gap ** 2.5) * 16.0 * eq * (0.6 + 0.4 * tolerancia_ambiental)

    penalizacion_equidad = 1.0 + penal_h2 + penal_extra + penal_h1 + penal_h1_ladder + penal_h2_ladder
    IE *= penalizacion_equidad

    trafico = entorno.get("trafico", {})
    M   = sum(float(v.get("total", 0)) * (1.0 - R.get(h, 0.0)) for h, v in vehiculos.items())
    vf  = float(trafico.get("v_f",          45.0))
    C   = float(trafico.get("capacidad_c",   3_500_000))
    α   = float(trafico.get("alpha",         0.15))
    β   = float(trafico.get("beta",          4.0))
    v_bpr = vf / (1.0 + α * (M / max(C, 1.0)) ** β)

    factor_imeca = (1.0 + max(0.0, (nivel_imeca_efectivo - 100) / 100.0) * (peso_ambiental - 1.0)) * factor_mensual
    return (v_bpr / (E * factor_imeca + IE * peso_economico + EPSILON)) * 1e6


# §1.4.3
def FuncionGeneracionParejas(
    poblacion: List[List[float]],
    aptitudes: List[float],
    estrategia: str = "ruleta",
) -> List[float]:
    if estrategia == "ruleta":
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

    elif estrategia == "torneo":
        k       = 3
        indices = random.sample(range(len(poblacion)), min(k, len(poblacion)))
        ganador = max(indices, key=lambda i: aptitudes[i])
        return poblacion[ganador][:]

    elif estrategia == "ranking":
        orden = sorted(range(len(poblacion)), key=lambda i: aptitudes[i])
        pesos = list(range(1, len(poblacion) + 1))
        total = sum(pesos)
        r, acum = random.uniform(0, total), 0.0
        for pos, idx in enumerate(orden):
            acum += pesos[pos]
            if acum >= r:
                return poblacion[idx][:]
        return poblacion[orden[-1]][:]

    return random.choice(poblacion)[:]


# §1.4.4
def FuncionCruza(
    padre1: List[float],
    padre2: List[float],
    prob_cruza: float = 0.60,
    estrategia: str   = "uniforme",
) -> Tuple[List[float], List[float]]:
    if random.random() >= prob_cruza:
        return padre1[:], padre2[:]

    if estrategia == "un_punto":
        p    = random.randint(1, GENES - 1)
        h1   = padre1[:p] + padre2[p:]
        h2   = padre2[:p] + padre1[p:]

    elif estrategia == "dos_puntos":
        a, b = sorted(random.sample(range(1, GENES), 2))
        h1   = padre1[:a] + padre2[a:b] + padre1[b:]
        h2   = padre2[:a] + padre1[a:b] + padre2[b:]

    else:
        h1 = [padre2[i] if random.random() < 0.5 else padre1[i] for i in range(GENES)]
        h2 = [padre1[i] if h1[i] == padre2[i]   else padre2[i]  for i in range(GENES)]

    return h1, h2


# §1.4.5
def FuncionMutacion(
    individuo: List[float],
    prob_mutacion: float = 0.10,
    estrategia: str      = "gaussiana",
) -> List[float]:
    mutado = individuo[:]
    for i in range(GENES):
        if random.random() < prob_mutacion:
            if estrategia == "uniforme":
                mutado[i] = clamp01(individuo[i] + random.uniform(-0.1, 0.1))
            elif estrategia == "gaussiana":
                mutado[i] = clamp01(individuo[i] + random.gauss(0, 0.08))
            else:
                mutado[i] = random.random()
    return mutado


# §1.4.6
def FuncionPoda(
    poblacion: List[List[float]],
    aptitudes: List[float],
    tam_objetivo: int,
    elitismo: int = 1,
) -> Tuple[List[List[float]], float]:
    ranking     = sorted(zip(poblacion, aptitudes), key=lambda x: x[1], reverse=True)
    nueva_gen   = [ind[:] for ind, _ in ranking[:tam_objetivo]]

    diversidad = 0.0
    if len(nueva_gen) >= 2:
        for g in range(GENES):
            vals   = [ind[g] for ind in nueva_gen]
            media  = sum(vals) / len(vals)
            var    = sum((v - media) ** 2 for v in vals) / len(vals)
            diversidad += var ** 0.5
        diversidad /= GENES

    return nueva_gen, diversidad


def ejecutar_algoritmo_genetico(
    factor_mensual: float,
    factor_sabado: float = 1.0,
    total_sabados: int = 4,
    nivel_imeca: float = 150.0,
    pop_size: int = DEFAULT_POP_SIZE,
    generaciones: int = DEFAULT_GENERATIONS,
    prob_cruza: float = 0.60,
    prob_mutacion: float = 0.05,
    elitismo: int = 2,
    estrategia_seleccion: str = "ruleta",
    estrategia_cruza: str = "un_punto",
    estrategia_mutacion: str = "uniforme",
    entorno: Optional[Dict[str, Any]] = None,
    peso_ambiental: float = 2.2,
    peso_economico: float = 1.55,
    peso_equidad: float = 1.0,
    stagnacion_umbral: int = 15,
    mutacion_max: float = 0.35,
    inyeccion_pct: float = 0.10,
    diversidad_minima: float = 0.04,
) -> Dict[str, Any]:
    env = entorno or {}

    def eval_ind(ind: List[float]) -> float:
        return FuncionAptitud(ind, env, total_sabados, nivel_imeca, factor_mensual, peso_ambiental, peso_economico, peso_equidad)

    poblacion  = FuncionInicializacion(pop_size)
    best_fit   = -math.inf
    best_ind: List[float] = []
    historial_mejor: List[float] = []
    historial_peor:  List[float] = []
    historial_prom:  List[float] = []
    historial_vars:  List[Dict[str, Any]] = []

    stagnacion_counter = 0
    prev_best          = -math.inf
    div_actual         = 1.0

    for _ in range(generaciones):
        aptitudes_lista = [eval_ind(ind) for ind in poblacion]
        mejor_idx = max(range(len(poblacion)), key=lambda i: aptitudes_lista[i])
        mejor_ind_gen = poblacion[mejor_idx]
        mejor_fit_gen = aptitudes_lista[mejor_idx]

        historial_mejor.append(float(mejor_fit_gen))
        historial_peor.append(float(min(aptitudes_lista)))
        historial_prom.append(float(sum(aptitudes_lista) / len(aptitudes_lista)))

        decoded_gen = decodificar_individuo(mejor_ind_gen, total_sabados, nivel_imeca)
        d_ag_gen    = decoded_gen["decisiones_ag"]
        historial_vars.append({
            "sabados_h1":       int(d_ag_gen.get("sabados_h1", 0)),
            "sabados_h2":       int(d_ag_gen.get("sabados_h2", 0)),
            "dias_extra_h2":    int(d_ag_gen.get("dias_extra_h2", 0)),
            "h0_weekday_count": int(d_ag_gen.get("h0_weekday_count", 0)),
            "n_light_h1":       int(d_ag_gen.get("n_light_h1", 0)),
            "n_light_h2":       int(d_ag_gen.get("n_light_h2", 0)),
        })

        if mejor_fit_gen > best_fit:
            best_fit, best_ind = float(mejor_fit_gen), mejor_ind_gen[:]

        if float(mejor_fit_gen) > prev_best + 1e-8:
            prev_best          = float(mejor_fit_gen)
            stagnacion_counter = 0
        else:
            stagnacion_counter += 1

        factor_adapt       = min(1.0, stagnacion_counter / max(1, stagnacion_umbral))
        prob_mutacion_actual = prob_mutacion + (mutacion_max - prob_mutacion) * factor_adapt

        elite_count = min(len(poblacion), max(1, elitismo))
        elite_idx = heapq.nlargest(elite_count, range(len(poblacion)), key=aptitudes_lista.__getitem__)
        elite = [poblacion[i][:] for i in elite_idx]
        nueva = list(elite)

        inyectar   = (stagnacion_counter >= stagnacion_umbral) or (div_actual < diversidad_minima)
        if inyectar:
            n_inject = max(1, int(pop_size * inyeccion_pct))
            nueva.extend(FuncionInicializacion(n_inject))

        while len(nueva) < pop_size:
            p1 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
            p2 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
            h1, h2 = FuncionCruza(p1, p2, prob_cruza, estrategia_cruza)
            nueva.append(FuncionMutacion(h1, prob_mutacion_actual, estrategia_mutacion))
            if len(nueva) < pop_size:
                nueva.append(FuncionMutacion(h2, prob_mutacion_actual, estrategia_mutacion))

        aptitudes_nueva = [eval_ind(ind) for ind in nueva]
        poblacion, div_actual = FuncionPoda(nueva, aptitudes_nueva, pop_size, elitismo)

    return {
        "mejor_fitness":      float(best_fit),
        "mejor_individuo":    best_ind,
        "historial_fitness":  historial_mejor,
        "historial_peor":     historial_peor,
        "historial_promedio": historial_prom,
        "historial_vars":     historial_vars,
    }


def evolucionar(factor_mensual: float, params: Optional[Dict[str, Any]] = None,
                total_sabados: int = 4, nivel_imeca: float = 150.0) -> Dict[str, Any]:
    cfg     = params or {}
    entorno = cargar_entorno_cdmx()
    return ejecutar_algoritmo_genetico(
        factor_mensual=factor_mensual,
        factor_sabado=resumen_probabilidad_sabado(entorno),
        total_sabados=total_sabados,
        nivel_imeca=nivel_imeca,
        pop_size=int(cfg.get("pop_size", DEFAULT_POP_SIZE)),
        generaciones=int(cfg.get("generaciones", DEFAULT_GENERATIONS)),
        prob_cruza=float(cfg.get("prob_cruza", 0.60)),
        prob_mutacion=float(cfg.get("mutacion", 0.05)),
        elitismo=int(cfg.get("elitismo", 1)),
    )


def generar_json_final(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    merged        = {**DEFAULT_PARAMS, **(params or {})}
    entorno       = cargar_entorno_cdmx()
    factor_sabado = resumen_probabilidad_sabado(entorno)

    start_year, start_month = parse_year_month(str(merged["start_month"]))
    meses_count   = max(1, int(merged["meses"]))
    nivel_imeca   = float(merged["nivel_imeca"])
    pop_size      = int(merged["pop_size"])
    generaciones  = int(merged["generaciones"])
    prob_cruza    = float(merged.get("prob_cruza", 0.60))
    prob_mutacion = float(merged["mutacion"])
    elitismo      = int(merged["elitismo"])

    meses_out: List[Dict[str, Any]] = []
    fitness_acumulado: List[float] = []
    analytics_por_mes: List[Dict[str, Any]] = []
    used_color_day_tuples: set = set()
    FLOTA_TOTAL = 6_000_000; CO2_KG = 4.2; EFFECTIVENESS = 0.60

    for i in range(meses_count):
        year_i, month_i = add_months(start_year, start_month, i)
        total_sab_i     = total_saturdays(year_i, month_i)
        factor_mes      = obtener_factor_mensual(entorno, year_i, month_i)
        nivel_imeca_mes = max(0.0, nivel_imeca * factor_mes)
        contaminacion_i  = contamination_for_month(month_i, nivel_imeca_mes)
        factor_i         = contamination_to_factor(contaminacion_i)

        ag_result = ejecutar_algoritmo_genetico(
            factor_mensual=factor_i, factor_sabado=factor_sabado,
            total_sabados=total_sab_i, nivel_imeca=nivel_imeca_mes,
            pop_size=pop_size, generaciones=generaciones,
            prob_cruza=prob_cruza, prob_mutacion=prob_mutacion, elitismo=elitismo,
            estrategia_seleccion=str(merged.get("estrategia_seleccion", "ruleta")),
            estrategia_cruza=str(merged.get("estrategia_cruza", "uniforme")),
            estrategia_mutacion=str(merged.get("estrategia_mutacion", "uniforme")),
            entorno=entorno,
            peso_ambiental=float(merged.get("peso_ambiental_critico", 2.2)),
            peso_economico=float(merged.get("peso_economico", 1.55)),
            peso_equidad=float(merged.get("peso_equidad", 1.0)),
        )
        fitness_acumulado.append(ag_result["mejor_fitness"])
        mejor_ind    = ag_result["mejor_individuo"]
        decoded      = decodificar_individuo(mejor_ind, total_sab_i, nivel_imeca_mes)
        color_to_day = decoded["color_dia_final"]
        _weekdays_i = sum(1 for w in monthcalendar(year_i, month_i) for d in w[:5] if d != 0)
        _h2_cd_i = (FLOTA_TOTAL*0.55/5*_weekdays_i)
        _h1_cd_i = (FLOTA_TOTAL*0.40/5*_weekdays_i)
        _co2_i   = (_h2_cd_i + _h1_cd_i) * CO2_KG * EFFECTIVENESS / 1000
        _autos_i = (_h2_cd_i + _h1_cd_i) / days_in_month(year_i, month_i) / 1e6

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
            nivel_imeca=nivel_imeca_mes,
        ))
        analytics_por_mes.append({
            "mes": month_i, "year": year_i, "contaminacion": contaminacion_i,
            "factor_mensual": round(float(factor_mes), 4),
            "nivel_imeca_efectivo": round(float(nivel_imeca_mes), 2),
            "historial_mejor":    ag_result.get("historial_fitness", []),
            "historial_peor":     ag_result.get("historial_peor", []),
            "historial_promedio": ag_result.get("historial_promedio", []),
            "historial_vars":     ag_result.get("historial_vars", []),
            "variables_optimas":  decoded["decisiones_ag"],
            "co2_evitado_ton":    round(_co2_i, 1),
            "autos_dia_millones": round(_autos_i, 3),
        })

    resultado = {
        "timestamp": str(date.today()),
        "parametros": {k: merged[k] for k in [
            "pop_size", "generaciones", "mutacion", "elitismo",
            "peso_equidad", "peso_ambiental_critico", "peso_economico",
            "nivel_imeca", "start_month", "meses", "prob_cruza",
        ]},
        "contexto_entorno": {"factor_sabado": factor_sabado, "usa_entorno_etl": bool(entorno)},
        "mejor_fitness": sum(fitness_acumulado) / len(fitness_acumulado) if fitness_acumulado else 0.0,
        "estrategias_usadas": {
            "seleccion": str(merged.get("estrategia_seleccion", "ruleta")),
            "cruza": str(merged.get("estrategia_cruza", "un_punto")),
            "mutacion": str(merged.get("estrategia_mutacion", "uniforme")),
        },
        "mejor_solucion": {"meses": meses_out},
        "analytics": {"por_mes": analytics_por_mes},
    }

    RESULTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTADO_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=4)

    return resultado


if __name__ == "__main__":
    resultado = generar_json_final()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
