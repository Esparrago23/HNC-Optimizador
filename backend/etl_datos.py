
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DIR_FACTORES  = PROJECT_ROOT / "1.Factores de Emisión"
DIR_PARQUE    = PROJECT_ROOT / "2.Composición del Parque Vehicular"
DIR_TRAFICO   = PROJECT_ROOT / "3.Curvas de Demanda y Tráfico"
DIR_DATA      = PROJECT_ROOT / "data"
DIR_GRAFICAS  = PROJECT_ROOT / "graficas"
ENTORNO_PATH  = DIR_DATA / "entorno_cdmx.json"

ARCHIVOS: Dict[str, Path] = {
    "verificacion":   DIR_FACTORES / "verificacion_automotriz.csv",
    "ias":            DIR_FACTORES / "ias_calidad_aire.csv",
    "vmrc":           DIR_PARQUE   / "vmrc_parque_vehicular.csv",
    "contaminantes":  DIR_TRAFICO  / "contaminantes.csv",
    "eod_semana_xlsx":DIR_TRAFICO  / "eod_entre_semana.xlsx",
    "eod_semana_csv": DIR_TRAFICO  / "eod_entre_semana.csv",
    "eod_sabado":     DIR_TRAFICO  / "eod_sabado.xlsx",
}

DESCRIPCION: Dict[str, str] = {
    "verificacion":    "Verificación automotriz (CSV con columnas: servicio, combustible, certificado, co_5024…)",
    "ias":             "IAS SIMAT CDMX (CSV con columnas: Fecha, Hora, Condicion, Parametros)",
    "vmrc":            "VMRC parque vehicular (CSV con columnas: cve_entidad, cve_municipio, año, valor…)",
    "contaminantes":   "Contaminantes (CSV con columnas: date, id_station, id_parameter, valor, unit)",
    "eod_semana_xlsx": "EOD entre semana (XLSX, hoja Cuadro_4.6A, con 'Hora de inicio del viaje')",
    "eod_semana_csv":  "EOD entre semana (CSV, con 'Hora de inicio del viaje')",
    "eod_sabado":      "EOD sábado (XLSX, hoja Cuadro_5.6A, con 'Hora de inicio del viaje')",
}


GRUPOS_PLACA = {"Amarillo": [5,6], "Rosa": [7,8], "Rojo": [3,4], "Verde": [1,2], "Azul": [9,0]}
DIAS_HABILES = {0:"Lunes", 1:"Martes", 2:"Miércoles", 3:"Jueves", 4:"Viernes"}
PL_CALIBRADO_BASE = {"H00":0.305352, "H0":0.295352, "H1":0.285352, "H2":0.275352}
HORA_COL    = "Hora de inicio del viaje"
TOTAL_COL   = "Total"
TRABAJO_COL = "Ir a trabajar"
ESTUDIO_COL = "Ir a estudiar"

CONDICION_IMECA: Dict[str, float] = {
    "buena":     25.0,
    "aceptable": 75.0,
    "mala":     125.0,
    "muy mala": 175.0,
    "ext. mala":225.0,
    "extrema":  225.0,
}

NOMBRES_MESES = [
    "Enero","Febrero","Marzo","Abril","Mayo","Junio",
    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def normalize_text(value: str) -> str:
    return " ".join(str(value).replace("\n", " ").split()).strip().lower()


def to_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9\.\-]", "", regex=True)
        .replace("", "0")
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def _resultado(ok: bool, msg: str) -> Tuple[bool, str]:
    return ok, msg


def validar_verificacion(path: Path) -> Tuple[bool, str]:
    try:
        df = pd.read_csv(path, nrows=5, low_memory=False)
        req = {"servicio", "combustible", "certificado"}
        cols = {c.strip().lower() for c in df.columns}
        faltantes = req - cols
        if faltantes:
            return _resultado(False,
                f"Faltan columnas requeridas: {sorted(faltantes)}. "
                f"Se encontraron: {sorted(cols)}")
        return _resultado(True, f"✓ verificacion_automotriz — {len(df.columns)} columnas detectadas")
    except Exception as e:
        return _resultado(False, f"No se pudo leer el archivo: {e}")


def validar_ias(path: Path) -> Tuple[bool, str]:
    try:
        skip = _detectar_encabezado_ias(path)
        df = pd.read_csv(path, skiprows=skip, nrows=10, encoding="utf-8-sig",
                         on_bad_lines="skip", low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        cols_l = [c.lower() for c in df.columns]
        if not any("fecha" in c for c in cols_l):
            return _resultado(False, "No se encontró columna 'Fecha'. ¿Es el archivo IAS de SIMAT CDMX?")
        if not any(k in c for c in cols_l for k in ["condic","calidad","estado"]):
            return _resultado(False, "No se encontró columna 'Condicion'. ¿Es el archivo IAS de SIMAT CDMX?")
        col_cond = next(c for c in df.columns if any(k in c.lower() for k in ["condic","calidad","estado"]))
        valores = df[col_cond].astype(str).str.strip().str.lower().unique().tolist()
        validos = [v for v in valores if v in CONDICION_IMECA]
        if not validos:
            return _resultado(False,
                f"Columna '{col_cond}' no contiene valores reconocidos "
                f"(Buena/Aceptable/Mala/Muy Mala/Ext. Mala). Valores encontrados: {valores[:5]}")
        return _resultado(True, f"✓ ias_calidad_aire — encabezado en fila {skip}, condiciones: {validos[:3]}…")
    except Exception as e:
        return _resultado(False, f"No se pudo leer el archivo: {e}")


def validar_vmrc(path: Path) -> Tuple[bool, str]:
    try:
        df = pd.read_csv(path, nrows=5, low_memory=False)
        cols_l = {c.strip().lower() for c in df.columns}
        req = {"cve_entidad", "año", "valor"}
        faltantes = req - cols_l
        if faltantes:
            return _resultado(False, f"Faltan columnas requeridas: {sorted(faltantes)}")
        return _resultado(True, f"✓ vmrc_parque_vehicular — columnas: {sorted(cols_l)[:5]}…")
    except Exception as e:
        return _resultado(False, f"No se pudo leer el archivo: {e}")


def validar_contaminantes(path: Path) -> Tuple[bool, str]:
    try:
        header_row = _detect_header_row_csv(path)
        df = pd.read_csv(path, skiprows=header_row, nrows=5, low_memory=False)
        cols_l = {c.strip().lower() for c in df.columns}
        req = {"date", "id_parameter", "valor"}
        faltantes = req - cols_l
        if faltantes:
            return _resultado(False, f"Faltan columnas: {sorted(faltantes)}. Encontradas: {sorted(cols_l)}")
        return _resultado(True, f"✓ contaminantes — encabezado en fila {header_row}")
    except Exception as e:
        return _resultado(False, f"No se pudo leer el archivo: {e}")


def validar_eod(path: Path, es_xlsx: bool = True) -> Tuple[bool, str]:
    try:
        if es_xlsx:
            xl = pd.ExcelFile(path)
            hojas = xl.sheet_names
            hoja = next((h for h in hojas if "4.6" in h or "5.6" in h), hojas[0] if hojas else None)
            if hoja is None:
                return _resultado(False, f"No se encontró hoja válida. Hojas: {hojas}")
            df_raw = pd.read_excel(path, sheet_name=hoja, header=None, nrows=30)
        else:
            df_raw = pd.read_csv(path, header=None, nrows=30, encoding="utf-8", engine="python")

        for idx in range(len(df_raw)):
            vals = [normalize_text(str(v)) for v in df_raw.iloc[idx].tolist()]
            if any("hora de inicio del viaje" in v for v in vals):
                return _resultado(True, f"✓ EOD — encabezado en fila {idx}, hoja '{hoja if es_xlsx else 'CSV'}'")
        return _resultado(False,
            "No se encontró 'Hora de inicio del viaje' en las primeras 30 filas. "
            "¿Es un archivo EOD 2017 del INEGI/SEMOVI?")
    except Exception as e:
        return _resultado(False, f"No se pudo leer el archivo: {e}")


def validar_archivo(path: Path, tipo: str) -> Tuple[bool, str]:
    validators = {
        "verificacion":    lambda p: validar_verificacion(p),
        "ias":             lambda p: validar_ias(p),
        "vmrc":            lambda p: validar_vmrc(p),
        "contaminantes":   lambda p: validar_contaminantes(p),
        "eod_semana_xlsx": lambda p: validar_eod(p, es_xlsx=True),
        "eod_semana_csv":  lambda p: validar_eod(p, es_xlsx=False),
        "eod_sabado":      lambda p: validar_eod(p, es_xlsx=True),
    }
    fn = validators.get(tipo)
    if fn is None:
        return _resultado(False, f"Tipo desconocido: '{tipo}'. Válidos: {sorted(validators)}")
    return fn(path)


def recibir_archivo(
    origen: Path,
    tipo: str,
    forzar: bool = False,
) -> Tuple[bool, str, Optional[Path]]:
    if tipo not in ARCHIVOS:
        return False, f"Tipo '{tipo}' no reconocido. Tipos válidos: {sorted(ARCHIVOS)}", None

    destino = ARCHIVOS[tipo]

    if not forzar:
        ok, msg = validar_archivo(origen, tipo)
        if not ok:
            return False, (
                f"❌ Archivo rechazado — estructura incorrecta.\n"
                f"Se esperaba: {DESCRIPCION.get(tipo, tipo)}\n"
                f"Problema encontrado: {msg}"
            ), None

    destino.parent.mkdir(parents=True, exist_ok=True)

    if destino.exists():
        backup = destino.with_suffix(f".bak{destino.suffix}")
        shutil.copy2(destino, backup)

    shutil.copy2(origen, destino)
    return True, (
        f"✅ Archivo guardado como '{destino.name}' en {destino.parent.name}/\n"
        f"   (nombre original conservado internamente como respaldo)"
    ), destino


def listar_archivos_disponibles() -> Dict[str, Dict]:
    resultado = {}
    for tipo, path in ARCHIVOS.items():
        existe = path.exists()
        resultado[tipo] = {
            "tipo":      tipo,
            "ruta":      str(path.relative_to(PROJECT_ROOT)),
            "nombre":    path.name,
            "existe":    existe,
            "tamaño_kb": round(path.stat().st_size / 1024, 1) if existe else None,
            "descripcion": DESCRIPCION.get(tipo, ""),
        }
    return resultado


def _detectar_encabezado_ias(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
        for i, line in enumerate(f):
            cols = [c.strip().lower() for c in line.split(",")]
            if any("fecha" in c for c in cols):
                return i
    raise ValueError(
        "No se encontró columna 'Fecha' en el CSV. "
        "Verifica que sea el archivo IAS de SIMAT CDMX."
    )


def _detect_header_row_csv(path: Path, marker: str = '"date","id_station","id_parameter","valor","unit"') -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if line.strip() == marker:
                return i
    raise ValueError("No se encontró encabezado esperado en el CSV de contaminantes.")


def find_header_row(df_raw: pd.DataFrame) -> int:
    for idx in range(len(df_raw)):
        row_values = [normalize_text(v) for v in df_raw.iloc[idx].tolist()]
        if any("hora de inicio del viaje" in v for v in row_values):
            return idx
    raise ValueError("No se encontró la fila de encabezados con 'Hora de inicio del viaje'.")


def build_dataframe_from_raw(df_raw: pd.DataFrame) -> pd.DataFrame:
    header_row = find_header_row(df_raw)
    headers = [str(v).strip() for v in df_raw.iloc[header_row].tolist()]
    df = df_raw.iloc[header_row + 1:].copy()
    df.columns = [str(c).strip() for c in headers]
    return df


def _calcular_probabilidad_laboral(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    required = {HORA_COL, TOTAL_COL, TRABAJO_COL, ESTUDIO_COL}
    if not required.issubset(df.columns):
        missing = sorted(required.difference(df.columns))
        raise ValueError(f"Faltan columnas EOD: {missing}")
    pattern_hora = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
    df = df[df[HORA_COL].astype(str).str.strip().str.match(pattern_hora, na=False)].copy()
    df[TOTAL_COL] = to_number(df[TOTAL_COL])
    df[TRABAJO_COL] = to_number(df[TRABAJO_COL])
    df[ESTUDIO_COL] = to_number(df[ESTUDIO_COL])
    grouped = (
        df.groupby(HORA_COL, as_index=False)[[TOTAL_COL, TRABAJO_COL, ESTUDIO_COL]]
        .sum().sort_values(HORA_COL)
    )
    grouped["probabilidad_laboral"] = (
        (grouped[TRABAJO_COL] + grouped[ESTUDIO_COL])
        .div(grouped[TOTAL_COL].where(grouped[TOTAL_COL] != 0, 1))
        .clip(0.0, 1.0)
    )
    return {
        row[HORA_COL]: {"probabilidad_laboral": round(float(row["probabilidad_laboral"]), 6)}
        for _, row in grouped.iterrows()
    }


def cargar_probabilidad_laboral_horaria(
    csv_path: Optional[Path] = None,
    xlsx_path: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    print("Cargando probabilidades laborales horarias (entre semana)…")
    csv_p  = csv_path  or ARCHIVOS["eod_semana_csv"]
    xlsx_p = xlsx_path or ARCHIVOS["eod_semana_xlsx"]
    if csv_p.exists():
        print(f"  Usando CSV: {csv_p.name}")
        df_raw = pd.read_csv(csv_p, header=None, encoding="utf-8", engine="python")
        df = build_dataframe_from_raw(df_raw)
    elif xlsx_p.exists():
        print(f"  Usando XLSX: {xlsx_p.name}")
        df_raw = pd.read_excel(xlsx_p, sheet_name="Cuadro_4.6A", header=None)
        df = build_dataframe_from_raw(df_raw)
    else:
        raise FileNotFoundError(
            f"No se encontró EOD entre semana. Se buscó:\n  {csv_p}\n  {xlsx_p}"
        )
    resultado = _calcular_probabilidad_laboral(df)
    print(f"  ✓ {len(resultado)} horas de probabilidad laboral")
    return resultado


def cargar_probabilidad_laboral_sabado_horaria(
    xlsx_path: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    print("Cargando probabilidades laborales horarias (sábado)…")
    path = xlsx_path or ARCHIVOS["eod_sabado"]
    if not path.exists():
        raise FileNotFoundError(f"No se encontró EOD sábado: {path}")
    df_raw = pd.read_excel(path, sheet_name="Cuadro_5.6A", header=None)
    df = build_dataframe_from_raw(df_raw)
    resultado = _calcular_probabilidad_laboral(df)
    print(f"  ✓ {len(resultado)} horas sábado")
    return resultado


def cargar_total_vehiculos(vmrc_path: Optional[Path] = None) -> int:
    print("Cargando total de vehículos (VMRC)…")
    path = vmrc_path or ARCHIVOS["vmrc"]
    df = pd.read_csv(path)
    df["cve_entidad"]  = df["cve_entidad"].astype(str).str.zfill(2)
    df["cve_municipio"] = pd.to_numeric(df["cve_municipio"], errors="coerce").fillna(-1).astype(int)
    df["año"]   = pd.to_numeric(df["año"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    estatal = df[(df["cve_entidad"] == "09") & (df["cve_municipio"] == 0)].copy()
    if estatal.empty:
        raise ValueError("No se encontró registro estatal (cve_municipio=0) para CDMX en VMRC.")
    max_anio = int(estatal["año"].max())
    total = int(round(float(estatal[estatal["año"] == max_anio]["valor"].iloc[0])))
    print(f"  ✓ {total:,} vehículos (año {max_anio})")
    return total


def _es_restringible(servicio: str, combustible: str) -> bool:
    s, c = normalize_text(servicio), normalize_text(combustible)
    if any(k in s for k in ["taxi","emergencia","servicios urbanos","carga",
                              "transporte publico","transporte público","motocic"]):
        return False
    if any(k in c for k in ["electr","hibr","hídrogeno","hidrogeno"]):
        return False
    return True


def _map_certificado(cert: str) -> str:
    c = normalize_text(cert)
    if c in {"doble cero","doble_cero","dbl_cero","00","h00"}: return "H00"
    if c in {"cero","0"}:  return "H0"
    if c in {"uno","1"}:   return "H1"
    if c in {"dos","2","rechazo"}: return "H2"
    return ""


def cargar_metricas_verificacion(
    verif_path: Optional[Path] = None,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    print("Cargando métricas de verificación ambiental…")
    path = verif_path or ARCHIVOS["verificacion"]
    counts = {"H00":0, "H0":0, "H1":0, "H2":0}
    sums   = {"H00":0.0,"H0":0.0,"H1":0.0,"H2":0.0}
    for chunk in pd.read_csv(
        path,
        usecols=["servicio","combustible","certificado","co_5024","nox_5024","hc_5024"],
        chunksize=250_000, low_memory=False,
    ):
        chunk = chunk.copy()
        mask = chunk.apply(
            lambda r: _es_restringible(r.get("servicio",""), r.get("combustible","")), axis=1
        )
        chunk = chunk[mask]
        chunk["grupo"] = chunk["certificado"].astype(str).map(_map_certificado)
        chunk = chunk[chunk["grupo"].isin(counts)]
        if chunk.empty: continue
        for col in ["co_5024","nox_5024","hc_5024"]:
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0.0)
        chunk["emision_bruta"] = (
            chunk["co_5024"].clip(0) + chunk["nox_5024"].clip(0) + chunk["hc_5024"].clip(0)
        )
        for k, v in chunk.groupby("grupo").size().items():
            counts[k] += int(v)
        for k, v in chunk.groupby("grupo")["emision_bruta"].sum().items():
            sums[k] += float(v)

    total = sum(counts.values())
    distribucion = {k: counts[k]/total for k in counts} if total > 0 else \
                   {"H00":0.20,"H0":0.30,"H1":0.30,"H2":0.20}
    medias = {k: (sums[k]/counts[k] if counts[k] > 0 else 0.0) for k in counts}
    positivos = [v for v in medias.values() if v > 0]
    base = sum(positivos)/len(positivos) if positivos else 1.0
    factores = {k: clamp(medias[k]/base if base > 0 else 1.0, 0.2, 8.0) for k in medias}
    print(f"  ✓ Distribución: {', '.join(f'{k}={v:.1%}' for k,v in distribucion.items())}")
    return distribucion, factores


def cargar_ajustes_semanales(
    contam_path: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    print("Cargando ajustes semanales de contaminación…")
    path = contam_path or ARCHIVOS["contaminantes"]
    header_row = _detect_header_row_csv(path)
    acumulado = {d: {"suma":0.0,"n":0} for d in DIAS_HABILES.values()}
    for chunk in pd.read_csv(
        path, skiprows=header_row,
        usecols=["date","id_parameter","valor"],
        chunksize=500_000, low_memory=False,
    ):
        chunk = chunk.copy()
        chunk["valor"] = pd.to_numeric(chunk["valor"], errors="coerce")
        chunk = chunk.dropna(subset=["valor","date"])
        chunk = chunk[chunk["id_parameter"].isin(["CO","NO2","PM10","PM2.5","O3"])]
        if chunk.empty: continue
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        chunk = chunk.dropna(subset=["date"])
        chunk["weekday"] = chunk["date"].dt.weekday
        chunk = chunk[chunk["weekday"].isin(DIAS_HABILES)]
        if chunk.empty: continue
        for _, row in chunk.groupby("weekday")["valor"].agg(["sum","count"]).reset_index().iterrows():
            dia = DIAS_HABILES[int(row["weekday"])]
            acumulado[dia]["suma"] += float(row["sum"])
            acumulado[dia]["n"]    += int(row["count"])

    medias = {d: (v["suma"]/v["n"] if v["n"] > 0 else 1.0) for d, v in acumulado.items()}
    media_global = sum(medias.values()) / max(len(medias), 1) or 1.0
    ajustes = {}
    for dia, valor in medias.items():
        rel = valor / media_global
        ajustes[dia] = {
            "factor_demanda":               round(clamp(rel, 0.85, 1.20), 4),
            "factor_probabilidad_laboral":  round(clamp(1.0 + (rel-1.0)*0.5, 0.90, 1.10), 4),
        }
    resumen = ", ".join(f"{d[:3]}={v['factor_demanda']:.3f}" for d, v in ajustes.items())
    print(f"  ✓ Ajustes semanales: {resumen}")
    return ajustes


def cargar_ajustes_mensuales(
    contam_path: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    print("Cargando ajustes mensuales de contaminación…")
    path = contam_path or ARCHIVOS["contaminantes"]
    header_row = _detect_header_row_csv(path)
    acumulado: Dict[int, Dict] = {m: {"suma":0.0,"n":0.0} for m in range(1,13)}
    for chunk in pd.read_csv(
        path, skiprows=header_row,
        usecols=["date","id_parameter","valor"],
        chunksize=500_000, low_memory=False,
    ):
        chunk = chunk.copy()
        chunk["valor"] = pd.to_numeric(chunk["valor"], errors="coerce")
        chunk = chunk.dropna(subset=["valor","date"])
        chunk = chunk[chunk["id_parameter"].isin(["CO","NO2","PM10","PM2.5","O3"])]
        if chunk.empty: continue
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        chunk = chunk.dropna(subset=["date"])
        chunk["month"] = chunk["date"].dt.month
        for _, row in chunk.groupby("month")["valor"].agg(["sum","count"]).reset_index().iterrows():
            acumulado[int(row["month"])]["suma"] += float(row["sum"])
            acumulado[int(row["month"])]["n"]    += float(row["count"])

    promedios = {m: (v["suma"]/v["n"] if v["n"] > 0 else 1.0) for m, v in acumulado.items()}
    promedio_global = sum(promedios.values()) / max(len(promedios), 1) or 1.0
    resultado: Dict[str, Dict] = {}
    for m, valor in sorted(promedios.items()):
        resultado[f"{m:02d}"] = {
            "factor_contaminacion": round(clamp(valor/promedio_global, 0.80, 1.35), 4),
            "indice_contaminacion": round(float(valor), 6),
        }
    print(f"  ✓ Ajustes mensuales: {len(resultado)} meses procesados")
    return resultado


def procesar_ias_csv(ias_path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    path = ias_path or ARCHIVOS["ias"]
    print(f"  Procesando IAS CSV: {path.name}")

    skip = _detectar_encabezado_ias(path)
    df = pd.read_csv(path, skiprows=skip, encoding="utf-8-sig",
                     on_bad_lines="skip", low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    col_fecha = next((c for c in df.columns if "fecha" in c.lower()), None)
    col_cond  = next((c for c in df.columns
                      if any(k in c.lower() for k in ["condic","calidad","estado"])), None)
    if col_fecha is None:
        raise ValueError("No se encontró columna 'Fecha' en el IAS CSV.")
    if col_cond is None:
        raise ValueError("No se encontró columna de condición en el IAS CSV.")

    df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
    df = df.dropna(subset=[col_fecha])
    df["mes"] = df[col_fecha].dt.month

    df["imeca"] = (
        df[col_cond].astype(str)
        .map(lambda v: " ".join(str(v).lower().strip().split()))
        .map(CONDICION_IMECA)
    )
    df = df.dropna(subset=["imeca"])

    if df.empty:
        raise ValueError(
            "No se extrajeron datos IMECA. "
            "Verifica que la columna Condicion tenga valores como Buena, Mala…"
        )

    promedios = df.groupby("mes")["imeca"].mean().to_dict()
    media_anual = sum(promedios.values()) / max(len(promedios), 1)
    for m in range(1, 13):
        promedios.setdefault(m, media_anual)

    media_anual = sum(promedios[m] for m in range(1,13)) / 12

    resultado: Dict[str, Dict] = {}
    for m in range(1, 13):
        prom = promedios[m]
        factor = clamp(prom / max(media_anual, 1.0), 0.40, 2.00)
        resultado[f"{m:02d}"] = {
            "factor_contaminacion": round(factor, 4),
            "imeca_promedio_real":  round(prom, 1),
            "fuente":               f"IAS SIMAT CDMX — {path.name}",
            "nombre_mes":           NOMBRES_MESES[m - 1],
        }

    print(
        f"  ✓ IAS procesado: {len(df):,} registros | "
        f"media anual={media_anual:.1f} IMECA"
    )
    for m, d in sorted(resultado.items()):
        print(f"    Mes {m} ({d['nombre_mes'][:3]}): "
              f"{d['imeca_promedio_real']:.1f} IMECA | factor={d['factor_contaminacion']:.3f}x")
    return resultado


def ejecutar_etl_ias(
    ias_path: Optional[Path] = None,
    entorno_path: Optional[Path] = None,
) -> Dict[str, Dict]:
    target = entorno_path or ENTORNO_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    entorno = {}
    if target.exists():
        with target.open("r", encoding="utf-8") as f:
            entorno = json.load(f)

    ajustes = procesar_ias_csv(ias_path)
    entorno["ajustes_mensuales"] = ajustes

    try:
        import os, subprocess
        if not os.access(target, os.W_OK) and target.exists():
            subprocess.run(["chmod", "u+w", str(target)], check=True)
    except Exception:
        pass

    with target.open("w", encoding="utf-8") as f:
        json.dump(entorno, f, ensure_ascii=False, indent=4)
    print(f"  ✓ entorno_cdmx.json actualizado con IAS → {target}")
    return ajustes


def estimar_pl_por_holograma(prob_laborales: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    valores = [float(v.get("probabilidad_laboral", 0.0))
               for v in prob_laborales.values() if isinstance(v, dict)]
    if not valores:
        return PL_CALIBRADO_BASE.copy()
    promedio = sum(valores) / len(valores)
    factor = clamp(promedio / 0.28, 0.85, 1.15)
    return {h: round(clamp(b*factor, 0.12, 0.55), 6) for h, b in PL_CALIBRADO_BASE.items()}


def consolidar_entorno(
    total_vehiculos: int,
    distribucion: Dict[str, float],
    factores_emision: Dict[str, float],
    prob_laborales: Dict[str, Dict[str, float]],
    prob_laborales_sabado: Dict[str, Dict[str, float]],
    ajustes_semanales: Dict[str, Dict[str, float]],
    ajustes_mensuales: Optional[Dict[str, Dict]] = None,
) -> Dict:
    print("\nConsolidando entorno…")
    p_l = estimar_pl_por_holograma(prob_laborales)

    raw_tot = {h: float(distribucion[h]) * float(total_vehiculos) for h in ["H00","H0","H1","H2"]}
    tot_int = {h: int(raw_tot[h]) for h in raw_tot}
    faltantes = int(total_vehiculos - sum(tot_int.values()))
    if faltantes > 0:
        residuos = sorted(((h, raw_tot[h]-tot_int[h]) for h in raw_tot), key=lambda x: x[1], reverse=True)
        for i in range(faltantes):
            tot_int[residuos[i % len(residuos)][0]] += 1

    vehiculos = {
        h: {
            "total": int(tot_int[h]),
            "ef":    float(factores_emision[h]),
            "costo": 1.15 if h == "H00" else (1.0 if h == "H1" else (0.85 if h == "H2" else 1.15)),
            "p_l":   float(p_l[h]),
        }
        for h in ["H00","H0","H1","H2"]
    }

    entorno = {
        "vehiculos": vehiculos,
        "grupos_placa": {c: d[:] for c, d in GRUPOS_PLACA.items()},
        "distancia_promedio_km": 24.0,
        "cumplimiento_ciudadano": 0.85,
        "factores_zona": {"Centro": 0.35, "Periferia": 0.55, "Total": 1.0},
        "trafico": {"v_f":45.0, "capacidad_c":3_500_000, "alpha":0.15, "beta":4.0},
        "equidad": {"umbral_r_h2":0.95, "factor":0.15},
        "probabilidad_laboral_horaria": prob_laborales,
        "probabilidad_laboral_sabado_horaria": prob_laborales_sabado,
        "ajustes_semanales": ajustes_semanales,
        "ajustes_mensuales": ajustes_mensuales or {},
    }
    print(f"  ✓ {sum(v['total'] for v in vehiculos.values()):,} vehículos consolidados")
    return entorno


def ejecutar_etl(
    eod_csv_path: Optional[Path] = None,
    eod_xlsx_path: Optional[Path] = None,
    eod_sabado_xlsx_path: Optional[Path] = None,
    vmrc_path: Optional[Path] = None,
    verif_path: Optional[Path] = None,
    contam_path: Optional[Path] = None,
    ias_path: Optional[Path] = None,
) -> Dict:
    prob_lab    = cargar_probabilidad_laboral_horaria(eod_csv_path, eod_xlsx_path)
    prob_sab    = cargar_probabilidad_laboral_sabado_horaria(eod_sabado_xlsx_path)
    total_veh   = cargar_total_vehiculos(vmrc_path)
    dist, ef    = cargar_metricas_verificacion(verif_path)
    aj_sem      = cargar_ajustes_semanales(contam_path)

    ias_p = ias_path or ARCHIVOS["ias"]
    if ias_p.exists():
        aj_men = procesar_ias_csv(ias_p)
        print("  ✓ Ajustes mensuales desde IAS SIMAT")
    else:
        aj_men = cargar_ajustes_mensuales(contam_path)
        print("  ✓ Ajustes mensuales desde contaminantes")

    entorno = consolidar_entorno(total_veh, dist, ef, prob_lab, prob_sab, aj_sem, aj_men)

    ENTORNO_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        import os, subprocess
        if not os.access(ENTORNO_PATH, os.W_OK) and ENTORNO_PATH.exists():
            subprocess.run(["chmod", "u+w", str(ENTORNO_PATH)], check=True)
    except Exception:
        pass
    with ENTORNO_PATH.open("w", encoding="utf-8") as f:
        json.dump(entorno, f, ensure_ascii=False, indent=4)
    print(f"\n✓ entorno_cdmx.json guardado en {ENTORNO_PATH}")
    return entorno


def main() -> None:
    print("=" * 70)
    print("ETL PIPELINE — HNC-Optimizador")
    print("=" * 70)
    print(f"\nProyecto: {PROJECT_ROOT}")
    print("Archivos canónicos:")
    for tipo, info in listar_archivos_disponibles().items():
        estado = "✓" if info["existe"] else "✗ FALTA"
        print(f"  [{estado}] {info['ruta']}")
    print()
    try:
        ejecutar_etl()
        print("\n" + "=" * 70)
        print("ETL COMPLETADO EXITOSAMENTE")
        print("=" * 70)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback; traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
