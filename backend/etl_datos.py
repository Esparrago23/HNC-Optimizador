"""
ETL (Extract, Transform, Load) para HNC.
Consolida obtención y limpieza de datos de movilidad, parque vehicular, verificación ambiental y contaminación.
"""

import json
import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd


# Rutas relativas - se actualizan según dónde se ejecute el script
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR  # Carpeta raíz con datos
DATA_DIR = BASE_DIR / "data"
OUTPUT_PATH = DATA_DIR / "entorno_cdmx.json"

# Rutas de entrada de datos
EOD_CSV_PATH = INPUT_DIR / "tabulados_eod_2017_entre_semana.xlsx - Cuadro_4.6A.csv"
EOD_XLSX_PATH = INPUT_DIR / "3.Curvas de Demanda y Tráfico" / "tabulados_eod_2017_entre_semana (1).xlsx"
EOD_SABADO_XLSX_PATH = INPUT_DIR / "3.Curvas de Demanda y Tráfico" / "tabulados_eod_2017_sabado.xlsx"
VMRC_PATH = INPUT_DIR / "2.Composición del Parque Vehicular" / "diccionario_de_datos valor_09" / "vmrc_valor_09.csv"
VERIF_PATH = INPUT_DIR / "1.Factores de Emisión" / "verificacion-automotriz-segundo-semestre-2018.csv"
CONTAM_PATH = INPUT_DIR / "3.Curvas de Demanda y Tráfico" / "contaminantes_2025 (1).csv"

HORA_COL = "Hora de inicio del viaje"
TOTAL_COL = "Total"
TRABAJO_COL = "Ir a trabajar"
ESTUDIO_COL = "Ir a estudiar"

GRUPOS_PLACA = {
    "Amarillo": [5, 6],
    "Rosa": [7, 8],
    "Rojo": [3, 4],
    "Verde": [1, 2],
    "Azul": [9, 0],
}

DIAS_HABILES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
}

PL_CALIBRADO_BASE = {
    "H00": 0.305352,
    "H0": 0.295352,
    "H1": 0.285352,
    "H2": 0.275352,
}


def normalize_text(value: str) -> str:
    """Normaliza texto removiendo espacios y convirtiendo a minúsculas."""
    return " ".join(str(value).replace("\n", " ").split()).strip().lower()


def clamp(value: float, low: float, high: float) -> float:
    """Limita value entre low y high."""
    return max(low, min(high, float(value)))


def to_number(series: pd.Series) -> pd.Series:
    """Convierte serie a números limpiando caracteres especiales."""
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9\.-]", "", regex=True)
        .replace("", "0")
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def find_header_row(df_raw: pd.DataFrame) -> int:
    """Busca fila de encabezados en dataframe sin procesar."""
    for idx in range(len(df_raw)):
        row_values = [normalize_text(v) for v in df_raw.iloc[idx].tolist()]
        if any("hora de inicio del viaje" in v for v in row_values):
            return idx
    raise ValueError("No se encontró la fila de encabezados con 'Hora de inicio del viaje'.")


def build_dataframe_from_raw(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Construye dataframe procesado a partir de uno sin procesar."""
    header_row = find_header_row(df_raw)
    headers = [str(v).strip() for v in df_raw.iloc[header_row].tolist()]
    df = df_raw.iloc[header_row + 1 :].copy()
    df.columns = headers
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _calcular_probabilidad_laboral(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Calcula la probabilidad laboral horaria a partir de un dataframe EOD."""
    required = {HORA_COL, TOTAL_COL, TRABAJO_COL, ESTUDIO_COL}
    if not required.issubset(df.columns):
        missing = sorted(required.difference(df.columns))
        raise ValueError(f"Faltan columnas requeridas en EOD: {missing}")

    pattern_hora = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
    df = df[df[HORA_COL].astype(str).str.strip().str.match(pattern_hora, na=False)].copy()

    df[TOTAL_COL] = to_number(df[TOTAL_COL])
    df[TRABAJO_COL] = to_number(df[TRABAJO_COL])
    df[ESTUDIO_COL] = to_number(df[ESTUDIO_COL])

    grouped = (
        df.groupby(HORA_COL, as_index=False)[[TOTAL_COL, TRABAJO_COL, ESTUDIO_COL]]
        .sum()
        .sort_values(HORA_COL)
    )

    grouped["probabilidad_laboral"] = (
        (grouped[TRABAJO_COL] + grouped[ESTUDIO_COL])
        .div(grouped[TOTAL_COL].where(grouped[TOTAL_COL] != 0, 1))
        .clip(lower=0.0, upper=1.0)
    )

    return {
        row[HORA_COL]: {"probabilidad_laboral": round(float(row["probabilidad_laboral"]), 6)}
        for _, row in grouped.iterrows()
    }


def cargar_probabilidad_laboral_horaria(
    eod_csv_path: Optional[Path] = None,
    eod_xlsx_path: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    """Carga probabilidad laboral por hora desde datos EOD."""
    print("Cargando probabilidades laborales horarias...")
    csv_path = eod_csv_path or EOD_CSV_PATH
    xlsx_path = eod_xlsx_path or EOD_XLSX_PATH
    
    if csv_path.exists():
        print(f"  Usando CSV: {csv_path}")
        df_raw = pd.read_csv(csv_path, header=None, encoding="utf-8", engine="python")
        df = build_dataframe_from_raw(df_raw)
    elif xlsx_path.exists():
        print(f"  Usando XLSX: {xlsx_path}")
        df_raw = pd.read_excel(xlsx_path, sheet_name="Cuadro_4.6A", header=None)
        df = build_dataframe_from_raw(df_raw)
    else:
        raise FileNotFoundError(
            "No se encontró archivo EOD. Se buscó:\n"
            f"- {csv_path}\n"
            f"- {xlsx_path}"
        )

    resultado = _calcular_probabilidad_laboral(df)

    print(f"  ✓ Cargadas {len(resultado)} horas de probabilidad laboral")
    return resultado


def cargar_probabilidad_laboral_sabado_horaria(
    eod_sabado_xlsx_path: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    """Carga probabilidad laboral por hora desde los tabulados de sábado."""
    print("Cargando probabilidades laborales de sábado...")
    sabado_path = eod_sabado_xlsx_path or EOD_SABADO_XLSX_PATH

    if not sabado_path.exists():
        raise FileNotFoundError(f"No se encontró archivo de sábado: {sabado_path}")

    df_raw = pd.read_excel(sabado_path, sheet_name="Cuadro_5.6A", header=None)
    df = build_dataframe_from_raw(df_raw)
    resultado = _calcular_probabilidad_laboral(df)

    print(f"  ✓ Cargadas {len(resultado)} horas de probabilidad laboral de sábado")
    return resultado


def cargar_total_vehiculos(vmrc_path: Optional[Path] = None) -> int:
    """Carga total de vehículos del VMRC."""
    print("Cargando total de vehículos...")
    path = vmrc_path or VMRC_PATH
    
    df = pd.read_csv(path)
    df["cve_entidad"] = df["cve_entidad"].astype(str).str.zfill(2)
    df["cve_municipio"] = pd.to_numeric(df["cve_municipio"], errors="coerce").fillna(-1).astype(int)
    df["año"] = pd.to_numeric(df["año"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)

    estatal = df[(df["cve_entidad"] == "09") & (df["cve_municipio"] == 0)].copy()
    if estatal.empty:
        raise ValueError("No se encontró registro estatal (cve_municipio=0) para CDMX en VMRC.")

    max_anio = int(estatal["año"].max())
    valor = float(estatal[estatal["año"] == max_anio]["valor"].iloc[0])
    total = int(round(valor))
    
    print(f"  ✓ Total de vehículos: {total:,}")
    return total


def _map_certificado(certificado: str) -> str:
    """Mapea descriptores de certificado a hologramas."""
    c = normalize_text(certificado)
    if c in {"doble cero", "doble_cero", "dbl_cero", "00", "h00"}:
        return "H00"
    if c in {"cero", "0"}:
        return "H0"
    if c in {"uno", "1"}:
        return "H1"
    if c in {"dos", "2", "rechazo"}:
        return "H2"
    return ""


def _iter_verificacion_chunks(verif_path: Optional[Path] = None) -> Iterable[pd.DataFrame]:
    """Itera sobre chunks de verificación ambiental."""
    path = verif_path or VERIF_PATH
    return pd.read_csv(
        path,
        usecols=["servicio", "combustible", "certificado", "co_5024", "nox_5024", "hc_5024"],
        chunksize=250_000,
        low_memory=False,
    )


def _es_restringible(servicio: str, combustible: str) -> bool:
    """Determina si vehículo es restrictible según servicio y combustible."""
    s = normalize_text(servicio)
    c = normalize_text(combustible)

    if "taxi" in s:
        return False
    if "emergencia" in s or "servicios urbanos" in s:
        return False
    if "carga" in s or "transporte publico" in s or "transporte público" in s:
        return False
    if "motocic" in s:
        return False
    if "electr" in c or "hibr" in c or "hídrogeno" in c or "hidrogeno" in c:
        return False

    return True


def cargar_metricas_verificacion(verif_path: Optional[Path] = None) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Carga distribución de parque y factores de emisión desde verificación ambiental."""
    print("Cargando métricas de verificación ambiental...")
    
    counts = {"H00": 0, "H0": 0, "H1": 0, "H2": 0}
    sums = {"H00": 0.0, "H0": 0.0, "H1": 0.0, "H2": 0.0}

    chunk_count = 0
    for chunk in _iter_verificacion_chunks(verif_path):
        chunk_count += 1
        chunk = chunk.copy()
        mask_restringible = chunk.apply(
            lambda r: _es_restringible(r.get("servicio", ""), r.get("combustible", "")),
            axis=1,
        )
        chunk = chunk[mask_restringible]
        chunk["grupo"] = chunk["certificado"].astype(str).map(_map_certificado)
        chunk = chunk[chunk["grupo"].isin(counts.keys())]
        if chunk.empty:
            continue

        for col in ["co_5024", "nox_5024", "hc_5024"]:
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0.0)

        chunk["emision_bruta"] = (
            chunk["co_5024"].clip(lower=0)
            + chunk["nox_5024"].clip(lower=0)
            + chunk["hc_5024"].clip(lower=0)
        )

        grouped_count = chunk.groupby("grupo").size().to_dict()
        grouped_sum = chunk.groupby("grupo")["emision_bruta"].sum().to_dict()

        for k, v in grouped_count.items():
            counts[k] += int(v)
        for k, v in grouped_sum.items():
            sums[k] += float(v)

    total = sum(counts.values())
    if total <= 0:
        distribucion = {"H00": 0.20, "H0": 0.30, "H1": 0.30, "H2": 0.20}
    else:
        distribucion = {k: counts[k] / total for k in counts}

    medias = {}
    for k in counts:
        if counts[k] > 0:
            medias[k] = sums[k] / counts[k]
        else:
            medias[k] = 0.0

    positivos = [v for v in medias.values() if v > 0]
    base = sum(positivos) / len(positivos) if positivos else 1.0
    factores_emision = {k: clamp(medias[k] / base if base > 0 else 1.0, 0.2, 8.0) for k in medias}

    print(f"  ✓ Procesados {chunk_count} chunks de verificación")
    print(f"  ✓ Distribución: {', '.join(f'{k}={v:.1%}' for k, v in distribucion.items())}")
    print(f"  ✓ Factores emisión: {', '.join(f'{k}={v:.2f}x' for k, v in factores_emision.items())}")

    return distribucion, factores_emision


def _detect_header_row_csv(path: Path, marker: str = '"date","id_station","id_parameter","valor","unit"') -> int:
    """Detecta fila de encabezados en CSV de contaminantes."""
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if line.strip() == marker:
                return i
    raise ValueError("No se encontró encabezado esperado en archivo de contaminantes.")


def cargar_ajustes_semanales(contam_path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    """Carga factores de demanda y probabilidad laboral por día de semana desde contaminación."""
    print("Cargando ajustes semanales...")
    
    path = contam_path or CONTAM_PATH
    header_row = _detect_header_row_csv(path)

    acumulado = {d: {"suma": 0.0, "n": 0} for d in DIAS_HABILES.values()}

    chunk_count = 0
    for chunk in pd.read_csv(
        path,
        skiprows=header_row,
        usecols=["date", "id_parameter", "valor"],
        chunksize=500_000,
        low_memory=False,
    ):
        chunk_count += 1
        chunk = chunk.copy()
        chunk["valor"] = pd.to_numeric(chunk["valor"], errors="coerce")
        chunk = chunk.dropna(subset=["valor", "date"])
        if chunk.empty:
            continue

        chunk = chunk[chunk["id_parameter"].isin(["CO", "NO2", "PM10", "PM2.5", "O3"])]
        if chunk.empty:
            continue

        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        chunk = chunk.dropna(subset=["date"])
        chunk["weekday"] = chunk["date"].dt.weekday
        chunk = chunk[chunk["weekday"].isin(DIAS_HABILES.keys())]
        if chunk.empty:
            continue

        grouped = chunk.groupby("weekday")["valor"].agg(["sum", "count"]).reset_index()
        for _, row in grouped.iterrows():
            dia = DIAS_HABILES[int(row["weekday"])]
            acumulado[dia]["suma"] += float(row["sum"])
            acumulado[dia]["n"] += int(row["count"])

    medias = {}
    for dia, values in acumulado.items():
        if values["n"] > 0:
            medias[dia] = values["suma"] / values["n"]
        else:
            medias[dia] = 1.0

    media_global = sum(medias.values()) / max(len(medias), 1)
    if media_global <= 0:
        media_global = 1.0

    ajustes = {}
    for dia, valor in medias.items():
        relativo = valor / media_global
        ajustes[dia] = {
            "factor_demanda": round(clamp(relativo, 0.85, 1.20), 4),
            "factor_probabilidad_laboral": round(clamp(1.0 + (relativo - 1.0) * 0.5, 0.90, 1.10), 4),
        }

    print(f"  ✓ Procesados {chunk_count} chunks de contaminación")
    for dia, ajuste in ajustes.items():
        print(f"  - {dia}: demanda={ajuste['factor_demanda']:.3f}, prob_lab={ajuste['factor_probabilidad_laboral']:.3f}")

    return ajustes


def cargar_ajustes_mensuales(contam_path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    """Carga un peso mensual de contaminación a partir del CSV de contaminantes."""
    print("Cargando ajustes mensuales de contaminación...")

    path = contam_path or CONTAM_PATH
    header_row = _detect_header_row_csv(path)

    acumulado: Dict[int, Dict[str, float]] = {m: {"suma": 0.0, "n": 0.0} for m in range(1, 13)}

    chunk_count = 0
    for chunk in pd.read_csv(
        path,
        skiprows=header_row,
        usecols=["date", "id_parameter", "valor"],
        chunksize=500_000,
        low_memory=False,
    ):
        chunk_count += 1
        chunk = chunk.copy()
        chunk["valor"] = pd.to_numeric(chunk["valor"], errors="coerce")
        chunk = chunk.dropna(subset=["valor", "date"])
        if chunk.empty:
            continue

        chunk = chunk[chunk["id_parameter"].isin(["CO", "NO2", "PM10", "PM2.5", "O3"])]
        if chunk.empty:
            continue

        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        chunk = chunk.dropna(subset=["date"])
        if chunk.empty:
            continue

        chunk["month"] = chunk["date"].dt.month
        grouped = chunk.groupby("month")["valor"].agg(["sum", "count"]).reset_index()
        for _, row in grouped.iterrows():
            month = int(row["month"])
            acumulado[month]["suma"] += float(row["sum"])
            acumulado[month]["n"] += float(row["count"])

    promedios = {
        month: (values["suma"] / values["n"] if values["n"] > 0 else 1.0)
        for month, values in acumulado.items()
    }
    promedio_global = sum(promedios.values()) / max(len(promedios), 1)
    if promedio_global <= 0:
        promedio_global = 1.0

    orden = sorted(promedios.items(), key=lambda kv: kv[1], reverse=True)
    resultado: Dict[str, Dict[str, float]] = {}
    for rank, (month, valor) in enumerate(orden, start=1):
        relativo = valor / promedio_global
        resultado[f"{month:02d}"] = {
            "factor_contaminacion": round(clamp(relativo, 0.80, 1.35), 4),
            "indice_contaminacion": round(float(valor), 6),
            "ranking_contaminacion": float(rank),
        }

    print(f"  ✓ Procesados {chunk_count} chunks de contaminación mensual")
    print(
        "  ✓ Meses más contaminados: "
        + ", ".join(f"{m}:{d['factor_contaminacion']:.2f}x" for m, d in list(resultado.items())[:5])
    )

    return resultado


def estimar_pl_por_holograma(prob_laborales: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Ajusta p_l calibrado por holograma usando el perfil laboral observado en EOD."""
    valores = [
        float(v.get("probabilidad_laboral", 0.0))
        for v in prob_laborales.values()
        if isinstance(v, dict)
    ]
    if not valores:
        return PL_CALIBRADO_BASE.copy()

    promedio = sum(valores) / len(valores)
    # Escalamos alrededor de un promedio de referencia para no perder calibración histórica.
    factor = clamp(promedio / 0.28, 0.85, 1.15)

    salida = {}
    for h, base in PL_CALIBRADO_BASE.items():
        salida[h] = round(clamp(base * factor, 0.12, 0.55), 6)
    return salida


def consolidar_entorno(
    total_vehiculos: int,
    distribucion: Dict[str, float],
    factores_emision: Dict[str, float],
    prob_laborales: Dict[str, Dict[str, float]],
    prob_laborales_sabado: Dict[str, Dict[str, float]],
    ajustes_semanales: Dict[str, Dict[str, float]],
    ajustes_mensuales: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict:
    """Consolida todos los datos en un entorno integrado."""
    print("\nConsolidando entorno...")
    p_l_por_holograma = estimar_pl_por_holograma(prob_laborales)

    # Asignar totales por holograma preservando exactamente el total VMRC.
    raw_totales = {h: float(distribucion[h]) * float(total_vehiculos) for h in ["H00", "H0", "H1", "H2"]}
    totales_enteros = {h: int(raw_totales[h]) for h in raw_totales}
    faltantes = int(total_vehiculos - sum(totales_enteros.values()))
    if faltantes > 0:
        residuos = sorted(
            ((h, raw_totales[h] - totales_enteros[h]) for h in raw_totales),
            key=lambda x: x[1],
            reverse=True,
        )
        for i in range(faltantes):
            h = residuos[i % len(residuos)][0]
            totales_enteros[h] += 1
    
    vehiculos = {}
    for h in ["H00", "H0", "H1", "H2"]:
        vehiculos[h] = {
            "total": int(totales_enteros[h]),
            "ef": float(factores_emision[h]),
            "costo": 1.0 if h == "H1" else (0.85 if h == "H2" else 1.15),
            "p_l": float(p_l_por_holograma[h]),
        }

    entorno = {
        "vehiculos": vehiculos,
        "grupos_placa": {color: digitos[:] for color, digitos in GRUPOS_PLACA.items()},
        "distancia_promedio_km": 24.0,
        "cumplimiento_ciudadano": 0.85,
        "factores_zona": {"Centro": 0.35, "Periferia": 0.55, "Total": 1.0},
        "trafico": {
            "v_f": 45.0,
            "capacidad_c": 3_500_000,
            "alpha": 0.15,
            "beta": 4.0,
        },
        "equidad": {
            "umbral_r_h2": 0.95,
            "factor": 0.15,
        },
        "probabilidad_laboral_horaria": prob_laborales,
        "probabilidad_laboral_sabado_horaria": prob_laborales_sabado,
        "ajustes_semanales": ajustes_semanales,
        "ajustes_mensuales": ajustes_mensuales or {},
    }

    print(f"  ✓ Entorno consolidado con {sum(v['total'] for v in vehiculos.values()):,} vehículos")
    print(f"  ✓ p_l por holograma: {', '.join(f'{k}={v:.4f}' for k, v in p_l_por_holograma.items())}")
    return entorno


def ejecutar_etl(
    eod_csv_path: Optional[Path] = None,
    eod_xlsx_path: Optional[Path] = None,
    eod_sabado_xlsx_path: Optional[Path] = None,
    vmrc_path: Optional[Path] = None,
    verif_path: Optional[Path] = None,
    contam_path: Optional[Path] = None,
) -> Dict:
    """Ejecuta pipeline ETL completo y devuelve el entorno consolidado."""
    prob_laborales = cargar_probabilidad_laboral_horaria(eod_csv_path, eod_xlsx_path)
    prob_laborales_sabado = cargar_probabilidad_laboral_sabado_horaria(eod_sabado_xlsx_path)
    total_vehiculos = cargar_total_vehiculos(vmrc_path)
    distribucion, factores_emision = cargar_metricas_verificacion(verif_path)
    ajustes_semanales = cargar_ajustes_semanales(contam_path)
    ajustes_mensuales = cargar_ajustes_mensuales(contam_path)

    entorno = consolidar_entorno(
        total_vehiculos,
        distribucion,
        factores_emision,
        prob_laborales,
        prob_laborales_sabado,
        ajustes_semanales,
        ajustes_mensuales,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(entorno, f, ensure_ascii=False, indent=4)

    return entorno


def main() -> None:
    """Ejecuta pipeline ETL completo."""
    print("=" * 70)
    print("ETL PIPELINE - HNC OPTIMIZATION")
    print("=" * 70)
    
    try:
        print(f"\nGuardando entorno en {OUTPUT_PATH}...")
        ejecutar_etl()

        print(f"  ✓ Archivo guardado exitosamente")
        print("\n" + "=" * 70)
        print("ETL COMPLETADO EXITOSAMENTE")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
