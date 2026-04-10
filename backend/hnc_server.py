import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict

from flask import Flask, jsonify, request, send_from_directory

import ag_evolutivo_hnc as ag
import etl_datos as etl


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")


def _guardar_subida(upload, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    upload.save(destino)
    return destino


@app.get("/")
def root() -> Any:
    return send_from_directory(FRONTEND_DIR, "hnc_ui.html")


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.get("/api/ultimo-resultado")
def ultimo_resultado() -> Any:
    """Devuelve el último resultado guardado del AG (resultado_ag_hnc.json)."""
    result_path = DATA_DIR / "resultado_ag_hnc.json"
    if not result_path.exists():
        return jsonify({"status": "sin_resultado"}), 404
    try:
        with result_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.get("/api/config-inicial")
def config_inicial() -> Any:
    """Información inicial del sistema: constantes y valores por defecto del AG."""
    try:
        return jsonify({
            "status": "ok",
            "grupos_placa": ag.GRUPOS_PLACA,
            "hologramas": ag.HOLOGRAMAS,
            "dias_orden": ag.DIAS_SEMANA,
            "colores": ag.COLOR_ORDER,
            "defaults": {
                "params": ag.DEFAULT_PARAMS,
                "ui": {
                    "imeca": 151,
                    "veh_holograma": "H1",
                    "veh_digito": "all",
                    "view_mode": "no-circula",
                },
            },
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)})


@app.post("/api/run")
def run_model() -> Any:
    """Ejecuta el AG y retorna el JSON final en formato oficial."""
    payload = request.get_json(silent=True) or {}
    params_raw = request.form.get("params")
    if params_raw is None:
        params_raw = json.dumps(payload.get("params", {}))
    try:
        params = json.loads(params_raw)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Parámetros inválidos: {exc}"}), 400

    datos_entrada = payload.get("datos_entrada", {}) if isinstance(payload, dict) else {}

    try:
        etl_regenerado = False
        fuentes_etl = []
        with TemporaryDirectory(prefix="hnc_uploads_") as temp_dir:
            temp_path = Path(temp_dir)
            eod_csv = request.files.get("eodEntreSemanaCsv")
            eod_xlsx = request.files.get("eodEntreSemanaXlsx")
            eod_sabado = request.files.get("eodSabado")
            vmrc = request.files.get("vmrc")
            verificacion = request.files.get("verificacion")
            contaminantes = request.files.get("contaminantes")

            if not request.files and datos_entrada:
                eod_csv = datos_entrada.get("eod_semana") or eod_csv
                eod_sabado = datos_entrada.get("eod_sabado") or eod_sabado
                vmrc = datos_entrada.get("vmrc") or vmrc
                verificacion = datos_entrada.get("verificacion") or verificacion
                contaminantes = datos_entrada.get("contaminantes") or contaminantes

            eod_csv_path = _guardar_subida(eod_csv, temp_path / "eod_entre_semana.csv") if eod_csv and eod_csv.filename else None
            eod_xlsx_path = _guardar_subida(eod_xlsx, temp_path / "eod_entre_semana.xlsx") if eod_xlsx and eod_xlsx.filename else None
            eod_sabado_path = _guardar_subida(eod_sabado, temp_path / "eod_sabado.xlsx") if eod_sabado and eod_sabado.filename else None
            vmrc_path = _guardar_subida(vmrc, temp_path / "vmrc_valor_09.csv") if vmrc and vmrc.filename else None
            verif_path = _guardar_subida(verificacion, temp_path / "verificacion.csv") if verificacion and verificacion.filename else None
            contam_path = _guardar_subida(contaminantes, temp_path / "contaminantes.csv") if contaminantes and contaminantes.filename else None

            if any(path is not None for path in [eod_csv_path, eod_xlsx_path, eod_sabado_path, vmrc_path, verif_path, contam_path]):
                etl_regenerado = True
                fuentes_etl = [
                    name for name, path in [
                        ("eodEntreSemanaCsv", eod_csv_path),
                        ("eodEntreSemanaXlsx", eod_xlsx_path),
                        ("eodSabado", eod_sabado_path),
                        ("vmrc", vmrc_path),
                        ("verificacion", verif_path),
                        ("contaminantes", contam_path),
                    ]
                    if path is not None
                ]
                etl.ejecutar_etl(
                    eod_csv_path=eod_csv_path,
                    eod_xlsx_path=eod_xlsx_path,
                    eod_sabado_xlsx_path=eod_sabado_path,
                    vmrc_path=vmrc_path,
                    verif_path=verif_path,
                    contam_path=contam_path,
                )

        payload = ag.generar_json_final(params)
        payload["etl_regenerado"] = etl_regenerado
        payload["fuentes_etl"] = fuentes_etl

        # Guardar el resultado
        with (DATA_DIR / "resultado_ag_hnc.json").open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)

        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc), "trace": repr(exc)}), 500


@app.get("/<path:path>")
def static_proxy(path: str) -> Any:
    return send_from_directory(FRONTEND_DIR, path)


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    app.run(host="127.0.0.1", port=8000, debug=True)