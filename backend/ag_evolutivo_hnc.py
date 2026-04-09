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
# 10 genes base + 5 genes de asignacion color->dia
GENES = 15
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTORNO_PATH = PROJECT_ROOT / "data" / "entorno_cdmx.json"


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
    # Escala suave: 0.5 -> 1.0, arriba de eso sube el costo de restringir sábados.
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

        # Dia repetido: reasignar uno disponible.
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

        # Evitar que el mes siguiente quede identico al anterior por color.
        prev = seleccion_tuplas[-1]
        if all(perm[i] == prev[i] for i in range(len(COLOR_ORDER))):
            continue

        seleccion_tuplas.append(perm)
        usadas.add(perm)
        if len(seleccion_tuplas) >= meses_count:
            break

    # Fallback defensivo para horizontes muy grandes.
    while len(seleccion_tuplas) < meses_count:
        idx = len(seleccion_tuplas) % len(COLOR_ORDER)
        rot = tuple(dias[idx:] + dias[:idx])
        if rot not in usadas:
            seleccion_tuplas.append(rot)
            usadas.add(rot)
        else:
            # Ultimo recurso: tomar cualquier permutacion no usada.
            for perm in todas:
                if perm not in usadas:
                    seleccion_tuplas.append(perm)
                    usadas.add(perm)
                    break
            else:
                # Si realmente se agotaron (improbable), repetir con rotacion.
                seleccion_tuplas.append(rot)

    asignaciones: List[Dict[str, str]] = []
    for perm in seleccion_tuplas[:meses_count]:
        asignaciones.append({color: perm[i] for i, color in enumerate(COLOR_ORDER)})
    return asignaciones


def construir_reglas_mes(
    year: int,
    month: int,
    contaminacion: str,
    color_to_day_lower: Dict[str, str],
) -> Dict[str, Any]:
    total_sab = total_saturdays(year, month)

    if contaminacion == "alta":
        h1_horario, h1_zona, h1_sab = [5, 22], "total", 2
        h2_horario, h2_zona, h2_sab = [5, 22], "total", total_sab
        extras_per_color = 2 if total_sab == 5 else 1
    elif contaminacion == "baja":
        h1_horario, h1_zona, h1_sab = [5, 16], "centro", 1
        h2_horario, h2_zona, h2_sab = [5, 16], "centro", min(3, total_sab)
        extras_per_color = 0
    else:
        h1_horario, h1_zona, h1_sab = [5, 22], "total", 2
        h2_horario, h2_zona, h2_sab = [5, 22], "total", total_sab
        extras_per_color = 0

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
            # Regla: los extras nunca deben caer en el mismo dia base del color.
            # Se usa desplazamiento +1 (ciclico lunes->martes...viernes->lunes).
            extra_weekday = (weekday + 1) % 5
            h2_item["extras"] = nth_weekday_dates(year, month, extra_weekday, extras_per_color)

        h2_por_color[color] = h2_item

    # Regla de consistencia: todos los colores deben tener el mismo numero de extras por mes.
    if extras_per_color > 0:
        for color in COLOR_ORDER:
            cfg = h2_por_color[color]
            extras = list(cfg.get("extras", []))

            # Si por cualquier razon faltan fechas, completar con el dia base del color.
            if len(extras) < extras_per_color:
                weekday = WEEKDAY_INDEX[color_to_day_lower.get(color, dia_base_por_defecto(color))]
                weekday = (weekday + 1) % 5
                filler = nth_weekday_dates(year, month, weekday, extras_per_color)
                extras = (extras + filler)[:extras_per_color]

            # Si sobran, recortar al objetivo.
            cfg["extras"] = extras[:extras_per_color]

            # Restriccion de negocio: extra no puede caer en el mismo dia base.
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
# DECODIFICACIÓN DEL ADN (LAS DECISIONES DEL ALGORITMO)
# ============================================================================
def generar_individuo() -> List[float]:
    return [random.random() for _ in range(GENES)]


def decodificar_individuo(individuo: List[float], total_sabados_mes: int = 4) -> Dict[str, Any]:
    """El AG decide severidad y propuesta color->dia, aplicando reparación de consistencia."""
    
    # 1. Porcentaje extra de restricción teórica (para la evaluación matemática)
    r_h00, r_h0, r_h1, r_h2 = sorted(float(g) for g in individuo[0:4])

    # 2. Horarios Dinámicos (¿Hasta las 16h o 22h?)
    hora_fin_h1 = 16 if individuo[4] < 0.4 else 22
    hora_fin_h2 = 16 if individuo[5] < 0.15 else 22 # H2 rara vez se libera temprano

    # 3. Zonas (¿Solo Centro o Toda la Ciudad?)
    zona_h1 = "Centro" if individuo[6] < 0.6 else "Total"
    zona_h2 = "Centro" if individuo[7] < 0.2 else "Total" # H2 casi siempre Total

    # 4. Sábados para H1 (Normalmente 2, baja a 1 o sube a 3)
    val_s1 = individuo[8]
    sabados_h1 = 1 if val_s1 < 0.33 else (2 if val_s1 < 0.66 else 3)
    sabados_h1 = min(sabados_h1, total_sabados_mes)

    # 5. Castigo H2 (Sábados y Días Extra)
    val_s2 = individuo[9]
    if val_s2 < 0.2:
        sabados_h2, dias_extra_h2 = 3, 0
    elif val_s2 < 0.5:
        sabados_h2, dias_extra_h2 = 4, 0
    elif val_s2 < 0.7:
        sabados_h2, dias_extra_h2 = total_sabados_mes, 0 # Todos los sábados
    elif val_s2 < 0.9:
        sabados_h2, dias_extra_h2 = total_sabados_mes, 1 # Todos los sábados + 1 día extra
    else:
        sabados_h2, dias_extra_h2 = total_sabados_mes, 2 # Todos los sábados + 2 días extra
        
    # Limitar para no exceder los sábados del mes
    sabados_h2 = min(sabados_h2, total_sabados_mes)

    # 6. Genes de asignacion color->dia (5 genes extra)
    propuesta_color_dia: Dict[str, str] = {}
    for idx, color in enumerate(COLOR_ORDER):
        g = individuo[10 + idx] if (10 + idx) < len(individuo) else 0.0
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
            "dias_extra_h2": dias_extra_h2
        }
    }


# ============================================================================
# EVALUACIÓN MATEMÁTICA (FITNESS)
# ============================================================================
def funcion_objetivo(individuo: List[float], factor_mensual: float, factor_sabado: float = 1.0) -> float:
    # Simulamos un mes estándar de 4 sábados para el entrenamiento base
    sol = decodificar_individuo(individuo, 4)
    d_ag = sol["decisiones_ag"]
    
    # Premia tiempos más cortos (16h vs 22h) económicamente, pero castiga emisiones
    f_tiempo_h1 = (d_ag["hora_fin_h1"] - 5) / 17.0 
    f_tiempo_h2 = (d_ag["hora_fin_h2"] - 5) / 17.0

    # Penalización económica si el AG abusa de meter castigos extra
    # Cada sábado extra y día extra destruye el fitness económico
    penalizacion_economia = 1.0 + (d_ag["sabados_h1"] * 0.05) + (d_ag["sabados_h2"] * 0.08) + (d_ag["dias_extra_h2"] * 0.20)
    penalizacion_economia *= 1.0 + ((factor_sabado - 1.0) * 0.35)
    
    # Reducción de emisiones simulada (entre más castigo, menos emisiones)
    reduccion_emisiones = 1.0 - (d_ag["sabados_h1"]*0.02 + d_ag["sabados_h2"]*0.04 + d_ag["dias_extra_h2"]*0.10)
    reduccion_emisiones -= (factor_sabado - 1.0) * 0.03
    
    # Balance: Si factor_mensual es alto (mucha contaminación), ponderamos más el ambiente
    peso_ambiental = 2.0 * factor_mensual
    peso_economico = 1.5
    
    fitness = 1000.0 / ((reduccion_emisiones * peso_ambiental) * (penalizacion_economia * peso_economico))

    # Penalizacion de respaldo: si sobrevive una propuesta invalida, castigar fuerte.
    viol = sol.get("violaciones_pre_reparacion", {})
    dias_repetidos = int(viol.get("dias_repetidos", 0))
    penalizacion_fuerte = 500.0 * dias_repetidos
    fitness_ajustado = max(1e-6, float(fitness) - penalizacion_fuerte)

    return float(fitness_ajustado)


def aptitud(individuo: List[float], factor_mensual: float, factor_sabado: float = 1.0) -> float:
    return funcion_objetivo(individuo, factor_mensual, factor_sabado)


def seleccionar_padre_ruleta(poblacion: List[List[float]], aptitudes: List[float]) -> List[float]:
    # Ruleta para maximización: desplazamos si hubiera aptitudes negativas.
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


def cruza_un_punto(padre1: List[float], padre2: List[float], prob_cruza: float) -> Tuple[List[float], List[float]]:
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


def poda(poblacion: List[List[float]], factor_mensual: float, factor_sabado: float, tam_objetivo: int) -> List[List[float]]:
    ranking = sorted(poblacion, key=lambda ind: aptitud(ind, factor_mensual, factor_sabado), reverse=True)
    return [ind[:] for ind in ranking[:tam_objetivo]]


def ejecutar_algoritmo_genetico(
    factor_mensual: float,
    factor_sabado: float = 1.0,
    pop_size: int = DEFAULT_POP_SIZE,
    generaciones: int = DEFAULT_GENERATIONS,
    prob_cruza: float = 0.85,
    prob_mutacion: float = 0.05,
    elitismo: int = 2,
) -> Dict[str, Any]:
    poblacion = [generar_individuo() for _ in range(pop_size)]
    best_fit = -math.inf
    best_ind: List[float] = []
    historial: List[float] = []

    for _ in range(generaciones):
        aptitudes = [aptitud(ind, factor_mensual, factor_sabado) for ind in poblacion]
        ranking = sorted(zip(poblacion, aptitudes), key=lambda x: x[1], reverse=True)

        mejor_gen_ind, mejor_gen_fit = ranking[0]
        historial.append(float(mejor_gen_fit))

        if mejor_gen_fit > best_fit:
            best_fit = float(mejor_gen_fit)
            best_ind = mejor_gen_ind[:]

        nueva_poblacion: List[List[float]] = [ind[:] for ind, _ in ranking[:max(1, elitismo)]]

        # Rellenar usando selección + cruza + mutación
        while len(nueva_poblacion) < pop_size:
            p1 = seleccionar_padre_ruleta(poblacion, aptitudes)
            p2 = seleccionar_padre_ruleta(poblacion, aptitudes)
            h1, h2 = cruza_un_punto(p1, p2, prob_cruza)
            nueva_poblacion.append(mutar(h1, prob_mutacion))
            if len(nueva_poblacion) < pop_size:
                nueva_poblacion.append(mutar(h2, prob_mutacion))

        poblacion = poda(nueva_poblacion, factor_mensual, factor_sabado, pop_size)

    return {
        "mejor_fitness": float(best_fit),
        "mejor_individuo": best_ind,
        "historial_fitness": historial,
    }


def evolucionar(factor_mensual: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Wrapper de compatibilidad con nombre anterior.
    cfg = params or {}
    entorno = cargar_entorno_cdmx()
    factor_sabado = resumen_probabilidad_sabado(entorno)
    return ejecutar_algoritmo_genetico(
        factor_mensual=factor_mensual,
        factor_sabado=factor_sabado,
        pop_size=int(cfg.get("pop_size", DEFAULT_POP_SIZE)),
        generaciones=int(cfg.get("generaciones", DEFAULT_GENERATIONS)),
        prob_cruza=0.85,
        prob_mutacion=float(cfg.get("mutacion", 0.05)),
        elitismo=int(cfg.get("elitismo", 2)),
    )

def generar_json_final(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    merged = {**DEFAULT_PARAMS, **(params or {})}
    entorno = cargar_entorno_cdmx()
    factor_sabado = resumen_probabilidad_sabado(entorno)

    start_year, start_month = parse_year_month(str(merged["start_month"]))
    meses_count = max(1, int(merged["meses"]))
    nivel_imeca = float(merged["nivel_imeca"])

    ag_global = evolucionar(1.0, merged)
    raw_fitness = float(ag_global["mejor_fitness"])
    fitness_norm = round(1.0 / (1.0 + (raw_fitness / 2500.0)), 6)
    mejor_ind = ag_global.get("mejor_individuo", [])
    decod_base = decodificar_individuo(mejor_ind, 4)
    color_to_day_base = decod_base.get("color_dia_final", {color: dia_base_por_defecto(color) for color in COLOR_ORDER})

    semilla_mensual = int(sum(float(g) for g in mejor_ind[:10]) * 1_000_000) if mejor_ind else 12345
    asignaciones_mensuales = generar_asignaciones_mensuales_desde_base(
        color_to_day_base,
        meses_count,
        semilla_mensual,
    )

    meses_out: List[Dict[str, Any]] = []
    for i in range(meses_count):
        year_i, month_i = add_months(start_year, start_month, i)
        contaminacion = contamination_for_month(month_i, nivel_imeca)
        color_to_day = asignaciones_mensuales[i]
        meses_out.append(construir_reglas_mes(year_i, month_i, contaminacion, color_to_day))

    mejor_solucion = {"meses": meses_out}

    return {
        "timestamp": date.today().isoformat(),
        "parametros": merged,
        "contexto_entorno": {
            "factor_sabado": round(float(factor_sabado), 6),
            "usa_entorno_etl": bool(entorno),
        },
        "mejor_fitness": fitness_norm,
        "mejor_solucion": mejor_solucion,
    }

if __name__ == "__main__":
    json_output = generar_json_final()
    with open("resultado_ag_hnc.json", "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)
    print("¡JSON Generado con éxito! Archivo: resultado_ag_hnc.json")