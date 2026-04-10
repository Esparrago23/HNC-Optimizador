import json
import itertools
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

_LOWER  = ["lunes", "martes", "miercoles", "jueves", "viernes"]
_TITULO = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
DIAS_SEMANA_LOWER = _LOWER
WEEKDAY_INDEX     = {d: i for i, d in enumerate(_LOWER)}
LOWER_TO_TITULO   = dict(zip(_LOWER, _TITULO))
LOWER_DIA         = dict(zip(_TITULO, _LOWER))

CONTAMINATION_FACTORS: Dict[str, float] = {
    "buena": 0.35, "aceptable": 0.90, "mala": 1.45, "muy_mala": 2.20, "extrema": 2.90,
}

_CCONFIG: Dict[str, Any] = {
    "buena":    {"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(0, 1),    "h2_sab_max":3,    "extras":(0, 0),
                 "h1_light_max":2,   "h2_light_max":3},
    "aceptable":{"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(0, 2),    "h2_sab_max":3,    "extras":(0, 0),
                 "h1_light_max":2,   "h2_light_max":3},
    "mala":     {"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(3, None), "h2_sab_max":None, "extras":(0, 2),
                 "h1_light_max":1,   "h2_light_max":2},
    "muy_mala": {"h2_total":False, "h0_wd_max":1,
                 "h1_sab":(3, None), "h2_sab_max":None, "extras":(1, 2),
                 "h1_light_max":1,   "h2_light_max":1},
    "extrema":  {"h2_total":True,  "h0_wd_max":2,
                 "h1_sab":(3, None), "h2_sab_max":None, "extras":(1, 2),
                 "h1_light_max":0,   "h2_light_max":0},
}

PROJECT_ROOT   = Path(__file__).resolve().parent.parent
ENTORNO_PATH   = PROJECT_ROOT / "data" / "entorno_cdmx.json"
RESULTADO_PATH = PROJECT_ROOT / "data" / "resultado_ag_hnc.json"
EPSILON        = 1e-6


def contamination_to_factor(c: str) -> float:
    return CONTAMINATION_FACTORS.get(c, 1.0)

def dia_base_por_defecto(color: str) -> str:
    return _LOWER[COLOR_ORDER.index(color)]

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

    h2_total  = cfg["h2_total"]
    h0_wd_max = cfg["h0_wd_max"]

    h1_min, h1_max_cfg = cfg["h1_sab"]
    h1_max = ts if h1_max_cfg is None else min(ts, h1_max_cfg)
    h2_max = ts if cfg["h2_sab_max"] is None else min(ts, cfg["h2_sab_max"])
    ex_min, ex_max = cfg["extras"]

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
        if h2_total:
            h2_item.update({
                "restriccion_total": True,
                "sabados": sat_list(ts, ts),
                "horario": [5, 22],
                "zona":    "total",
            })
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
                if _LOWER[date(*(int(x) for x in iso.split("-"))).weekday()] != dia
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
        color: _LOWER[min(4, int(float(individuo[11 + idx]) * 5.0))]
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
    """
    Genera la población inicial de `pop_size` individuos de forma aleatoria.

    Cada individuo es un cromosoma de GENES=16 valores reales en [0.0, 1.0].
    Se eligió representación real (en lugar de binaria) porque las variables
    de decisión del HNC son continuas o discretas de rango amplio, y permite
    aplicar mutación gaussiana de forma natural.

    Estructura del cromosoma:
      gen[0-3]   → umbrales que determinan el tipo de restricción por holograma
                   (H00 / H0 / H1 / H2); se ordenan de menor a mayor
      gen[4]     → fracción de colores H1 con horario/zona reducido (0-5 colores)
      gen[5]     → fracción de colores H2 con horario/zona reducido (0-5 colores)
      gen[6]     → fase de rotación del orden de prioridad en H1
      gen[7]     → fase de rotación del orden de prioridad en H2
      gen[8]     → número de sábados de restricción H1  ∈ [0, total_sábados]
      gen[9]     → número de sábados de restricción H2  ∈ [0, total_sábados]
      gen[10]    → días extra de restricción H2          ∈ [0, 4]
      gen[11-15] → día base de la semana por color (Verde / Amarillo / Rosa /
                   Rojo / Azul); se repara si hay colisiones (Lamarckismo)
    """
    return [[random.random() for _ in range(GENES)] for _ in range(pop_size)]


# §1.4.1
def FuncionAptitud(
    individuo: List[float],
    entorno: Dict[str, Any],
    total_sabados: int,
    nivel_imeca: float,
    peso_ambiental: float = 2.2,
    peso_economico: float = 1.55,
) -> float:
    """
    Evalúa la aptitud de un individuo para un mes dado.

    El individuo se decodifica en decisiones concretas de restricción vehicular
    y se calcula la aptitud con base en tres variables de optimización:

        Aptitud = v / (E × w_amb + IE × w_eco + ε) × 10⁶          (Ec. 1.2)

    Variables:
      v  = velocidad vial promedio  [km/h]        → MAXIMIZAR
      E  = emisiones totales        [g/día]        → MINIMIZAR
      IE = impacto económico        [MXN/día]      → MINIMIZAR

    ── Paso 1: decodificar el cromosoma ─────────────────────────────────────
    """
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

    trafico = entorno.get("trafico", {})
    M   = sum(float(v.get("total", 0)) * (1.0 - R.get(h, 0.0)) for h, v in vehiculos.items())
    vf  = float(trafico.get("v_f",          45.0))
    C   = float(trafico.get("capacidad_c",   3_500_000))
    α   = float(trafico.get("alpha",         0.15))
    β   = float(trafico.get("beta",          4.0))
    v_bpr = vf / (1.0 + α * (M / max(C, 1.0)) ** β)

    factor_imeca = 1.0 + max(0.0, (nivel_imeca - 100) / 100.0) * (peso_ambiental - 1.0)
    return (v_bpr / (E * factor_imeca + IE * peso_economico + EPSILON)) * 1e6


# §1.4.3
def FuncionGeneracionParejas(
    poblacion: List[List[float]],
    aptitudes: List[float],
    estrategia: str = "ruleta",
) -> List[float]:
    """
    Selecciona UN padre de la población según la estrategia indicada.
    Llamar dos veces para obtener la pareja completa (padre1, padre2).

    Estrategias implementadas
    ─────────────────────────
    "ruleta"  — Selección proporcional a la aptitud.
                P(i) = aptitud_ajustada(i) / suma_total.
                Se desplaza el rango si hay aptitudes negativas para garantizar
                P(i) > 0 en todos los individuos.

    "torneo"  — Se eligen k=3 candidatos al azar y gana el de mayor aptitud.
                Más robusto que ruleta cuando las aptitudes tienen escala extrema
                o valores negativos. Mayor k → mayor presión selectiva.

    "ranking" — Se asigna peso p a cada individuo según su posición en el
                ranking (posición 1 = peor, posición N = mejor).
                Reduce la dominancia de individuos muy superiores y mantiene
                mayor diversidad que ruleta cuando el mejor es muy distante.
    """
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
    """
    Recombina dos padres para producir dos hijos.
    Si random() ≥ prob_cruza, los padres se copian sin cambios.

    Estrategias implementadas
    ─────────────────────────
    "un_punto"   — Se elige un punto de corte aleatorio p ∈ [1, GENES-1].
                   hijo1 = padre1[:p] + padre2[p:]
                   hijo2 = padre2[:p] + padre1[p:]
                   Preserva bloques contiguos de genes (schemata cortos).

    "dos_puntos" — Se eligen dos puntos a < b.  El segmento central se cruza.
                   hijo1 = padre1[:a] + padre2[a:b] + padre1[b:]
                   Mayor mezcla que un punto; útil en cromosomas medianos.

    "uniforme"   — Cada gen se intercambia de forma independiente con P=0.5.
                   Es la estrategia más disruptiva y maximiza la exploración
                   del espacio de búsqueda en cromosomas largos como el HNC.
    """
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
    """
    Aplica mutación gen a gen con probabilidad prob_mutacion.
    Todos los valores se mantienen en [0.0, 1.0] mediante clamp01().

    Estrategias implementadas
    ─────────────────────────
    "uniforme"  — El gen muta sumando una perturbación ε ∈ Uniforme(−0.1, 0.1).
                  Produce cambios de magnitud constante y exploración localizada.

    "gaussiana" — El gen muta sumando ε ~ N(0, σ=0.08).
                  Mutaciones pequeñas son más frecuentes que las grandes
                  (cola de campana), favorece ajuste fino cerca del óptimo.
                  σ=0.08 es mayor que el típico 0.05 para escapar mesetas.

    "reset"     — El gen se reemplaza por un valor completamente aleatorio en
                  [0, 1].  Exploración global; útil cuando la población se ha
                  homogeneizado y el AG está estancado.
    """
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
) -> List[List[float]]:
    """
    Reduce la población al tamaño objetivo seleccionando los mejores individuos.

    Estrategia: reemplazo generacional con elitismo.
    ─────────────────────────────────────────────────
    1. Se ordenan todos los individuos (padres + hijos) de mayor a menor aptitud.
    2. Los primeros `elitismo` pasan directamente garantizando que el mejor
       individuo jamás se pierda (propiedad de monotonía).
    3. Se conservan en total los primeros `tam_objetivo` individuos.

    También mide la diversidad genética de la nueva generación como la
    desviación estándar promedio de cada gen (0 = clones, ~0.29 = aleatorio),
    información que el motor usa para detectar convergencia prematura.
    """
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

    return nueva_gen


def _diversidad_poblacion(poblacion: List[List[float]]) -> float:
    """Calcula la diversidad genética como desviación estándar promedio por gen."""
    diversidad = 0.0
    if len(poblacion) >= 2:
        for g in range(len(poblacion[0])):
            vals  = [ind[g] for ind in poblacion]
            media = sum(vals) / len(vals)
            var   = sum((v - media) ** 2 for v in vals) / len(vals)
            diversidad += var ** 0.5
        diversidad /= len(poblacion[0])
    return diversidad


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
    """
    Motor evolutivo con estrategias configurables y mecanismo anti-convergencia prematura.

    Soporta múltiples operadores por etapa:
      Selección:   ruleta | torneo | ranking
      Cruzamiento: un_punto | dos_puntos | uniforme
      Mutación:    uniforme | gaussiana | reset

    Mecanismo anti-estancamiento:
      - Mutación adaptativa: la tasa sube gradualmente cada generación sin mejora.
      - Inyección de diversidad: se insertan individuos aleatorios cuando el AG
        lleva `stagnacion_umbral` generaciones sin progresar O cuando la diversidad
        genética cae por debajo de `diversidad_minima`.
    """
    env = entorno or {}

    def eval_ind(ind: List[float]) -> float:
        return FuncionAptitud(ind, env, total_sabados, nivel_imeca, peso_ambiental, peso_economico)

    poblacion  = FuncionInicializacion(pop_size)
    best_fit   = -math.inf
    best_ind: List[float] = []
    historial_mejor: List[float] = []
    historial_peor:  List[float] = []
    historial_prom:  List[float] = []
    historial_vars:  List[Dict[str, Any]] = []

    stagnacion_counter = 0
    prev_best          = -math.inf

    for _ in range(generaciones):
        aptitudes_lista = [eval_ind(ind) for ind in poblacion]
        ranking = sorted(zip(poblacion, aptitudes_lista), key=lambda x: x[1], reverse=True)
        mejor_ind_gen, mejor_fit_gen = ranking[0]

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

        elite = [ind[:] for ind, _ in ranking[:max(1, elitismo)]]
        nueva = list(elite)

        div_actual = _diversidad_poblacion(poblacion)
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
        poblacion       = FuncionPoda(nueva, aptitudes_nueva, pop_size, elitismo)

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
        prob_cruza=float(cfg.get("prob_cruza", 0.60)),
        prob_mutacion=float(cfg.get("mutacion", 0.05)),
        elitismo=int(cfg.get("elitismo", 1)),
    )


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
        contaminacion_i = contamination_for_month(month_i, nivel_imeca)
        factor_i        = contamination_to_factor(contaminacion_i)

        ag_result = ejecutar_algoritmo_genetico(
            factor_mensual=factor_i, factor_sabado=factor_sabado,
            total_sabados=total_sab_i, nivel_imeca=nivel_imeca,
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
        decoded      = decodificar_individuo(mejor_ind, total_sab_i, nivel_imeca)
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
            nivel_imeca=nivel_imeca,
        ))
        analytics_por_mes.append({
            "mes": month_i, "year": year_i, "contaminacion": contaminacion_i,
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
