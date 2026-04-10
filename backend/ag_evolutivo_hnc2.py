import json
import itertools
import heapq
import math
import random
from calendar import monthcalendar, monthrange
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GENES            = 18  # +2 genes para zona (centro vs total) de días ligeros H1/H2
DEFAULT_POP_SIZE = 100
DEFAULT_GENERATIONS = 120

DEFAULT_PARAMS = {
    "pop_size": 120, "generaciones": 150, "mutacion": 0.10, "elitismo": 3,
    "peso_equidad": 1, "peso_ambiental_critico": 2.2, "peso_economico": 1.55,
    "nivel_imeca": 150, "start_month": "2026-04", "meses": 6,
    "prob_cruza": 0.78,
    "estrategia_seleccion": "torneo",
    "estrategia_cruza":     "multipunto",
    "estrategia_mutacion":  "gaussiana",
    "estrategia_poda":      "elitismo",
    "n_runs": 2,
}
DEFAULT_POP_SIZE    = 120
DEFAULT_GENERATIONS = 150

GRUPOS_PLACA = {"Amarillo": [5, 6], "Rosa": [7, 8], "Rojo": [3, 4], "Verde": [1, 2], "Azul": [9, 0]}
HOLOGRAMAS   = ["H00", "H0", "H1", "H2"]
COLOR_ORDER  = ["Verde", "Amarillo", "Rosa", "Rojo", "Azul"]

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes"]
WEEKDAY_INDEX = {d: i for i, d in enumerate(DIAS_SEMANA)}
DIA_BASE_POR_COLOR = dict(zip(COLOR_ORDER, DIAS_SEMANA))

CONTAMINATION_FACTORS: Dict[str, float] = {
    "buena": 0.35, "aceptable": 0.90, "mala": 1.45, "muy_mala": 2.21, "extrema": 2.90,
}

_CCONFIG: Dict[str, Any] = {
    # Días H1/H2 pueden tener 3 modos: (05:00-16:00 centro), (05:00-16:00 total), (05:00-22:00 total)
    # h2_sab: (min, max) donde None = ts (todos los sábados del mes)
    # Escalera H2: 5-sáb → (3,0)→(4,0)→(5,0)→(5,1)→(5,2) | 4-sáb → (3,0)→(4,0)→(4,0)→(4,1)→(4,2)

    # Buena (0-50 IMECA): 3 sábados H2, hasta 3 colores con horario ligero
    "buena":    {"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(0, 1),    "h2_sab":(3, 3),       "extras":(0, 0),
                 "h1_light_max":3,   "h2_light_max":2},
    # Aceptable (51-100 IMECA): H2 cubre todos los sábados del mes (mín 4 o ts si ts<4)
    "aceptable":{"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(1, 2),    "h2_sab":(4, None),    "extras":(0, 0),
                 "h1_light_max":2,   "h2_light_max":1},
    # Mala (101-150 IMECA): todos los sábados H2, sin días extra aún
    "mala":     {"h2_total":False, "h0_wd_max":0,
                 "h1_sab":(1, 3),    "h2_sab":(None, None), "extras":(0, 0),
                 "h1_light_max":1,   "h2_light_max":0},
    # Muy mala (151-200 IMECA): todos los sábados H2 + hasta 1 día extra
    "muy_mala": {"h2_total":False, "h0_wd_max":1,
                 "h1_sab":(2, 4),    "h2_sab":(None, None), "extras":(0, 1),
                 "h1_light_max":0,   "h2_light_max":0},
    # Extrema (200+ IMECA): todos los sábados H2 + 1-2 días extra, restricción total
    "extrema":  {"h2_total":True,  "h0_wd_max":2,
                 "h1_sab":(3, None), "h2_sab":(None, None), "extras":(1, 2),
                 "h1_light_max":0,   "h2_light_max":0},
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
        cfg_l = _CCONFIG.get(contaminacion, _CCONFIG["extrema"])
        h1_cap, h2_cap = int(cfg_l.get("h1_light_max", 0)), int(cfg_l.get("h2_light_max", 0))

        # USAR las decisiones ya tomadas por el AG en decodificar_individuo.
        # Los genes phase_h1/h2 rotan qué colores reciben hora=16.
        # Los genes n_centro_h1/h2 determinan cuáles de esos días son zona "Centro".
        # Sólo aplicamos el cap de contaminación como guardia final.
        if "h1_hora_por_color" in d_ag:
            raw_h1      = d_ag["h1_hora_por_color"]
            raw_h2      = d_ag.get("h2_hora_por_color", {c: 22 for c in COLOR_ORDER})
            raw_h1_zona = d_ag.get("h1_zona_por_color", {c: "Total" for c in COLOR_ORDER})
            raw_h2_zona = d_ag.get("h2_zona_por_color", {c: "Total" for c in COLOR_ORDER})
            # Colores con hora=16 en orden COLOR_ORDER (determinista)
            ligeras_h1 = [c for c in COLOR_ORDER if raw_h1.get(c, 22) == 16]
            ligeras_h2 = [c for c in COLOR_ORDER if raw_h2.get(c, 22) == 16]
            # Aplicar cap por contaminación
            activas_h1 = set(ligeras_h1[:h1_cap])
            activas_h2 = set(ligeras_h2[:h2_cap])
            # Zona: preservar "Centro" de las decisiones del AG (sólo cuando hora=16)
            return {
                "h1_hora_por_color": {c: (16 if c in activas_h1 else 22) for c in COLOR_ORDER},
                "h1_zona_por_color": {
                    c: (raw_h1_zona.get(c, "Total") if c in activas_h1 else "Total")
                    for c in COLOR_ORDER
                },
                "h2_hora_por_color": {c: (16 if c in activas_h2 else 22) for c in COLOR_ORDER},
                "h2_zona_por_color": {
                    c: (raw_h2_zona.get(c, "Total") if c in activas_h2 else "Total")
                    for c in COLOR_ORDER
                },
            }

        # Fallback sin decisiones del AG: restricción completa
        return {
            "h1_hora_por_color": {c: 22 for c in COLOR_ORDER},
            "h1_zona_por_color": {c: "Total" for c in COLOR_ORDER},
            "h2_hora_por_color": {c: 22 for c in COLOR_ORDER},
            "h2_zona_por_color": {c: "Total" for c in COLOR_ORDER},
        }

    ts  = total_saturdays(year, month)
    cfg = _CCONFIG.get(contaminacion, _CCONFIG["extrema"])

    h2_total  = cfg["h2_total"]
    h0_wd_max = cfg["h0_wd_max"]

    h1_min, h1_max_cfg = cfg["h1_sab"]
    h1_max = ts if h1_max_cfg is None else min(ts, h1_max_cfg)

    # h2_sab es (min, max); None significa "todos los sábados del mes"
    h2_sab_cfg = cfg["h2_sab"]
    h2_min_cfg = ts if h2_sab_cfg[0] is None else min(ts, h2_sab_cfg[0])
    h2_max_cfg = ts if h2_sab_cfg[1] is None else min(ts, h2_sab_cfg[1])

    ex_min, ex_max = cfg["extras"]

    if ag_decisions:
        ag_h1 = int(ag_decisions.get("sabados_h1",       h1_max))
        ag_h2 = int(ag_decisions.get("sabados_h2",       h2_max_cfg))
        ag_ex = int(ag_decisions.get("dias_extra_h2",    ex_max))
        ag_h0 = int(ag_decisions.get("h0_weekday_count", h0_wd_max))
    else:
        ag_h1, ag_h2, ag_ex, ag_h0 = h1_max, h2_max_cfg, ex_max, h0_wd_max

    h1_sab           = max(h1_min,     min(h1_max,     ag_h1))
    h2_sab           = max(h2_min_cfg, min(h2_max_cfg, ag_h2))
    extras_per_color = max(ex_min,     min(ex_max,     ag_ex))
    # Escalera coherente: sin extras si los sábados no están al máximo
    if h2_sab < h2_max_cfg:
        extras_per_color = 0
    h0_weekday_count = min(h0_wd_max, h0_limits_from_imeca(nivel_imeca)[0], ag_h0)

    # ── Pre-cómputo de fechas_ligeras ────────────────────────────────────────
    # El AG decide:  n_light_h1 = total entradas ligeras del mes para H1
    #                n_centro_h1 = cuántas de esas entradas son zona "Centro"
    #                prio = orden en que se distribuyen por color (del AG)
    # Se distribuye en round-robin por prioridad del AG.
    # Cada entrada en fechas_ligeras lleva su propia (fecha, horario, zona).

    def _build_fechas_ligeras(
        n_total: int, n_centro: int,
        prio: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {c: [] for c in COLOR_ORDER}
        if n_total <= 0:
            return result
        # Distribuir n_total entre colores en round-robin por prioridad
        counts: Dict[str, int] = {c: 0 for c in COLOR_ORDER}
        remaining = n_total
        i = 0
        while remaining > 0 and i < len(prio) * 6:
            c = prio[i % len(prio)]
            wd_c = WEEKDAY_INDEX[color_to_day_lower.get(c, dia_base_por_defecto(c))]
            max_c = len(all_weekday_dates(year, month, wd_c))
            if counts[c] < max_c:
                counts[c] += 1
                remaining -= 1
            i += 1
        # Seleccionar fechas específicas y asignar zona globalmente
        centro_left = n_centro
        for c in prio:
            cnt = counts[c]
            if cnt == 0:
                continue
            wd_c  = WEEKDAY_INDEX[color_to_day_lower.get(c, dia_base_por_defecto(c))]
            bias  = COLOR_ORDER.index(c)
            dates = spread_weekday_dates(
                year, month, wd_c, cnt,
                salt=color_month_salt(year, month, f"light-{c}"),
                phase_bias=bias,
            )
            for fecha in sorted(dates):
                zona = "centro" if centro_left > 0 else "total"
                if centro_left > 0:
                    centro_left -= 1
                result[c].append({"fecha": fecha, "horario": [5, 16], "zona": zona})
        return result

    _d = ag_decisions or {}
    _prio_h1 = list(_d.get("orden_prioridad_ligero_h1", COLOR_ORDER))
    _prio_h2 = list(_d.get("orden_prioridad_ligero_h2", COLOR_ORDER))
    _fl_h1 = _build_fechas_ligeras(
        int(_d.get("n_light_h1", 0)), int(_d.get("n_centro_h1", 0)), _prio_h1,
    )
    _fl_h2 = _build_fechas_ligeras(
        int(_d.get("n_light_h2", 0)), int(_d.get("n_centro_h2", 0)), _prio_h2,
    )
    # ─────────────────────────────────────────────────────────────────────────

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
        h1_item: Dict[str, Any] = {
            "dia_base": dia, "sabados": sat_list(ts, h1_sab),
            "horario": [5, 22], "zona": "total",
        }
        if _fl_h1[color]:          # hay fechas ligeras para este color
            h1_item["fechas_ligeras"] = _fl_h1[color]
        h1_por_color[color] = h1_item

        h2_item: Dict[str, Any] = {
            "dia_base": dia, "sabados": sat_list(ts, h2_sab),
            "horario": [5, 22], "zona": "total",
        }
        if _fl_h2[color]:
            h2_item["fechas_ligeras"] = _fl_h2[color]
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
    def _cov(hora: Dict[str, int], zona: Dict[str, str]) -> float:
        return sum(
            (1.0 if "entro" not in str(zona.get(c, "Total")) else 0.5) *
            (1.0 if int(hora.get(c, 22)) == 22 else 11.0 / 17.0)
            for c in COLOR_ORDER
        ) / len(COLOR_ORDER)

    r_h00, r_h0, r_h1, r_h2 = sorted(float(g) for g in individuo[0:4])
    ts = total_sabados_mes

    # n_light depende del nivel de contaminación:
    # buena=0-3 colores, aceptable=0-2, mala=0-1, muy_mala/extrema=0
    _cc_dec  = contamination_for_month(1, nivel_imeca)
    _cfg_dec = _CCONFIG.get(_cc_dec, _CCONFIG["extrema"])
    _h1cap   = int(_cfg_dec.get("h1_light_max", 0))
    _h2cap   = int(_cfg_dec.get("h2_light_max", 0))

    # Mínimos de días ligeros por política:
    #   buena     → H1 debe tener al menos 2 colores con hora=16 (la restricción completa sería excesiva)
    #   aceptable → H1 debe tener al menos 1 color con hora=16
    #   mala+     → sin mínimo (el AG decide si aplica alguno dentro del cap)
    _h1_light_min = {"buena": 2, "aceptable": 1}.get(_cc_dec, 0)
    _h2_light_min = {"buena": 1}.get(_cc_dec, 0)

    n_light_h1 = max(_h1_light_min, min(_h1cap, int(individuo[4] * (_h1cap + 1)))) if _h1cap > 0 else 0
    n_light_h2 = max(_h2_light_min, min(_h2cap, int(individuo[5] * (_h2cap + 1)))) if _h2cap > 0 else 0

    phase_h1      = min(4, int(individuo[6] * 5))
    phase_h2      = min(4, int(individuo[7] * 5))
    sabados_h1    = min(ts, int(individuo[8] * (ts + 1)))
    sabados_h2    = min(ts, int(individuo[9] * (ts + 1)))
    dias_extra_h2 = min(4, int((individuo[10] if len(individuo) > 10 else 0.0) * 5))

    # Genes 16-17: cuántos de los días ligeros (hora=16) usan zona "Centro" (el resto "Total")
    # Los 3 modos posibles son: (05-16 Centro), (05-16 Total), (05-22 Total)
    # En buena: al menos 1 color con hora=16 debe ser zona Centro
    # En aceptable: no se usa Centro (moderado, solo Total)
    # En mala+: sin días ligeros, por lo que n_centro = 0
    _g16 = individuo[16] if len(individuo) > 16 else 0.0
    _g17 = individuo[17] if len(individuo) > 17 else 0.0

    # En buena: al menos 1 Centro Y al menos 1 Total (para tener los 3 modos).
    # n_centro ∈ [1, n_light-1] cuando n_light >= 2.
    # En aceptable: sin Centro (solo Total+16 y Total+22).
    # En mala+: n_light=0, por lo que n_centro=0 de todas formas.
    if _cc_dec == "buena" and n_light_h1 >= 2:
        _h1c_min = 1
        _h1c_max = n_light_h1 - 1          # deja al menos 1 ligero en Total
        n_centro_h1 = max(_h1c_min, min(_h1c_max, int(_g16 * (_h1c_max + 1))))
    else:
        n_centro_h1 = 0                     # aceptable/mala+: sin Centro en H1

    if _cc_dec == "buena" and n_light_h2 >= 2:
        _h2c_max = n_light_h2 - 1
        n_centro_h2 = min(_h2c_max, int(_g17 * (_h2c_max + 1)))
    else:
        n_centro_h2 = 0

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

    # 3 modos posibles por color: (05-16 Centro), (05-16 Total), (05-22 Total).
    # El AG decide via phase_h1/h2 (rotación) qué colores reciben hora=16,
    # y via n_centro_h1/h2 cuántos de esos días ligeros son zona "Centro".
    h1_hora_por_color = {c: (16 if i < n_light_h1 else 22) for i, c in enumerate(prio_h1)}
    h1_zona_por_color = {
        c: ("Centro" if i < n_centro_h1 and h1_hora_por_color[c] == 16 else "Total")
        for i, c in enumerate(prio_h1)
    }
    h2_hora_por_color = {c: (16 if i < n_light_h2 else 22) for i, c in enumerate(prio_h2)}
    h2_zona_por_color = {
        c: ("Centro" if i < n_centro_h2 and h2_hora_por_color[c] == 16 else "Total")
        for i, c in enumerate(prio_h2)
    }

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
            "n_centro_h1": n_centro_h1, "n_centro_h2": n_centro_h2,
            "orden_prioridad_ligero_h1": prio_h1,
            "orden_prioridad_ligero_h2": prio_h2,
            "phase_h1": phase_h1, "phase_h2": phase_h2,
        },
    }


def FuncionInicializacion(pop_size: int) -> List[List[float]]:
    return [[random.random() for _ in range(GENES)] for _ in range(pop_size)]


def FuncionAptitud(
    individuo: List[float],
    entorno: Dict[str, Any],
    total_sabados: int,
    nivel_imeca: float,
    peso_ambiental: float = 2.2,
    peso_economico: float = 1.55,
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

    trafico = entorno.get("trafico", {})
    M   = sum(float(v.get("total", 0)) * (1.0 - R.get(h, 0.0)) for h, v in vehiculos.items())
    vf  = float(trafico.get("v_f",          45.0))
    C   = float(trafico.get("capacidad_c",   3_500_000))
    α   = float(trafico.get("alpha",         0.15))
    β   = float(trafico.get("beta",          4.0))
    v_bpr = vf / (1.0 + α * (M / max(C, 1.0)) ** β)

    factor_imeca = 1.0 + max(0.0, (nivel_imeca - 100) / 100.0) * (peso_ambiental - 1.0)
    fitness_base = (v_bpr / (E * factor_imeca + IE * peso_economico + EPSILON)) * 1e6

    # Penalización ligera por días horario=16 cuando IMECA es muy alto.
    # Se redujo al mínimo para que el AG explore libremente y llegue al mejor equilibrio.
    n_l_h1   = int(d_ag.get("n_light_h1", 0))
    n_l_h2   = int(d_ag.get("n_light_h2", 0))
    n_l_total = n_l_h1 + n_l_h2
    _imeca_factor = max(0.0, (nivel_imeca - 100) / 200.0)
    penalizador_ligero = 1.0 - (n_l_total * _imeca_factor * 0.015)   # muy suave

    # Penalización mínima por escalera H2 incoherente (extras antes de llenar sábados).
    if h2_ex > 0 and h2_sabs < total_sabados:
        _sab_faltantes = total_sabados - h2_sabs
        penalizador_escalera = max(0.70, 1.0 - 0.05 * h2_ex * _sab_faltantes)
    else:
        penalizador_escalera = 1.0

    # Bonus por restricción proporcional al nivel IMECA.
    _n_centro_h1 = int(d_ag.get("n_centro_h1", 0))
    if nivel_imeca <= 50:
        _bonus_proporcional = 1.0 + n_l_h1 * 0.07 + _n_centro_h1 * 0.04
    elif nivel_imeca <= 100:
        _bonus_proporcional = 1.0 + n_l_h1 * 0.04
    else:
        _bonus_proporcional = 1.0

    return fitness_base * max(0.5, penalizador_ligero) * penalizador_escalera * _bonus_proporcional


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
        k       = 5   # torneo más grande → más presión de selección → mejores padres
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


def FuncionCruza(
    padre1: List[float],
    padre2: List[float],
    prob_cruza: float = 0.78,
    estrategia: str   = "multipunto",
) -> Tuple[List[float], List[float]]:
    """
    Estrategias de cruzamiento disponibles:
      un_punto   — Un único punto de corte; intercambia los segmentos resultantes.
      multipunto — K puntos de corte aleatorios (K entre 2 y 4); mejor mezcla genética.
      uniforme   — Cada gen se hereda de uno u otro padre con prob. 0.5.
      permutacion— Genera una permutación aleatoria de posiciones; los hijos heredan
                   la mitad de las posiciones de cada padre según la permutación.
    """
    if random.random() >= prob_cruza:
        return padre1[:], padre2[:]

    if estrategia == "un_punto":
        # Un solo punto de corte aleatorio
        p  = random.randint(1, GENES - 1)
        h1 = padre1[:p] + padre2[p:]
        h2 = padre2[:p] + padre1[p:]

    elif estrategia == "multipunto":
        # K puntos aleatorios (2-4); alterna segmentos entre padres.
        # Más mezcla que un punto; ideal para cromosomas con genes relacionados.
        k      = random.randint(2, min(4, GENES - 1))
        puntos = sorted(random.sample(range(1, GENES), k))
        h1, h2 = [], []
        prev   = 0
        de_p1  = True          # primer segmento viene de padre1 para h1
        for punto in puntos + [GENES]:
            seg = slice(prev, punto)
            if de_p1:
                h1.extend(padre1[seg]); h2.extend(padre2[seg])
            else:
                h1.extend(padre2[seg]); h2.extend(padre1[seg])
            de_p1 = not de_p1
            prev  = punto

    elif estrategia == "uniforme":
        # Cada gen se toma de padre1 o padre2 con prob. 50% independientemente.
        h1 = [padre2[i] if random.random() < 0.5 else padre1[i] for i in range(GENES)]
        h2 = [padre1[i] if h1[i] == padre2[i]   else padre2[i]  for i in range(GENES)]

    else:  # permutacion
        # Permutación de posiciones: una máscara aleatoria decide qué mitad de
        # las posiciones del cromosoma hereda cada gen de cuál padre.
        perm = list(range(GENES))
        random.shuffle(perm)
        mitad = GENES // 2
        h1    = list(padre1)
        h2    = list(padre2)
        for idx in perm[mitad:]:
            h1[idx], h2[idx] = padre2[idx], padre1[idx]

    return h1, h2


def FuncionMutacion(
    individuo: List[float],
    prob_mutacion: float = 0.10,
    estrategia: str      = "gaussiana",
    escala: float        = 0.07,
) -> List[float]:
    """
    Estrategias de mutación disponibles:
      intercambio — Intercambia (swap) pares de genes seleccionados al azar.
                    Mantiene los valores pero cambia sus posiciones.
      sustitucion — Reemplaza cada gen seleccionado con un valor aleatorio en [0,1].
                    También llamada 'inserción' o 'reset'.
      gaussiana   — Suma un pequeño ruido gaussiano (creep) al gen.
                    Exploración local suave; la más efectiva para valores continuos.
    """
    mutado = individuo[:]

    if estrategia == "intercambio":
        # Reúne los índices a mutar y los intercambia en pares
        indices = [i for i in range(GENES) if random.random() < prob_mutacion]
        random.shuffle(indices)
        for k in range(0, len(indices) - 1, 2):
            i, j         = indices[k], indices[k + 1]
            mutado[i], mutado[j] = mutado[j], mutado[i]
        # Si sobra un índice sin par, lo intercambia con una posición aleatoria
        if len(indices) % 2 == 1:
            i = indices[-1]
            j = random.randint(0, GENES - 1)
            mutado[i], mutado[j] = mutado[j], mutado[i]

    elif estrategia == "sustitucion":
        # Reemplaza el gen con un valor aleatorio uniforme (sustitución/inserción)
        for i in range(GENES):
            if random.random() < prob_mutacion:
                mutado[i] = random.random()

    else:  # gaussiana (creep)
        # Perturbación gaussiana pequeña; la más adecuada para búsqueda continua.
        # La escala se adapta externamente según el nivel de estancamiento.
        for i in range(GENES):
            if random.random() < prob_mutacion:
                mutado[i] = clamp01(individuo[i] + random.gauss(0, escala))

    return mutado


def _calcular_diversidad(poblacion: List[List[float]]) -> float:
    if len(poblacion) < 2:
        return 0.0
    div = 0.0
    for g in range(GENES):
        vals  = [ind[g] for ind in poblacion]
        media = sum(vals) / len(vals)
        var   = sum((v - media) ** 2 for v in vals) / len(vals)
        div  += var ** 0.5
    return div / GENES


def FuncionPoda(
    candidatos: List[List[float]],
    aptitudes:  List[float],
    tam_objetivo: int,
    elitismo_n: int = 1,
    estrategia_poda: str = "elitismo",
    poblacion_actual: Optional[List[List[float]]] = None,
    aptitudes_actual: Optional[List[float]]       = None,
) -> Tuple[List[List[float]], float]:
    """
    Estrategias de poda / reemplazo:
      generacional    — La descendencia reemplaza completamente a los padres.
                        Exploración rápida; conserva el mejor global para no regredir.
      elitismo        — Los mejores N individuos de la generación actual sobreviven;
                        el resto se rellena con la mejor descendencia. Equilibrio estable.
      estado_estacionario — Solo se reemplazan los peores K miembros de la población
                        cuando un hijo nuevo los supera. Convergencia lenta pero sólida.
    """
    if estrategia_poda == "generacional":
        # Reemplaza toda la población con la descendencia.
        # El mejor individuo global (primer elemento de candidatos si lo pasamos) SIEMPRE sobrevive.
        ranking   = sorted(zip(candidatos, aptitudes), key=lambda x: x[1], reverse=True)
        nueva_gen = [ind[:] for ind, _ in ranking[:tam_objetivo]]

    elif estrategia_poda == "estado_estacionario":
        # Combina población actual con candidatos (nueva descendencia),
        # reemplaza solo a los peores por los mejores nuevos individuos.
        if poblacion_actual and aptitudes_actual:
            todos     = list(zip(poblacion_actual + candidatos,
                                 aptitudes_actual  + aptitudes))
        else:
            todos = list(zip(candidatos, aptitudes))
        ranking   = sorted(todos, key=lambda x: x[1], reverse=True)
        nueva_gen = [ind[:] for ind, _ in ranking[:tam_objetivo]]

    else:  # "elitismo" (default)
        # Candidatos ya incluye elite + descendencia; tomamos los mejores K.
        ranking   = sorted(zip(candidatos, aptitudes), key=lambda x: x[1], reverse=True)
        nueva_gen = [ind[:] for ind, _ in ranking[:tam_objetivo]]

    return nueva_gen, _calcular_diversidad(nueva_gen)


def ejecutar_algoritmo_genetico(
    factor_mensual: float,
    factor_sabado: float = 1.0,
    total_sabados: int = 4,
    nivel_imeca: float = 150.0,
    pop_size: int = DEFAULT_POP_SIZE,
    generaciones: int = DEFAULT_GENERATIONS,
    prob_cruza: float = 0.80,
    prob_mutacion: float = 0.10,
    elitismo: int = 3,
    estrategia_seleccion: str = "torneo",
    estrategia_cruza: str = "multipunto",
    estrategia_mutacion: str = "gaussiana",
    estrategia_poda: str = "elitismo",
    entorno: Optional[Dict[str, Any]] = None,
    peso_ambiental: float = 2.2,
    peso_economico: float = 1.55,
    peso_equidad: float = 1.0,
    stagnacion_umbral: int = 12,
    mutacion_max: float = 0.45,
    inyeccion_pct: float = 0.20,
    diversidad_minima: float = 0.02,
    restart_umbral: int = 35,
    restart_keep_pct: float = 0.20,
) -> Dict[str, Any]:
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
    restart_counter    = 0
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

        # ── métricas derivadas para las 3 gráficas adicionales ──────────────
        _d_g     = d_ag_gen
        _cum_g   = float(env.get("cumplimiento_ciudadano", 0.85))
        _dias_g  = 30
        _h1s_g   = int(_d_g.get("sabados_h1", 0))
        _h2s_g   = int(_d_g.get("sabados_h2", 0))
        _h2x_g   = int(_d_g.get("dias_extra_h2", 0))
        _h0_g    = int(_d_g.get("h0_weekday_count", 0))
        _cov1_g  = float(_d_g.get("cov_h1_avg", 1.0))
        _cov2_g  = float(_d_g.get("cov_h2_avg", 1.0))
        _dh_g    = max(1, _dias_g - total_sabados)
        _R_g = {
            "H00": 0.0,
            "H0" : _cum_g * (_h0_g / max(1, _dias_g)),
            "H1" : _cum_g * ((_dh_g / 5 + _h1s_g) / _dias_g) * _cov1_g,
            "H2" : _cum_g * ((_dh_g / 5 + _h2s_g + _h2x_g) / _dias_g) * _cov2_g,
        }
        _veh_g  = env.get("vehiculos", {})
        _D_g    = float(env.get("distancia_promedio_km", 24.0))
        # Emisiones totales (gr/km): suma contaminantes ponderada por vehículos activos
        _E_g = sum(
            float(v.get("total", 0)) * (1.0 - _R_g.get(h, 0.0))
            * float(v.get("ef", 1.0)) * _D_g
            for h, v in _veh_g.items()
        ) if _veh_g else (
            nivel_imeca * (1.0 - (_R_g["H1"] + _R_g["H2"]) / 2.0)
        )
        # Velocidad promedio BPR (km/h)
        _M_g    = sum(float(v.get("total", 0)) * (1.0 - _R_g.get(h, 0.0)) for h, v in _veh_g.items())
        _trafico_g = env.get("trafico", {})
        _vf_g   = float(_trafico_g.get("v_f", 45.0))
        _C_g    = float(_trafico_g.get("capacidad_c", 3_500_000))
        _α_g    = float(_trafico_g.get("alpha", 0.15))
        _β_g    = float(_trafico_g.get("beta", 4.0))
        _vbpr_g = _vf_g / (1.0 + _α_g * (_M_g / max(_C_g, 1.0)) ** _β_g)
        # Impacto económico: viajes laborales cancelados/retrasados (miles)
        _IE_g = sum(
            _R_g.get(h, 0.0) * float(v.get("total", 0))
            * float(v.get("p_l", 0.3)) * float(v.get("costo", 1.0))
            for h, v in _veh_g.items()
        ) if _veh_g else (
            (_R_g["H1"] + _R_g["H2"]) / 2.0 * 6_000_000 * 0.29
        )

        historial_vars.append({
            "sabados_h1":         int(_d_g.get("sabados_h1", 0)),
            "sabados_h2":         int(_d_g.get("sabados_h2", 0)),
            "dias_extra_h2":      int(_d_g.get("dias_extra_h2", 0)),
            "h0_weekday_count":   int(_d_g.get("h0_weekday_count", 0)),
            "n_light_h1":         int(_d_g.get("n_light_h1", 0)),
            "n_light_h2":         int(_d_g.get("n_light_h2", 0)),
            "emisiones_totales":  round(_E_g, 1),
            "velocidad_promedio": round(_vbpr_g, 2),
            "impacto_economico":  round(_IE_g / 1000, 1),   # en miles de viajes
        })

        if mejor_fit_gen > best_fit:
            best_fit, best_ind = float(mejor_fit_gen), mejor_ind_gen[:]

        if float(mejor_fit_gen) > prev_best + 1e-8:
            prev_best          = float(mejor_fit_gen)
            stagnacion_counter = 0
            restart_counter    = 0
        else:
            stagnacion_counter += 1
            restart_counter    += 1

        # ── Reinicio con memoria (mecanismo interno anti-convergencia) ─────────
        if restart_counter >= restart_umbral:
            n_keep    = max(1, int(pop_size * restart_keep_pct))
            keep_idx  = heapq.nlargest(n_keep, range(len(poblacion)),
                                       key=aptitudes_lista.__getitem__)
            keep_inds = [poblacion[i][:] for i in keep_idx]
            if best_ind:
                keep_inds[0] = best_ind[:]
            nueva_pob       = keep_inds + FuncionInicializacion(pop_size - n_keep)
            aptitudes_nueva = [eval_ind(ind) for ind in nueva_pob]
            poblacion, div_actual = FuncionPoda(
                nueva_pob, aptitudes_nueva, pop_size,
                estrategia_poda=estrategia_poda,
            )
            stagnacion_counter = 0
            restart_counter    = 0
            continue

        # ── Adaptación de la tasa de mutación según estancamiento ───────────
        factor_adapt         = min(1.0, stagnacion_counter / max(1, stagnacion_umbral))
        prob_mutacion_actual = prob_mutacion + (mutacion_max - prob_mutacion) * factor_adapt
        # La escala gaussiana también crece con el estancamiento
        escala_mut = 0.04 + 0.10 * factor_adapt   # 0.04 → 0.14

        # ── Generación de descendencia según estrategia de poda ─────────────
        if estrategia_poda == "generacional":
            # Poda generacional: la descendencia reemplaza completamente a los padres.
            # Solo el mejor individuo global siempre sobrevive (evitar regresión).
            nueva = [best_ind[:]] if best_ind else []
            while len(nueva) < pop_size:
                p1 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
                p2 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
                h1, h2 = FuncionCruza(p1, p2, prob_cruza, estrategia_cruza)
                nueva.append(FuncionMutacion(h1, prob_mutacion_actual, estrategia_mutacion, escala_mut))
                if len(nueva) < pop_size:
                    nueva.append(FuncionMutacion(h2, prob_mutacion_actual, estrategia_mutacion, escala_mut))
            aptitudes_nueva = [eval_ind(ind) for ind in nueva]
            poblacion, div_actual = FuncionPoda(
                nueva, aptitudes_nueva, pop_size,
                estrategia_poda="generacional",
            )

        elif estrategia_poda == "estado_estacionario":
            # Estado estacionario: solo se reemplazan los K peores miembros por
            # descendientes mejores. La mayoría de la población sobrevive.
            n_reemplazo = max(2, pop_size // 8)
            descendencia = []
            while len(descendencia) < n_reemplazo:
                p1 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
                p2 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
                h1, h2 = FuncionCruza(p1, p2, prob_cruza, estrategia_cruza)
                descendencia.append(FuncionMutacion(h1, prob_mutacion_actual, estrategia_mutacion, escala_mut))
                if len(descendencia) < n_reemplazo:
                    descendencia.append(FuncionMutacion(h2, prob_mutacion_actual, estrategia_mutacion, escala_mut))
            apt_desc   = [eval_ind(ind) for ind in descendencia]
            # Reemplaza solo los peores con los mejores descendientes
            peor_idx   = sorted(range(len(poblacion)), key=lambda i: aptitudes_lista[i])[:n_reemplazo]
            nueva      = poblacion[:]
            apt_nueva  = list(aptitudes_lista)
            for idx, ind, apt in zip(peor_idx, descendencia, apt_desc):
                if apt > aptitudes_lista[idx]:
                    nueva[idx]   = ind
                    apt_nueva[idx] = apt
            poblacion, div_actual = FuncionPoda(
                nueva, apt_nueva, pop_size,
                estrategia_poda="estado_estacionario",
                poblacion_actual=poblacion, aptitudes_actual=apt_nueva,
            )

        else:  # elitismo (default)
            # Elitismo: los mejores N individuos siempre sobreviven a la siguiente
            # generación. El resto se rellena con la mejor descendencia.
            elite_count = min(len(poblacion), max(1, elitismo))
            elite_idx   = heapq.nlargest(elite_count, range(len(poblacion)),
                                         key=aptitudes_lista.__getitem__)
            elite = [poblacion[i][:] for i in elite_idx]
            nueva = list(elite)

            inyectar = (stagnacion_counter >= stagnacion_umbral) or (div_actual < diversidad_minima)
            if inyectar:
                n_inject = max(1, int(pop_size * inyeccion_pct))
                nueva.extend(FuncionInicializacion(n_inject))

            while len(nueva) < pop_size:
                p1 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
                p2 = FuncionGeneracionParejas(poblacion, aptitudes_lista, estrategia_seleccion)
                h1, h2 = FuncionCruza(p1, p2, prob_cruza, estrategia_cruza)
                nueva.append(FuncionMutacion(h1, prob_mutacion_actual, estrategia_mutacion, escala_mut))
                if len(nueva) < pop_size:
                    nueva.append(FuncionMutacion(h2, prob_mutacion_actual, estrategia_mutacion, escala_mut))

            aptitudes_nueva = [eval_ind(ind) for ind in nueva]
            poblacion, div_actual = FuncionPoda(
                nueva, aptitudes_nueva, pop_size,
                estrategia_poda="elitismo",
            )

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
        contaminacion_i = contamination_for_month(month_i, nivel_imeca)
        factor_i        = contamination_to_factor(contaminacion_i)

        # ── Multi-run: corre el AG N veces y conserva el mejor resultado ────
        # Cada corrida parte de una población aleatoria distinta (diferente semilla).
        # Esto garantiza que si una corrida queda atrapada en un óptimo local,
        # las otras tienen la oportunidad de encontrar algo mejor.
        _ag_kwargs = dict(
            factor_mensual=factor_i, factor_sabado=factor_sabado,
            total_sabados=total_sab_i, nivel_imeca=nivel_imeca,
            pop_size=pop_size, generaciones=generaciones,
            prob_cruza=prob_cruza, prob_mutacion=prob_mutacion, elitismo=elitismo,
            estrategia_seleccion=str(merged.get("estrategia_seleccion", "torneo")),
            estrategia_cruza=str(merged.get("estrategia_cruza", "multipunto")),
            estrategia_mutacion=str(merged.get("estrategia_mutacion", "gaussiana")),
            estrategia_poda=str(merged.get("estrategia_poda", "elitismo")),
            entorno=entorno,
            peso_ambiental=float(merged.get("peso_ambiental_critico", 2.2)),
            peso_economico=float(merged.get("peso_economico", 1.55)),
            peso_equidad=float(merged.get("peso_equidad", 1.0)),
        )
        n_runs  = int(merged.get("n_runs", 2))   # 2 corridas independientes por mes
        ag_result = ejecutar_algoritmo_genetico(**_ag_kwargs)
        for _ in range(n_runs - 1):
            _r2 = ejecutar_algoritmo_genetico(**_ag_kwargs)
            if _r2["mejor_fitness"] > ag_result["mejor_fitness"]:
                ag_result = _r2   # conserva el historial de la mejor corrida
        # ─────────────────────────────────────────────────────────────────────
        fitness_acumulado.append(ag_result["mejor_fitness"])
        mejor_ind    = ag_result["mejor_individuo"]
        decoded      = decodificar_individuo(mejor_ind, total_sab_i, nivel_imeca)
        color_to_day = decoded["color_dia_final"]
        _weekdays_i = sum(1 for w in monthcalendar(year_i, month_i) for d in w[:5] if d != 0)
        _h2_cd_i = (FLOTA_TOTAL*0.55/5*_weekdays_i)
        _h1_cd_i = (FLOTA_TOTAL*0.40/5*_weekdays_i)
        _co2_i   = (_h2_cd_i + _h1_cd_i) * CO2_KG * EFFECTIVENESS / 1000
        _co2_base_i = (_h2_cd_i + _h1_cd_i) * CO2_KG / 1000  # sin restricción (sin efectividad)
        _autos_i = (_h2_cd_i + _h1_cd_i) / days_in_month(year_i, month_i) / 1e6
        # Costo económico estimado: días restringidos × costo por vehículo × cumplimiento
        _cum_i   = float(entorno.get("cumplimiento_ciudadano", 0.85))
        _veh     = entorno.get("vehiculos", {})
        _costo_i = round((
            float(_veh.get("H1", {}).get("total", FLOTA_TOTAL*0.40)) * (_weekdays_i/5)
            * float(_veh.get("H1", {}).get("p_l", 0.29)) * float(_veh.get("H1", {}).get("costo", 1.0)) * _cum_i
            + float(_veh.get("H2", {}).get("total", FLOTA_TOTAL*0.55)) * (_weekdays_i/5)
            * float(_veh.get("H2", {}).get("p_l", 0.28)) * float(_veh.get("H2", {}).get("costo", 0.85)) * _cum_i
        ) * 150 / 1_000_000, 1)  # 150 pesos por viaje → millones MXN

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
            "historial_mejor":         ag_result.get("historial_fitness", []),
            "historial_peor":          ag_result.get("historial_peor", []),
            "historial_promedio":      ag_result.get("historial_promedio", []),
            "historial_vars":          ag_result.get("historial_vars", []),
            "variables_optimas":       decoded["decisiones_ag"],
            "co2_evitado_ton":         round(_co2_i, 1),
            "co2_base_ton":            round(_co2_base_i, 1),
            "autos_dia_millones":      round(_autos_i, 3),
            "costo_economico_millones": _costo_i,
            "nivel_imeca_efectivo":    nivel_imeca,
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