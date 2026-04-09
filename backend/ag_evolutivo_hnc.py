import json
import itertools
import math
import random
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# CONFIGURACIÓN Y REGLAS BASE DEL HNC
# ============================================================================
# 11 genes base + 5 genes de asignacion color->dia
# Gen  0-3 : niveles teóricos de restricción (R_H00, R_H0, R_H1, R_H2)
# Gen  4   : hora_fin_h1        (< 0.4 → 16h, si no → 22h)
# Gen  5   : hora_fin_h2        (< 0.15 → 16h, si no → 22h)
# Gen  6   : zona_h1            (< 0.6 → centro, si no → total)
# Gen  7   : zona_h2            (< 0.2 → centro, si no → total)
# Gen  8   : sabados_h1         (0 – 3)
# Gen  9   : sabados_h2         (3 – total_sab del mes)
# Gen 10   : extras_h2          (0 – 3 fechas adicionales para H2)
# Gen 11-15: color → día        (5 colores)
GENES = 16
DEFAULT_POP_SIZE = 100
DEFAULT_GENERATIONS = 120

DEFAULT_PARAMS = {
    "pop_size": 100,
    "generaciones": 120,
    "mutacion": 0.05,
    "elitismo": 2,
    "peso_equidad": 1,
    "peso_ambiental_critico": 2.2,
    "peso_economico": 1.55,
    "nivel_imeca": 150,
    "start_month": "2026-04",
    "meses": 6,
}

GRUPOS_PLACA = {
    "Amarillo": [5, 6], "Rosa": [7, 8], "Rojo": [3, 4],
    "Verde": [1, 2], "Azul": [9, 0],
}
HOLOGRAMAS = ["H00", "H0", "H1", "H2"]
LOWER_DIA = {
    "Lunes": "lunes",
    "Martes": "martes",
    "Miércoles": "miercoles",
    "Jueves": "jueves",
    "Viernes": "viernes",
}
WEEKDAY_INDEX = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
}
COLOR_ORDER = ["Verde", "Amarillo", "Rosa", "Rojo", "Azul"]
LOWER_TO_TITULO = {
    "lunes": "Lunes",
    "martes": "Martes",
    "miercoles": "Miércoles",
    "jueves": "Jueves",
    "viernes": "Viernes",
}
DIAS_SEMANA_LOWER = ["lunes", "martes", "miercoles", "jueves", "viernes"]

# ============================================================================
# FACTORES DE CONTAMINACIÓN — mapeo nivel → peso para el AG
# ============================================================================
CONTAMINATION_FACTORS: Dict[str, float] = {
    "baja":   0.50,   # poca contaminación → AG prioriza economía
    "normal": 1.00,   # contaminación media → balance
    "alta":   1.80,   # alta contaminación → AG prioriza ambiente
}

# Rangos válidos de sábados por holograma/contaminación (según reglas HNC)
SABADOS_RANGOS = {
    # (contaminacion, holograma) -> (min, max)
    ("alta",   "H1"): (2, 3),
    ("normal", "H1"): (1, 3),
    ("baja",   "H1"): (1, 2),
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTORNO_PATH = PROJECT_ROOT / "data" / "entorno_cdmx.json"


# ============================================================================
# UTILIDADES GENERALES
# ============================================================================
def contamination_to_factor(contaminacion: str) -> float:
    """Convierte nivel de contaminación en factor para la función de fitness."""
    return CONTAMINATION_FACTORS.get(contaminacion, 1.0)


def dia_base_por_defecto(color: str) -> str:
    indice = COLOR_ORDER.index(color)
    return DIAS_SEMANA_LOWER[indice]

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def parse_year_month(value: str) -> Tuple[int, int]:
    year_str, month_str = value.split("-")
    return int(year_str), int(month_str)


def add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


def days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - date(year, month, 1)).days


def total_saturdays(year: int, month: int) -> int:
    total = 0
    for d in range(1, days_in_month(year, month) + 1):
        if date(year, month, d).weekday() == 5:
            total += 1
    return total


def nth_weekday_dates(year: int, month: int, weekday: int, count: int) -> List[str]:
    matches: List[str] = []
    for d in range(1, days_in_month(year, month) + 1):
        current = date(year, month, d)
        if current.weekday() == weekday:
            matches.append(current.isoformat())
            if len(matches) >= count:
                break
    return matches


def contamination_for_month(month: int, nivel_imeca: float) -> str:
    if nivel_imeca >= 220:
        return "alta"
    if nivel_imeca <= 90:
        return "baja"
    if month in (5, 6):
        return "alta"
    if month in (7, 8):
        return "baja"
    return "normal"


def sat_list(total_sab: int, wanted: int) -> List[int]:
    return list(range(1, min(total_sab, wanted) + 1))


def cargar_entorno_cdmx() -> Dict[str, Any]:
    """Carga el entorno generado por el ETL, si existe."""
    if not ENTORNO_PATH.exists():
        return {}
    try:
        with ENTORNO_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resumen_probabilidad_sabado(entorno: Dict[str, Any]) -> float:
    """Resume la tabla de sábado en un factor escalar para la fitness."""
    sabado = entorno.get("probabilidad_laboral_sabado_horaria", {}) if isinstance(entorno, dict) else {}
    if not isinstance(sabado, dict) or not sabado:
        return 1.0

    valores = []
    for v in sabado.values():
        if isinstance(v, dict) and "probabilidad_laboral" in v:
            try:
                valores.append(float(v["probabilidad_laboral"]))
            except (TypeError, ValueError):
                continue

    if not valores:
        return 1.0

    promedio = sum(valores) / len(valores)
    return clamp01(promedio / 0.5)


def reparar_asignacion_colores_dias(propuesta: Dict[str, str]) -> Dict[str, str]:
    """Repara una propuesta color->dia para que no haya dias repetidos."""
    usados = set()
    resultado: Dict[str, str] = {}
    disponibles = set(DIAS_SEMANA_LOWER)

    for color in COLOR_ORDER:
        dia = propuesta.get(color, dia_base_por_defecto(color))
        if dia not in DIAS_SEMANA_LOWER:
            dia = dia_base_por_defecto(color)

        if dia not in usados:
            resultado[color] = dia
            usados.add(dia)
            disponibles.discard(dia)
            continue

        dia_default = dia_base_por_defecto(color)
        if dia_default in disponibles:
            resultado[color] = dia_default
            usados.add(dia_default)
            disponibles.discard(dia_default)
        else:
            nuevo = sorted(disponibles)[0]
            resultado[color] = nuevo
            usados.add(nuevo)
            disponibles.discard(nuevo)

    return resultado


def generar_asignaciones_mensuales_desde_base(
    base_map: Dict[str, str],
    meses_count: int,
    semilla: int,
) -> List[Dict[str, str]]:
    """Genera asignaciones color->dia distintas por mes sin repetir configuraciones."""
    dias = DIAS_SEMANA_LOWER[:]
    base_tuple = tuple(base_map[color] for color in COLOR_ORDER)

    todas = list(itertools.permutations(dias, len(COLOR_ORDER)))
    rng = random.Random(semilla)
    rng.shuffle(todas)

    seleccion_tuplas: List[Tuple[str, ...]] = [base_tuple]
    usadas = {base_tuple}

    for perm in todas:
        if perm in usadas:
            continue
        prev = seleccion_tuplas[-1]
        if all(perm[i] == prev[i] for i in range(len(COLOR_ORDER))):
            continue
        seleccion_tuplas.append(perm)
        usadas.add(perm)
        if len(seleccion_tuplas) >= meses_count:
            break

    while len(seleccion_tuplas) < meses_count:
        idx = len(seleccion_tuplas) % len(COLOR_ORDER)
        rot = tuple(dias[idx:] + dias[:idx])
        if rot not in usadas:
            seleccion_tuplas.append(rot)
            usadas.add(rot)
        else:
            for perm in todas:
                if perm not in usadas:
                    seleccion_tuplas.append(perm)
                    usadas.add(perm)
                    break
            else:
                seleccion_tuplas.append(rot)

    asignaciones: List[Dict[str, str]] = []
    for perm in seleccion_tuplas[:meses_count]:
        asignaciones.append({color: perm[i] for i, color in enumerate(COLOR_ORDER)})
    return asignaciones


# ============================================================================
# CONSTRUCCIÓN DE REGLAS POR MES — ahora usa decisiones del AG
# ============================================================================
def construir_reglas_mes(
    year: int,
    month: int,
    contaminacion: str,
    color_to_day_lower: Dict[str, str],
    ag_decisions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construye las reglas de restricción para un mes dado aplicando las
    decisiones evolucionadas por el AG.

    Rangos que el AG controla:
      H1  sábados : 0 – 3          (guiado por factor_mensual en fitness)
      H2  sábados : 3 – total_sab  (mín garantizado = 3)
      H2  extras  : 0 – 3 fechas adicionales (independiente de sábados)
    """
    total_sab = total_saturdays(year, month)

    # ── Defaults de fallback (sin AG) ─────────────────────────────────────
    if contaminacion == "alta":
        h1_def_hora, h1_def_zona, h1_def_sab = 22, "total", 2
        h2_def_hora, h2_def_zona = 22, "total"
        h2_def_sab   = total_sab
        def_extras   = 1
    elif contaminacion == "baja":
        h1_def_hora, h1_def_zona, h1_def_sab = 16, "centro", 1
        h2_def_hora, h2_def_zona = 16, "centro"
        h2_def_sab   = min(3, total_sab)
        def_extras   = 0
    else:  # normal
        h1_def_hora, h1_def_zona, h1_def_sab = 22, "total", 2
        h2_def_hora, h2_def_zona = 22, "total"
        h2_def_sab   = total_sab
        def_extras   = 0

    # ── Aplicar decisiones del AG (o usar defaults si no hay AG) ──────────
    if ag_decisions:
        # H1
        h1_horario = [5, int(ag_decisions.get("hora_fin_h1", h1_def_hora))]
        zona_raw   = str(ag_decisions.get("zona_h1", h1_def_zona)).lower()
        h1_zona    = "total" if "total" in zona_raw else "centro"
        # H1 sábados: AG decide 0–3, validado para no superar el mes
        h1_sab = max(0, min(int(ag_decisions.get("sabados_h1", h1_def_sab)), 3))
        h1_sab = min(h1_sab, total_sab)

        # H2
        h2_horario = [5, int(ag_decisions.get("hora_fin_h2", h2_def_hora))]
        zona_raw2  = str(ag_decisions.get("zona_h2", h2_def_zona)).lower()
        h2_zona    = "total" if "total" in zona_raw2 else "centro"
        # H2 sábados: AG decide 3–total_sab
        h2_sab = max(3, min(int(ag_decisions.get("sabados_h2", h2_def_sab)), total_sab))
        # H2 extras: AG decide 0–2 (independiente, sin restricción por contaminación)
        extras_per_color = max(0, min(int(ag_decisions.get("dias_extra_h2", def_extras)), 2))
    else:
        # Modo legado / sin AG
        h1_horario       = [5, h1_def_hora]
        h1_zona          = h1_def_zona
        h1_sab           = h1_def_sab
        h2_horario       = [5, h2_def_hora]
        h2_zona          = h2_def_zona
        h2_sab           = h2_def_sab
        extras_per_color = def_extras

    # ── Construir reglas por color ─────────────────────────────────────────
    h1_por_color: Dict[str, Any] = {}
    h2_por_color: Dict[str, Any] = {}

    for color in COLOR_ORDER:
        dia_base = color_to_day_lower.get(color, dia_base_por_defecto(color))
        h1_por_color[color] = {
            "dia_base": dia_base,
            "sabados": sat_list(total_sab, h1_sab),
            "horario": h1_horario,
            "zona": h1_zona,
        }

        h2_item: Dict[str, Any] = {
            "dia_base": dia_base,
            "sabados": sat_list(total_sab, h2_sab),
            "horario": h2_horario,
            "zona": h2_zona,
        }

        if extras_per_color > 0:
            weekday = WEEKDAY_INDEX[dia_base]
            extra_weekday = (weekday + 1) % 5
            h2_item["extras"] = nth_weekday_dates(year, month, extra_weekday, extras_per_color)

        h2_por_color[color] = h2_item

    # ── Consistencia de extras ─────────────────────────────────────────────
    if extras_per_color > 0:
        for color in COLOR_ORDER:
            cfg = h2_por_color[color]
            extras = list(cfg.get("extras", []))

            if len(extras) < extras_per_color:
                weekday = WEEKDAY_INDEX[color_to_day_lower.get(color, dia_base_por_defecto(color))]
                weekday = (weekday + 1) % 5
                filler = nth_weekday_dates(year, month, weekday, extras_per_color)
                extras = (extras + filler)[:extras_per_color]

            cfg["extras"] = extras[:extras_per_color]

            dia_base = color_to_day_lower.get(color, dia_base_por_defecto(color))
            filtradas: List[str] = []
            for iso in cfg["extras"]:
                y, m, d = (int(x) for x in iso.split("-"))
                wd = DIAS_SEMANA_LOWER[date(y, m, d).weekday()]
                if wd != dia_base:
                    filtradas.append(iso)

            while len(filtradas) < extras_per_color:
                wd_idx = (WEEKDAY_INDEX[dia_base] + 1) % 5
                candidatos = nth_weekday_dates(year, month, wd_idx, extras_per_color + 2)
                for c in candidatos:
                    if c not in filtradas:
                        filtradas.append(c)
                    if len(filtradas) >= extras_per_color:
                        break

            cfg["extras"] = filtradas[:extras_per_color]

    return {
        "mes": month,
        "year": year,
        "contaminacion": contaminacion,
        "h00": "libre",
        "h0": "libre",
        "h1": {"por_color": h1_por_color},
        "h2": {"por_color": h2_por_color},
    }


# ============================================================================
# DECODIFICACIÓN DEL ADN
# ============================================================================
def generar_individuo() -> List[float]:
    return [random.random() for _ in range(GENES)]


def decodificar_individuo(individuo: List[float], total_sabados_mes: int = 4) -> Dict[str, Any]:
    """
    Decodifica el cromosoma del AG en decisiones concretas de restricción.

    Sábados H1  : el AG elige libremente 0–3 (el factor de contaminación en
                  la función de fitness lo guía al rango adecuado).
    Sábados H2  : el AG elige entre 3 y total_sabados_mes (mín 3, máx 4 ó 5
                  según el mes).
    Extras H2   : el AG elige 0–3 fechas adicionales, de forma independiente
                  a los sábados.
    """
    # ── Genes 0-3: niveles teóricos de restricción ────────────────────────
    r_h00, r_h0, r_h1, r_h2 = sorted(float(g) for g in individuo[0:4])

    # ── Gene 4: hora fin H1 ───────────────────────────────────────────────
    hora_fin_h1 = 16 if individuo[4] < 0.4 else 22

    # ── Gene 5: hora fin H2 ───────────────────────────────────────────────
    hora_fin_h2 = 16 if individuo[5] < 0.15 else 22

    # ── Gene 6: zona H1 ───────────────────────────────────────────────────
    zona_h1 = "Centro" if individuo[6] < 0.6 else "Total"

    # ── Gene 7: zona H2 ───────────────────────────────────────────────────
    zona_h2 = "Centro" if individuo[7] < 0.2 else "Total"

    # ── Gene 8: sábados H1  →  0, 1, 2 ó 3 ──────────────────────────────
    # El gene [0,1] se mapea a 4 niveles; se limita a los sábados reales.
    val_s1 = individuo[8]
    sabados_h1 = min(3, int(val_s1 * 4))       # 0·25·50·75 → 0·1·2·3
    sabados_h1 = min(sabados_h1, total_sabados_mes)

    # ── Gene 9: sábados H2  →  3 … total_sab ─────────────────────────────
    # Mínimo garantizado: 3.  Máximo: todos los sábados del mes (4 ó 5).
    val_s2 = individuo[9]
    rango_h2 = max(0, total_sabados_mes - 3)    # cuántos pasos sobre el mínimo
    sabados_h2 = 3 + min(rango_h2, int(val_s2 * (rango_h2 + 1)))
    sabados_h2 = max(3, min(sabados_h2, total_sabados_mes))

    # ── Gene 10: extras H2  →  0, 1 ó 2 fechas adicionales ─────────────
    # Completamente independiente de los sábados; el AG decide cuántas
    # fechas extra aplica H2 más allá de los sábados (máximo 2).
    val_ex = individuo[10] if len(individuo) > 10 else 0.0
    dias_extra_h2 = min(2, int(val_ex * 3))     # 0·1·2

    # ── Genes 11-15: color → día de la semana ─────────────────────────────
    propuesta_color_dia: Dict[str, str] = {}
    for idx, color in enumerate(COLOR_ORDER):
        g = individuo[11 + idx] if (11 + idx) < len(individuo) else 0.0
        day_idx = min(4, int(float(g) * 5.0))
        propuesta_color_dia[color] = DIAS_SEMANA_LOWER[day_idx]

    repetidos_pre = len(propuesta_color_dia.values()) - len(set(propuesta_color_dia.values()))
    asignacion_reparada = reparar_asignacion_colores_dias(propuesta_color_dia)

    return {
        "R_H00": r_h00, "R_H0": r_h0, "R_H1": r_h1, "R_H2": r_h2,
        "color_dia_propuesta": propuesta_color_dia,
        "color_dia_final": asignacion_reparada,
        "violaciones_pre_reparacion": {
            "dias_repetidos": max(0, repetidos_pre),
        },
        "decisiones_ag": {
            "hora_fin_h1": hora_fin_h1,
            "hora_fin_h2": hora_fin_h2,
            "zona_h1": zona_h1,
            "zona_h2": zona_h2,
            "sabados_h1": sabados_h1,
            "sabados_h2": sabados_h2,
            "dias_extra_h2": dias_extra_h2,
        },
    }


# ============================================================================
# FUNCIÓN DE FITNESS — recibe el contexto real del mes
# ============================================================================
def funcion_objetivo(
    individuo: List[float],
    factor_mensual: float,
    factor_sabado: float = 1.0,
    total_sabados: int = 4,
) -> float:
    """
    Evalúa un cromosoma con el contexto real del mes.

    Lógica rediseñada:
      beneficio = nivel_restriccion × factor_mensual   → sube con contaminación
      costo     = cuadrático en restricciones           → penaliza el exceso
      factor_costo = mayor cuando contaminación es baja → el costo económico
                     pesa más, inhibiendo las restricciones innecesarias

    Comportamiento esperado:
      baja  (0.5) → H1 sin sábados o 1, H2 mínimo (3 sábs), 0 extras
      normal(1.0) → H1 1-2 sábs, H2 todos los sábs, 0-1 extras
      alta  (1.8) → H1 2-3 sábs, H2 todos los sábs, 1-2 extras
    """
    sol  = decodificar_individuo(individuo, total_sabados)
    d_ag = sol["decisiones_ag"]

    sab_h1 = d_ag["sabados_h1"]     # 0 – 3
    sab_h2 = d_ag["sabados_h2"]     # 3 – total_sab
    extras = d_ag["dias_extra_h2"]  # 0 – 2

    # ── Restricción normalizada [0, 1] ────────────────────────────────────
    # H2 base (3 sábs) es obligatorio; solo contamos lo que el AG agrega
    # sobre ese mínimo para no distorsionar el costo.
    h2_extra_sats = sab_h2 - 3
    h2_max_extra  = max(1, total_sabados - 3)   # 1 si mes tiene 4 sábs, 2 si tiene 5

    W_H1, W_H2, W_EX = 0.30, 0.35, 0.35
    nivel_restriccion = (
          (sab_h1        / 3.0)            * W_H1
        + (h2_extra_sats / h2_max_extra)   * W_H2
        + (extras        / 2.0)            * W_EX
    )

    # ── Beneficio ambiental ───────────────────────────────────────────────
    # A mayor contaminación, cada punto de restricción aporta más beneficio.
    beneficio = nivel_restriccion * factor_mensual * 2.5

    # ── Costo económico (cuadrático) ──────────────────────────────────────
    # La potencia 1.5 encarece rápidamente los niveles altos de restricción;
    # H2 extra-sábados y extras de H2 cuestan más que H1 porque afectan
    # días con mayor actividad (sábados laborales y días hábiles extra).
    costo = (
          (sab_h1        ** 1.5) * 0.08
        + (h2_extra_sats ** 1.5) * 0.40
        + (extras        ** 1.5) * 0.35
    )
    # El ETL informa qué tan laborales son los sábados en CDMX;
    # a mayor actividad laboral en sábado, más caro restringir.
    costo *= 1.0 + (factor_sabado - 1.0) * 0.40

    # ── Multiplicador de costo: inversamente proporcional a contaminación ─
    # Con poca contaminación el beneficio ambiental es bajo pero el costo
    # económico permanece alto → el AG aprende a restringir menos.
    # baja (0.5)  → factor_costo ≈ 1.72
    # normal(1.0) → factor_costo ≈ 1.44
    # alta (1.8)  → factor_costo = 1.00
    factor_costo = 2.0 - clamp01(factor_mensual / 1.8)

    # ── Fitness final (puede ser negativo: el AG selecciona por ranking) ──
    fitness = (beneficio - costo * factor_costo) * 1000.0

    # ── Penalización por días repetidos ───────────────────────────────────
    dias_repetidos = int(sol.get("violaciones_pre_reparacion", {}).get("dias_repetidos", 0))
    if dias_repetidos:
        fitness -= 500.0 * dias_repetidos

    return float(fitness)


def aptitud(
    individuo: List[float],
    factor_mensual: float,
    factor_sabado: float = 1.0,
    total_sabados: int = 4,
) -> float:
    return funcion_objetivo(individuo, factor_mensual, factor_sabado, total_sabados)


# ============================================================================
# OPERADORES GENÉTICOS
# ============================================================================
def seleccionar_padre_ruleta(poblacion: List[List[float]], aptitudes: List[float]) -> List[float]:
    minimo = min(aptitudes)
    offset = abs(minimo) + 1e-9 if minimo < 0 else 0.0
    ajustadas = [a + offset for a in aptitudes]
    total = sum(ajustadas)

    if total <= 0:
        return random.choice(poblacion)[:]

    r = random.uniform(0.0, total)
    acumulado = 0.0
    for ind, fit in zip(poblacion, ajustadas):
        acumulado += fit
        if acumulado >= r:
            return ind[:]
    return poblacion[-1][:]


def cruza_un_punto(
    padre1: List[float], padre2: List[float], prob_cruza: float
) -> Tuple[List[float], List[float]]:
    if random.random() >= prob_cruza:
        return padre1[:], padre2[:]
    punto = random.randint(1, GENES - 1)
    hijo1 = padre1[:punto] + padre2[punto:]
    hijo2 = padre2[:punto] + padre1[punto:]
    return hijo1, hijo2


def mutar(individuo: List[float], prob_mutacion: float) -> List[float]:
    mutado = []
    for g in individuo:
        if random.random() < prob_mutacion:
            g = clamp01(g + random.uniform(-0.1, 0.1))
        mutado.append(g)
    return mutado


def poda(
    poblacion: List[List[float]],
    factor_mensual: float,
    factor_sabado: float,
    total_sabados: int,
    tam_objetivo: int,
) -> List[List[float]]:
    ranking = sorted(
        poblacion,
        key=lambda ind: aptitud(ind, factor_mensual, factor_sabado, total_sabados),
        reverse=True,
    )
    return [ind[:] for ind in ranking[:tam_objetivo]]


# ============================================================================
# MOTOR EVOLUTIVO — ahora recibe el contexto real del mes
# ============================================================================
def ejecutar_algoritmo_genetico(
    factor_mensual: float,
    factor_sabado: float = 1.0,
    total_sabados: int = 4,
    pop_size: int = DEFAULT_POP_SIZE,
    generaciones: int = DEFAULT_GENERATIONS,
    prob_cruza: float = 0.85,
    prob_mutacion: float = 0.05,
    elitismo: int = 2,
) -> Dict[str, Any]:
    """
    Ejecuta el AG para un contexto de mes concreto:
    - factor_mensual: peso ambiental (alto = meses con más contaminación)
    - total_sabados: número real de sábados en el mes
    """
    poblacion = [generar_individuo() for _ in range(pop_size)]
    best_fit = -math.inf
    best_ind: List[float] = []
    historial: List[float] = []

    for _ in range(generaciones):
        aptitudes_lista = [
            aptitud(ind, factor_mensual, factor_sabado, total_sabados)
            for ind in poblacion
        ]
        ranking = sorted(zip(poblacion, aptitudes_lista), key=lambda x: x[1], reverse=True)

        mejor_gen_ind, mejor_gen_fit = ranking[0]
        historial.append(float(mejor_gen_fit))

        if mejor_gen_fit > best_fit:
            best_fit = float(mejor_gen_fit)
            best_ind = mejor_gen_ind[:]

        nueva_poblacion: List[List[float]] = [ind[:] for ind, _ in ranking[: max(1, elitismo)]]

        while len(nueva_poblacion) < pop_size:
            p1 = seleccionar_padre_ruleta(poblacion, aptitudes_lista)
            p2 = seleccionar_padre_ruleta(poblacion, aptitudes_lista)
            h1, h2 = cruza_un_punto(p1, p2, prob_cruza)
            nueva_poblacion.append(mutar(h1, prob_mutacion))
            if len(nueva_poblacion) < pop_size:
                nueva_poblacion.append(mutar(h2, prob_mutacion))

        poblacion = poda(nueva_poblacion, factor_mensual, factor_sabado, total_sabados, pop_size)

    return {
        "mejor_fitness": float(best_fit),
        "mejor_individuo": best_ind,
        "historial_fitness": historial,
    }


def evolucionar(
    factor_mensual: float,
    params: Optional[Dict[str, Any]] = None,
    total_sabados: int = 4,
) -> Dict[str, Any]:
    """Wrapper de compatibilidad con el nombre anterior."""
    cfg = params or {}
    entorno = cargar_entorno_cdmx()
    factor_sabado = resumen_probabilidad_sabado(entorno)
    return ejecutar_algoritmo_genetico(
        factor_mensual=factor_mensual,
        factor_sabado=factor_sabado,
        total_sabados=total_sabados,
        pop_size=int(cfg.get("pop_size", DEFAULT_POP_SIZE)),
        generaciones=int(cfg.get("generaciones", DEFAULT_GENERATIONS)),
        prob_cruza=0.85,
        prob_mutacion=float(cfg.get("mutacion", 0.05)),
        elitismo=int(cfg.get("elitismo", 2)),
    )


# ============================================================================
# GENERACIÓN DEL JSON FINAL — AG dinámico por mes
# ============================================================================
def generar_json_final(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Genera el calendario óptimo de restricciones HNC.

    Cambios dinámicos respecto a la versión anterior:
    - El AG se ejecuta de forma independiente para cada mes.
    - Cada ejecución usa el factor_mensual correspondiente al nivel de
      contaminación real de ese mes (baja/normal/alta).
    - El número real de sábados del mes se pasa al AG para que lo tome en
      cuenta en la evolución.
    - Las decisiones evolucionadas (horario, zona, sábados) se aplican
      directamente en las reglas de ese mes, dentro de los límites válidos
      del nivel de contaminación.
    - Las asignaciones color→día se diversifican automáticamente para que
      cada mes tenga una rotación diferente.
    """
    merged = {**DEFAULT_PARAMS, **(params or {})}
    entorno = cargar_entorno_cdmx()
    factor_sabado = resumen_probabilidad_sabado(entorno)

    start_year, start_month = parse_year_month(str(merged["start_month"]))
    meses_count = max(1, int(merged["meses"]))
    nivel_imeca = float(merged["nivel_imeca"])

    pop_size       = int(merged["pop_size"])
    generaciones   = int(merged["generaciones"])
    prob_mutacion  = float(merged["mutacion"])
    elitismo       = int(merged["elitismo"])

    meses_out: List[Dict[str, Any]] = []
    fitness_acumulado: List[float] = []
    used_color_day_tuples: set = set()   # garantiza diversidad de rotaciones

    for i in range(meses_count):
        year_i, month_i = add_months(start_year, start_month, i)
        total_sab_i = total_saturdays(year_i, month_i)
        contaminacion_i = contamination_for_month(month_i, nivel_imeca)
        factor_i = contamination_to_factor(contaminacion_i)

        # ── Ejecutar AG con contexto real de este mes ────────────────────
        ag_result = ejecutar_algoritmo_genetico(
            factor_mensual=factor_i,
            factor_sabado=factor_sabado,
            total_sabados=total_sab_i,
            pop_size=pop_size,
            generaciones=generaciones,
            prob_cruza=0.85,
            prob_mutacion=prob_mutacion,
            elitismo=elitismo,
        )

        fitness_acumulado.append(ag_result["mejor_fitness"])
        mejor_ind = ag_result["mejor_individuo"]

        # ── Decodificar decisiones evolucionadas ─────────────────────────
        decoded = decodificar_individuo(mejor_ind, total_sab_i)
        color_to_day = decoded["color_dia_final"]
        ag_decisions = decoded["decisiones_ag"]

        # ── Garantizar rotación única de color→día por mes ───────────────
        tuple_i = tuple(color_to_day[c] for c in COLOR_ORDER)
        if tuple_i in used_color_day_tuples:
            # Generar alternativas con semilla derivada del individuo + posición
            semilla = int(sum(float(g) for g in mejor_ind) * 1_000_000) + i * 7919
            alternativas = generar_asignaciones_mensuales_desde_base(
                color_to_day, meses_count * 2 + 5, semilla
            )
            for alt in alternativas[1:]:   # [0] es la misma base, saltar
                alt_tuple = tuple(alt[c] for c in COLOR_ORDER)
                if alt_tuple not in used_color_day_tuples:
                    color_to_day = alt
                    tuple_i = alt_tuple
                    break

        used_color_day_tuples.add(tuple_i)

        # ── Construir reglas del mes usando las decisiones del AG ─────────
        mes_data = construir_reglas_mes(
            year_i, month_i, contaminacion_i, color_to_day, ag_decisions
        )
        meses_out.append(mes_data)

    # ── Fitness global: promedio normalizado de todos los meses ──────────
    raw_fitness_promedio = (
        sum(fitness_acumulado) / len(fitness_acumulado) if fitness_acumulado else 0.0
    )
    # Normalizar a [0, 1]: ~3000 es el fitness máximo esperado (alta contaminación)
    # max(0, ...) porque en contaminación baja puede ser negativo o cercano a 0
    fitness_norm = round(clamp01(max(0.0, raw_fitness_promedio) / 3000.0), 6)

    return {
        "timestamp": date.today().isoformat(),
        "parametros": merged,
        "contexto_entorno": {
            "factor_sabado": round(float(factor_sabado), 6),
            "usa_entorno_etl": bool(entorno),
        },
        "mejor_fitness": fitness_norm,
        "mejor_solucion": {"meses": meses_out},
    }


if __name__ == "__main__":
    json_output = generar_json_final()
    with open("resultado_ag_hnc.json", "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)
    print("¡JSON Generado con éxito! Archivo: resultado_ag_hnc.json")
