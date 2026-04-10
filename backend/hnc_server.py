
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

import ag_evolutivo_hnc2 as ag
import etl_datos as etl


BASE_DIR     = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR     = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")


@app.get("/")
def root() -> Any:
    return send_from_directory(FRONTEND_DIR, "hnc_ui.html")


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.get("/api/config-inicial")
def config_inicial() -> Any:
    try:
        return jsonify({
            "status": "ok",
            "grupos_placa": ag.GRUPOS_PLACA,
            "hologramas":   ag.HOLOGRAMAS,
            "dias_orden":   ag.DIAS_SEMANA,
            "colores":      ag.COLOR_ORDER,
            "defaults": {
                "params": ag.DEFAULT_PARAMS,
                "ui": {
                    "imeca":         151,
                    "veh_holograma": "H1",
                    "veh_digito":    "all",
                    "view_mode":     "no-circula",
                },
            },
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.get("/api/archivos")
def listar_archivos() -> Any:
    return jsonify(etl.listar_archivos_disponibles())


@app.post("/api/validar-archivo")
def validar_archivo() -> Any:
    archivo = request.files.get("archivo")
    tipo    = request.form.get("tipo", "").strip()

    if not archivo or not archivo.filename:
        return jsonify({"error": "Se requiere el campo 'archivo'."}), 400
    if not tipo:
        return jsonify({"error": "Se requiere el campo 'tipo'."}), 400

    with TemporaryDirectory(prefix="hnc_val_") as tmp:
        ext     = Path(archivo.filename).suffix
        tmpfile = Path(tmp) / f"temp{ext}"
        archivo.save(tmpfile)

        ok, msg = etl.validar_archivo(tmpfile, tipo)
        return jsonify({
            "ok":                   ok,
            "tipo":                 tipo,
            "mensaje":              msg,
            "descripcion_esperada": etl.DESCRIPCION.get(tipo, ""),
        })


@app.post("/api/subir-archivo")
def subir_archivo() -> Any:
    archivo = request.files.get("archivo")
    tipo    = request.form.get("tipo", "").strip()

    if not archivo or not archivo.filename:
        return jsonify({"error": "Se requiere el campo 'archivo'."}), 400
    if not tipo:
        return jsonify({"error": "Se requiere el campo 'tipo'."}), 400

    with TemporaryDirectory(prefix="hnc_sub_") as tmp:
        ext     = Path(archivo.filename).suffix
        tmpfile = Path(tmp) / f"temp{ext}"
        archivo.save(tmpfile)

        ok, msg, destino = etl.recibir_archivo(tmpfile, tipo)
        resp = {
            "ok":              ok,
            "tipo":            tipo,
            "mensaje":         msg,
            "ruta_canonica":   str(destino.relative_to(PROJECT_ROOT)) if destino else None,
            "nombre_canonico": destino.name if destino else None,
        }
        return jsonify(resp), (200 if ok else 422)


@app.post("/api/etl-ias")
def etl_ias() -> Any:
    usar_canonico = request.form.get("usar_canonico") == "1"

    if usar_canonico:
        ias_path = etl.ARCHIVOS["ias"]
        if not ias_path.exists():
            return jsonify({"error": "No hay archivo IAS guardado. Súbelo primero."}), 404
        try:
            ajustes = etl.ejecutar_etl_ias(
                ias_path=ias_path,
                entorno_path=DATA_DIR / "entorno_cdmx.json",
            )
            return jsonify({
                "status":            "ok",
                "ajustes_mensuales": ajustes,
                "mensaje":           "Datos IAS integrados en entorno_cdmx.json",
            })
        except Exception as exc:
            return jsonify({"error": str(exc), "trace": repr(exc)}), 500

    ias_file = request.files.get("ias_csv")
    if not ias_file or not ias_file.filename:
        return jsonify({"error": "Se requiere el campo 'ias_csv' o 'usar_canonico=1'."}), 400

    with TemporaryDirectory(prefix="hnc_ias_") as tmp:
        tmpfile = Path(tmp) / (ias_file.filename or "ias.csv")
        ias_file.save(tmpfile)

        ok_val, msg_val = etl.validar_archivo(tmpfile, "ias")
        if not ok_val:
            return jsonify({"error": f"Archivo IAS inválido: {msg_val}"}), 422

        try:
            etl.recibir_archivo(tmpfile, "ias", forzar=True)
            ajustes = etl.ejecutar_etl_ias(
                ias_path=etl.ARCHIVOS["ias"],
                entorno_path=DATA_DIR / "entorno_cdmx.json",
            )
            return jsonify({
                "status":            "ok",
                "ajustes_mensuales": ajustes,
                "mensaje":           "Datos IAS integrados en entorno_cdmx.json",
            })
        except Exception as exc:
            return jsonify({"error": str(exc), "trace": repr(exc)}), 500


_FILE_TIPOS = {
    "eodEntreSemanaCsv":  "eod_semana_csv",
    "eodEntreSemanaXlsx": "eod_semana_xlsx",
    "eodSabado":          "eod_sabado",
    "vmrc":               "vmrc",
    "verificacion":       "verificacion",
    "contaminantes":      "contaminantes",
    "iasCsv":             "ias",
}


@app.post("/api/run")
def run_model() -> Any:
    payload    = request.get_json(silent=True) or {}
    params_raw = request.form.get("params") or json.dumps(payload.get("params", {}))
    try:
        params = json.loads(params_raw)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Parámetros inválidos: {exc}"}), 400

    etl_regenerado = False
    fuentes_etl    = []
    advertencias   = []

    with TemporaryDirectory(prefix="hnc_run_") as tmp:
        tmp_path = Path(tmp)

        for form_key, tipo in _FILE_TIPOS.items():
            f = request.files.get(form_key)
            if not f or not f.filename:
                continue
            ext     = Path(f.filename).suffix
            tmpfile = tmp_path / f"{tipo}{ext}"
            f.save(tmpfile)

            ok_v, msg_v = etl.validar_archivo(tmpfile, tipo)
            if ok_v:
                etl.recibir_archivo(tmpfile, tipo, forzar=True)
                fuentes_etl.append(tipo)
            else:
                advertencias.append(f"{tipo}: {msg_v}")

        if fuentes_etl:
            etl_regenerado = True
            etl.ejecutar_etl()

    try:
        resultado = ag.generar_json_final(params)
        resultado["etl_regenerado"]   = etl_regenerado
        resultado["fuentes_etl"]      = fuentes_etl
        resultado["advertencias_etl"] = advertencias

        DATA_DIR.mkdir(exist_ok=True)
        with (DATA_DIR / "resultado_ag_hnc.json").open("w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)

        return jsonify(resultado)
    except Exception as exc:
        return jsonify({"error": str(exc), "trace": repr(exc)}), 500


@app.get("/api/ultimo-resultado")
def ultimo_resultado() -> Any:
    result_path = DATA_DIR / "resultado_ag_hnc.json"
    if not result_path.exists():
        return jsonify({"status": "sin_resultado"}), 404
    try:
        with result_path.open("r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.get("/<path:path>")
def static_proxy(path: str) -> Any:
    return send_from_directory(FRONTEND_DIR, path)


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    (PROJECT_ROOT / "graficas").mkdir(exist_ok=True)
    print(f"Servidor HNC-Optimizador en http://127.0.0.1:8000")
    print(f"  Frontend:  {FRONTEND_DIR}")
    print(f"  Data:      {DATA_DIR}")
    app.run(host="127.0.0.1", port=8000, debug=True)
