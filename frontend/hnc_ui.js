const state = {
  files: { eodSemana: null, eodSabado: null, vmrc: null, verificacion: null, contaminantes: null },
  running: false, stopRequested: false, result: null, runController: null,
  monthKeys: [], monthIndex: 0, selectedDate: null,
  defaults: null,
};

const FALLBACK_DEFAULTS = {
  params: {
    pop_size: 100, generaciones: 120, mutacion: 0.05, elitismo: 2,
    peso_equidad: 1, peso_ambiental_critico: 2.2, peso_economico: 1.55,
    nivel_imeca: 150, start_month: "2026-04", meses: 6,
  },
  ui: { imeca: 151, veh_holograma: "H1", veh_digito: "all" },
};

const DAYS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"];
const DIGIT_COLOR = {
  0:"#2563eb", 9:"#2563eb", 1:"#16a34a", 2:"#16a34a", 3:"#ef4444", 4:"#ef4444",
  5:"#eab308", 6:"#eab308", 7:"#ec4899", 8:"#ec4899",
};
const MONTH_NAMES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
const FALLBACK_GRUPOS_PLACA = {
  Amarillo: [5, 6],
  Rosa: [7, 8],
  Rojo: [3, 4],
  Verde: [1, 2],
  Azul: [9, 0],
};

const IMECA_WEIGHT_POINTS = [
  { imeca: 0, weight: 0.8 },
  { imeca: 50, weight: 0.8 },
  { imeca: 100, weight: 1.2 },
  { imeca: 150, weight: 2.2 },
  { imeca: 200, weight: 2.5 },
  { imeca: 300, weight: 3.5 },
  { imeca: 400, weight: 5.0 },
];

const els = {};

function initializeDOM() {
  els.tabDemo = document.getElementById("tabDemo") || document.createElement("div");
  els.tabAdvanced = document.getElementById("tabAdvanced") || document.createElement("div");
  els.panelDemo = document.getElementById("panelDemo") || document.createElement("div");
  els.panelAdvanced = document.getElementById("panelAdvanced") || document.createElement("div");
  els.demoStatusText = document.getElementById("demoStatusText") || document.createElement("div");
  els.demoVehicleSummary = document.getElementById("demoVehicleSummary") || document.createElement("div");
  els.btnVerificar = document.getElementById("btnVerificar") || document.createElement("button");
  els.etlFileList = document.getElementById("etlFileList") || document.createElement("div");
  // IAS panel
  els.fileIas = document.getElementById("fileIas") || document.createElement("input");
  els.iasFileName = document.getElementById("iasFileName") || document.createElement("span");
  els.btnImportarIas = document.getElementById("btnImportarIas") || document.createElement("button");
  els.iasBadge = document.getElementById("iasBadge") || document.createElement("span");
  els.iasStatus = document.getElementById("iasStatus") || document.createElement("div");
  els.iasPreview = document.getElementById("iasPreview") || document.createElement("div");
  els.startMonth = document.getElementById("startMonth") || document.createElement("input");
  els.horizonteMeses = document.getElementById("horizonteMeses") || document.createElement("input");
  els.envSummary = document.getElementById("envSummary") || document.createElement("div");
  els.imecaSlider = document.getElementById("imecaSlider") || document.createElement("input");
  els.imecaBadge = document.getElementById("imecaBadge") || document.createElement("div");
  els.popSize = document.getElementById("popSize") || document.createElement("input");
  els.generaciones = document.getElementById("generaciones") || document.createElement("input");
  els.mutacion = document.getElementById("mutacion") || document.createElement("input");
  els.elitismo = document.getElementById("elitismo") || document.createElement("input");
  els.pesoEquidad = document.getElementById("pesoEquidad") || document.createElement("input");
  els.pesoAmbiental = document.getElementById("pesoAmbiental") || document.createElement("input");
  els.pesoEconomico = document.getElementById("pesoEconomico") || document.createElement("input");
  els.btnResetDefaults = document.getElementById("btnResetDefaults") || document.createElement("button");
  els.btnRun = document.getElementById("btnRun") || document.createElement("button");
  els.btnStop = document.getElementById("btnStop") || document.createElement("button");
  els.generationLabel = document.getElementById("generationLabel") || document.createElement("div");
  els.fitnessLabel = document.getElementById("fitnessLabel") || document.createElement("div");
  els.progressFill = document.getElementById("progressFill") || document.createElement("div");
  els.logBox = document.getElementById("logBox") || document.createElement("div");
  els.globalStatus = document.getElementById("globalStatus") || document.createElement("div");
  els.btnExport = document.getElementById("btnExport") || document.createElement("button");
  els.statsStrip = document.getElementById("statsStrip") || document.createElement("div");
  els.statZona = document.getElementById("statZona") || document.createElement("div");
  els.statFitness = document.getElementById("statFitness") || document.createElement("div");
  els.statH0  = document.getElementById("statH0")  || document.createElement("div");
  els.statH1  = document.getElementById("statH1")  || document.createElement("div");
  els.statH2  = document.getElementById("statH2")  || document.createElement("div");
  els.statH00 = document.getElementById("statH00") || document.createElement("div"); // legacy
  els.hybridSummary = document.getElementById("hybridSummary") || document.createElement("div");
  els.vehHolograma = document.getElementById("vehHolograma") || document.createElement("select");
  els.vehDigito = document.getElementById("vehDigito") || document.createElement("select");
  els.calendarPanel = document.getElementById("calendarPanel") || document.createElement("div");
  els.calendarTitle = document.getElementById("calendarTitle") || document.createElement("div");
  els.calendarGrid = document.getElementById("calendarGrid") || document.createElement("div");
  els.dayDetail = document.getElementById("dayDetail") || document.createElement("div");
  els.monthTabsWrap = document.getElementById("monthTabsWrap") || document.createElement("div");
  els.resultsContainer = document.getElementById("resultsContainer") || document.createElement("div");
}

function getConfigDefaults(payload) {
  const defaults = payload?.defaults || payload || {};
  return {
    params: { ...FALLBACK_DEFAULTS.params, ...(defaults.params || {}) },
    ui: { ...FALLBACK_DEFAULTS.ui, ...(defaults.ui || {}) },
    grupos_placa: payload?.grupos_placa || defaults.grupos_placa || FALLBACK_GRUPOS_PLACA,
  };
}

function populateDigitOptions(gruposPlaca) {
  if (!els.vehDigito) return;
  const digits = new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  for (const value of Object.values(gruposPlaca || {})) {
    if (!Array.isArray(value)) continue;
    for (const digit of value) {
      const num = Number(digit);
      if (!Number.isNaN(num)) digits.add(num);
    }
  }

  const previousValue = els.vehDigito.value || FALLBACK_DEFAULTS.ui.veh_digito;
  els.vehDigito.innerHTML = "";

  const optionAll = document.createElement("option");
  optionAll.value = "all";
  optionAll.textContent = "Todos";
  els.vehDigito.appendChild(optionAll);

  [...digits].sort((a, b) => a - b).forEach((digit) => {
    const option = document.createElement("option");
    option.value = String(digit);
    option.textContent = String(digit);
    els.vehDigito.appendChild(option);
  });

  els.vehDigito.value = [...els.vehDigito.options].some(opt => opt.value === previousValue)
    ? previousValue
    : FALLBACK_DEFAULTS.ui.veh_digito;
}

function applyConfigToUI(config) {
  const normalized = getConfigDefaults(config);
  state.defaults = normalized;

  els.popSize.value = normalized.params.pop_size;
  els.generaciones.value = normalized.params.generaciones;
  els.mutacion.value = normalized.params.mutacion;
  els.elitismo.value = normalized.params.elitismo;
  els.pesoEquidad.value = normalized.params.peso_equidad;
  els.pesoAmbiental.value = normalized.params.peso_ambiental_critico;
  els.pesoEconomico.value = normalized.params.peso_economico;
  els.imecaSlider.value = normalized.ui.imeca;
  els.startMonth.value = normalized.params.start_month;
  els.horizonteMeses.value = normalized.params.meses;

  if (els.vehHolograma) {
    els.vehHolograma.value = normalized.ui.veh_holograma;
  }
  populateDigitOptions(normalized.grupos_placa);
  if (els.vehDigito) {
    els.vehDigito.value = normalized.ui.veh_digito;
  }
  syncClimateControls("imeca");
  updateEnvSummary();
}

function imecaClassify(value) {
  const imeca = Number(value);
  if (imeca <= 50) return { label: "Buena", color: "#16a34a" };
  if (imeca <= 100) return { label: "Aceptable", color: "#eab308" };
  if (imeca <= 150) return { label: "Mala", color: "#f97316" };
  if (imeca <= 200) return { label: "Muy Mala", color: "#ef4444" };
  return { label: "Extremadamente Mala", color: "#8b5cf6" };
}

function updateImecaBadgeOnly(value) {
  if (!els.imecaBadge) return;
  const cls = imecaClassify(value);
  els.imecaBadge.textContent = `${cls.label} — ${Number(value)}`;
  els.imecaBadge.style.backgroundColor = cls.color;
}

function interpolatePoints(value, points, xKey, yKey) {
  if (!Array.isArray(points) || points.length === 0) return value;
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) return points[0][yKey];
  if (numericValue <= points[0][xKey]) return points[0][yKey];
  if (numericValue >= points[points.length - 1][xKey]) return points[points.length - 1][yKey];
  for (let index = 0; index < points.length - 1; index++) {
    const left = points[index];
    const right = points[index + 1];
    if (numericValue >= left[xKey] && numericValue <= right[xKey]) {
      const ratio = (numericValue - left[xKey]) / (right[xKey] - left[xKey]);
      return left[yKey] + ratio * (right[yKey] - left[yKey]);
    }
  }
  return points[points.length - 1][yKey];
}

function imecaToWeight(imeca) {
  return Number(interpolatePoints(imeca, IMECA_WEIGHT_POINTS, "imeca", "weight")).toFixed(2);
}

function weightToImeca(weight) {
  const inversePoints = IMECA_WEIGHT_POINTS.map(point => ({ imeca: point.weight, weight: point.imeca }));
  return Math.round(interpolatePoints(weight, inversePoints, "imeca", "weight"));
}

function syncClimateControls(source) {
  if (!els.imecaSlider || !els.pesoAmbiental) return;
  if (source === "weight") {
    const imecaValue = weightToImeca(els.pesoAmbiental.value);
    els.imecaSlider.value = String(Math.max(0, Math.min(400, imecaValue)));
  } else {
    els.pesoAmbiental.value = imecaToWeight(els.imecaSlider.value);
  }
  updateImecaBadgeOnly(els.imecaSlider.value);
  updateEnvSummary();
}

function setRunningUi(isRunning, message) {
  if (els.btnRun) els.btnRun.disabled = isRunning;
  if (els.btnStop) els.btnStop.disabled = !isRunning;
  if (els.globalStatus) {
    els.globalStatus.textContent = message || (isRunning ? "Optimizando..." : "Listo");
  }
  if (els.logBox && isRunning) {
    els.logBox.innerHTML = "<p>Iniciando algoritmo...</p><p>Procesando... esto puede tomar unos minutos.</p>";
  }
}

function setResultsVisible(visible) {
  if (els.calendarPanel) els.calendarPanel.classList.toggle("hidden", !visible);
  if (els.statsStrip) els.statsStrip.classList.toggle("hidden", !visible);
  if (els.hybridSummary) els.hybridSummary.classList.toggle("hidden", !visible);
  if (els.btnExport) els.btnExport.disabled = !visible;
  if (els.resultsContainer) {
    els.resultsContainer.classList.toggle("hidden", visible);
    els.resultsContainer.textContent = visible ? "" : "Ejecuta el modelo para ver el calendario óptimo.";
  }
}

function normalizeResultForUI(result) {
  if (!result) return null;
  const meses = result?.mejor_solucion?.meses;
  if (!Array.isArray(meses)) {
    return result?.calendario_meses ? result : null;
  }
  const grupos = { Amarillo:[5,6], Rosa:[7,8], Rojo:[3,4], Verde:[1,2], Azul:[9,0] };
  const calendario = {};

  const contaminationLabelMap = {
    buena: "Buena",
    aceptable: "Aceptable",
    mala: "Mala",
    muy_mala: "Muy Mala",
    extrema: "Extremadamente Mala",
  };

  for (const mesData of meses) {
    const key = `${mesData.year}-${String(mesData.mes).padStart(2,"0")}`;
    const castigosH00 = {};
    const castigosH0 = {};
    const castigosH1 = {};
    const castigosH2 = {};
    for (const [color, cfg] of Object.entries(mesData?.h00?.por_color || {})) {
      const dia = (cfg.dia_base || "").toLowerCase();
      const diaNormal = dia === "miercoles" ? "Miércoles" : `${dia.slice(0,1).toUpperCase()}${dia.slice(1)}`;
      const horario = `${String(cfg.horario?.[0] ?? 5).padStart(2, "0")}:00 a ${String(cfg.horario?.[1] ?? 22).padStart(2, "0")}:00`;
      const zona = `${(cfg.zona || "total").slice(0, 1).toUpperCase()}${(cfg.zona || "total").slice(1)}`;
      castigosH00[color] = {
        placas: grupos[color] || [], dia_normal: diaNormal, dias_extra: [],
        fechas_restriccion: Array.isArray(cfg.fechas_restriccion) ? cfg.fechas_restriccion : [],
        sabados: Array.isArray(cfg.sabados) ? cfg.sabados : [],
        total_sabados_castigados: 0,
        horario: horario,
        zona: zona,
      };
    }
    for (const [color, cfg] of Object.entries(mesData?.h0?.por_color || {})) {
      const dia = (cfg.dia_base || "").toLowerCase();
      const diaNormal = dia === "miercoles" ? "Miércoles" : `${dia.slice(0,1).toUpperCase()}${dia.slice(1)}`;
      const horario = `${String(cfg.horario?.[0] ?? 5).padStart(2, "0")}:00 a ${String(cfg.horario?.[1] ?? 22).padStart(2, "0")}:00`;
      const zona = `${(cfg.zona || "total").slice(0, 1).toUpperCase()}${(cfg.zona || "total").slice(1)}`;
      castigosH0[color] = {
        placas: grupos[color] || [], dia_normal: diaNormal, dias_extra: [],
        fechas_restriccion: Array.isArray(cfg.fechas_restriccion) ? cfg.fechas_restriccion : [],
        sabados: Array.isArray(cfg.sabados) ? cfg.sabados : [],
        total_sabados_castigados: 0,
        horario: horario,
        zona: zona,
      };
    }
    for (const [color, cfg] of Object.entries(mesData?.h1?.por_color || {})) {
      const dia = (cfg.dia_base || "").toLowerCase();
      const diaNormal = dia === "miercoles" ? "Miércoles" : `${dia.slice(0,1).toUpperCase()}${dia.slice(1)}`;
      const horario = `${String(cfg.horario?.[0] ?? 5).padStart(2, "0")}:00 a ${String(cfg.horario?.[1] ?? 22).padStart(2, "0")}:00`;
      const zona = `${(cfg.zona || "total").slice(0, 1).toUpperCase()}${(cfg.zona || "total").slice(1)}`;
      // fechas_ligeras: [{fecha, horario, zona}, ...] — cada entrada trae su propio schedule
      const fechasLigerasH1 = Array.isArray(cfg.fechas_ligeras) ? cfg.fechas_ligeras : [];
      castigosH1[color] = {
        placas: grupos[color] || [], dia_normal: diaNormal, dias_extra: [],
        sabados: Array.isArray(cfg.sabados) ? cfg.sabados : [],
        total_sabados_castigados: Array.isArray(cfg.sabados) ? cfg.sabados.length : 0,
        horario: horario,
        zona: zona,
        fechas_ligeras: fechasLigerasH1,
      };
    }
    for (const [color, cfg] of Object.entries(mesData?.h2?.por_color || {})) {
      const dia = (cfg.dia_base || "").toLowerCase();
      const diaNormal = dia === "miercoles" ? "Miércoles" : `${dia.slice(0,1).toUpperCase()}${dia.slice(1)}`;
      const horario = `${String(cfg.horario?.[0] ?? 5).padStart(2, "0")}:00 a ${String(cfg.horario?.[1] ?? 22).padStart(2, "0")}:00`;
      const zona = `${(cfg.zona || "total").slice(0, 1).toUpperCase()}${(cfg.zona || "total").slice(1)}`;
      const diasExtra = (cfg.extras || []).map(iso => {
        const [yr, mo, dy] = iso.split("-").map(Number);
        const dt = new Date(yr, mo - 1, dy);
        const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1;
        return DAYS[idx];
      });
      // fechas_ligeras: [{fecha, horario, zona}, ...] — mismo formato que H1
      const fechasLigerasH2 = Array.isArray(cfg.fechas_ligeras) ? cfg.fechas_ligeras : [];
      castigosH2[color] = {
        placas: grupos[color] || [], dia_normal: diaNormal,
        dias_extra: diasExtra, fechas_extra: Array.isArray(cfg.extras) ? cfg.extras : [],
        fechas_restriccion: Array.isArray(cfg.fechas_restriccion) ? cfg.fechas_restriccion : [],
        sabados: Array.isArray(cfg.sabados) ? cfg.sabados : [],
        restriccion_total: Boolean(cfg.restriccion_total),
        total_sabados_castigados: Array.isArray(cfg.sabados) ? cfg.sabados.length : 0,
        horario: horario,
        zona: zona,
        fechas_ligeras: fechasLigerasH2,
      };
    }
    const h1Verde = mesData?.h1?.por_color?.Verde || { horario:[5,22], zona:"total" };
    const h2Verde = mesData?.h2?.por_color?.Verde || { horario:[5,22], zona:"total" };
    const estado = mesData.contaminacion || "aceptable";
    const estadoLabel = contaminationLabelMap[estado] || estado;

    calendario[key] = {
      estado_contaminacion: estadoLabel,
      castigos_hologramas: {
        H00: Object.values(castigosH00).every(info => (info.fechas_restriccion || []).length === 0) ? { regla: "Ninguno. Circulan libremente." } : {
          horario: `${String((mesData?.h00?.por_color?.Verde?.horario?.[0] ?? 5)).padStart(2,"0")}:00 a ${String((mesData?.h00?.por_color?.Verde?.horario?.[1] ?? 22)).padStart(2,"0")}:00`,
          zona: `${((mesData?.h00?.por_color?.Verde?.zona || "total").slice(0,1).toUpperCase())}${((mesData?.h00?.por_color?.Verde?.zona || "total").slice(1))}`,
          colores: castigosH00,
        },
        H0: Object.keys(castigosH0).length > 0 ? {
          horario: `${String((mesData?.h0?.por_color?.Verde?.horario?.[0] ?? 5)).padStart(2,"0")}:00 a ${String((mesData?.h0?.por_color?.Verde?.horario?.[1] ?? 22)).padStart(2,"0")}:00`,
          zona: `${((mesData?.h0?.por_color?.Verde?.zona || "total").slice(0,1).toUpperCase())}${((mesData?.h0?.por_color?.Verde?.zona || "total").slice(1))}`,
          colores: castigosH0,
        } : { regla: "Ninguno. Circulan libremente." },
        H1: {
          horario: `${String(h1Verde.horario?.[0]??5).padStart(2,"0")}:00 a ${String(h1Verde.horario?.[1]??22).padStart(2,"0")}:00`,
          zona: `${(h1Verde.zona||"total").slice(0,1).toUpperCase()}${(h1Verde.zona||"total").slice(1)}`,
          colores: castigosH1,
        },
        H2: {
          horario: `${String(h2Verde.horario?.[0]??5).padStart(2,"0")}:00 a ${String(h2Verde.horario?.[1]??22).padStart(2,"0")}:00`,
          zona: `${(h2Verde.zona||"total").slice(0,1).toUpperCase()}${(h2Verde.zona||"total").slice(1)}`,
          colores: castigosH2,
        },
      },
    };
  }
  return { ...result, calendario_meses: calendario };
}

function renderMonthTabs() {
  if (!state.result?.calendario_meses) {
    if (els.monthTabsWrap) els.monthTabsWrap.innerHTML = "";
    return;
  }
  state.monthKeys = Object.keys(state.result.calendario_meses).sort();
  if (els.monthTabsWrap) {
    els.monthTabsWrap.innerHTML = "";
    state.monthKeys.forEach((key, idx) => {
      const btn = document.createElement("button");
      btn.textContent = key;
      btn.className = "month-tab-btn";
      btn.classList.toggle("active", idx === state.monthIndex);
      btn.addEventListener("click", () => selectMonth(idx));
      els.monthTabsWrap.appendChild(btn);
    });
  }
}

function selectMonth(idx) {
  state.monthIndex = idx;
  state.selectedDate = null;
  renderMonthTabs();
  renderCalendarGrid();
  renderDayDetail();
}

function renderCalendarGrid() {
  if (!els.calendarGrid) return;
  els.calendarGrid.innerHTML = "";
  if (!state.monthKeys.length) return;
  const monthKey = state.monthKeys[state.monthIndex];
  if (!monthKey) return;
  const [year, month] = monthKey.split("-").map(Number);
  const firstDay = new Date(year, month - 1, 1);
  const lastDay = new Date(year, month, 0);
  const startDate = new Date(firstDay);
  startDate.setDate(startDate.getDate() - (firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1));
  const monthData = state.result?.calendario_meses?.[monthKey];
  const holograma = els.vehHolograma?.value || "H1";
  const digitoFilter = els.vehDigito?.value || "all";
  const weekDayLabels = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sab", "Dom"];
  weekDayLabels.forEach(day => {
    const h = document.createElement("div");
    h.className = "weekday";
    h.textContent = day;
    els.calendarGrid.appendChild(h);
  });
  let currentDate = new Date(startDate);
  const endVisibleDate = new Date(lastDay);
  const lastDayIndex = lastDay.getDay() === 0 ? 6 : lastDay.getDay() - 1;
  endVisibleDate.setDate(endVisibleDate.getDate() + (6 - lastDayIndex));
  while (currentDate <= endVisibleDate) {
    const dayEl = document.createElement("div");
    dayEl.className = "day-cell";
    const dateStr = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, "0")}-${String(currentDate.getDate()).padStart(2, "0")}`;
    const isOutsideMonth = currentDate.getMonth() !== month - 1;
    if (isOutsideMonth) {
      dayEl.classList.add("outside");
      dayEl.setAttribute("aria-hidden", "true");
    } else {
      const number = document.createElement("span");
      number.className = "day-number";
      number.textContent = currentDate.getDate();
      dayEl.appendChild(number);
    }
    if (!isOutsideMonth) {
      const restrictedDigits = getRestrictedDigitsForDay(monthData, holograma, currentDate);
      const displayDigits = digitoFilter === "all" ? restrictedDigits : restrictedDigits.filter(d => parseInt(digitoFilter) === d);
      if (digitoFilter !== "all" && displayDigits.length > 0) {
        dayEl.classList.add("blocked");
      }
      if (displayDigits.length > 0) {
        const dotsContainer = document.createElement("div");
        dotsContainer.className = "day-dot-wrap";
        displayDigits.forEach(digit => {
          const dot = document.createElement("span");
          dot.className = "day-dot";
          dot.style.backgroundColor = DIGIT_COLOR[digit] || "#999";
          dotsContainer.appendChild(dot);
        });
        dayEl.appendChild(dotsContainer);
      }
      dayEl.addEventListener("click", () => {
        state.selectedDate = dateStr;
        renderCalendarGrid();
        renderDayDetail();
      });
      dayEl.style.cursor = "pointer";
      if (state.selectedDate === dateStr) {
        dayEl.classList.add("selected");
      }
    }
    els.calendarGrid.appendChild(dayEl);
    currentDate.setDate(currentDate.getDate() + 1);
  }
  if (els.calendarTitle) {
    els.calendarTitle.textContent = `${MONTH_NAMES[month - 1]} ${year}`;
  }
}

function getRestrictedDigitsForDay(monthData, holograma, dt) {
  if (!monthData) return [];
  const dayName = DAYS[dt.getDay() === 0 ? 6 : dt.getDay() - 1];
  const isoDate = dt.toISOString().split("T")[0];
  const castigos = monthData?.castigos_hologramas?.[holograma] || {};
  const colores = castigos.colores || {};
  const saturdayNumber = getSaturdayNumber(dt);
  const restrictedDigits = [];
  const isDateOnlyHologram = holograma === "H0" || holograma === "H00";

  for (const [color, info] of Object.entries(colores)) {
    const placas = info.placas || [];
    const isNormalDay = !isDateOnlyHologram && info.dia_normal === dayName;
    const isSaturday = dayName === "Sábado";
    const dateBasedRestricted = Array.isArray(info.fechas_restriccion) && info.fechas_restriccion.includes(isoDate);
    const isSaturdayRestricted = !isDateOnlyHologram && isSaturday && Array.isArray(info.sabados) && info.sabados.includes(saturdayNumber);
    const isExtraDay = !isDateOnlyHologram && Array.isArray(info.fechas_extra) && info.fechas_extra.includes(isoDate);
    if (isDateOnlyHologram ? dateBasedRestricted : (isNormalDay || isSaturdayRestricted || isExtraDay || dateBasedRestricted)) {
      placas.forEach(p => restrictedDigits.push(p));
    }
  }
  return [...new Set(restrictedDigits)].sort((a, b) => a - b);
}

function getSaturdayNumber(dt) {
  if (DAYS[dt.getDay() === 0 ? 6 : dt.getDay() - 1] !== "Sábado") return -1;
  const year = dt.getFullYear();
  const month = dt.getMonth();
  const firstDay = new Date(year, month, 1);
  const firstSaturday = new Date(year, month, 1 + ((6 - firstDay.getDay() + 7) % 7));
  const saturdayNum = Math.floor((dt.getDate() - firstSaturday.getDate()) / 7) + 1;
  return saturdayNum;
}

function renderDayDetail() {
  if (!state.selectedDate || !els.dayDetail) {
    if (els.dayDetail) els.dayDetail.textContent = "Selecciona un día para ver el detalle.";
    return;
  }
  const [yr, mo, dy] = state.selectedDate.split("-").map(Number);
  const dt = new Date(yr, mo - 1, dy);
  const dayName = DAYS[dt.getDay() === 0 ? 6 : dt.getDay() - 1];
  const year = dt.getFullYear();
  const month = dt.getMonth() + 1;
  const monthKey = `${year}-${String(month).padStart(2,"0")}`;
  const monthData = state.result?.calendario_meses?.[monthKey];
  if (!monthData) {
    els.dayDetail.innerHTML = "<strong>Sin información para esta fecha.</strong>";
    return;
  }
  const holograma = els.vehHolograma?.value || "H1";
  const castigos = monthData.castigos_hologramas?.[holograma] || {};
  const colores = castigos.colores || {};
  let dayHorario = castigos.horario || "Libre";
  let dayZona = castigos.zona || "Total";
  let matchedColors = [];
  const isDateOnlyHologram = holograma === "H0" || holograma === "H00";

  for (const [color, info] of Object.entries(colores)) {
    const isoDate = state.selectedDate;
    const isNormalDay = !isDateOnlyHologram && info.dia_normal === dayName;
    const isSaturday = dayName === "Sábado";
    const isSaturdayRestricted = !isDateOnlyHologram && isSaturday && Array.isArray(info.sabados) && info.sabados.includes(getSaturdayNumber(dt));
    const isExtraDay = !isDateOnlyHologram && Array.isArray(info.fechas_extra) && info.fechas_extra.includes(isoDate);
    const isDateBasedRestricted = Array.isArray(info.fechas_restriccion) && info.fechas_restriccion.includes(isoDate);
    // Buscar si esta fecha tiene una entrada ligera propia con su horario/zona
    const lightEntry = Array.isArray(info.fechas_ligeras)
      ? info.fechas_ligeras.find(e => e.fecha === isoDate)
      : null;
    if (isDateOnlyHologram ? isDateBasedRestricted : (isNormalDay || isSaturdayRestricted || isExtraDay || isDateBasedRestricted)) {
      matchedColors.push({ color, info });
      if (isDateOnlyHologram ? isDateBasedRestricted : (isNormalDay || isSaturdayRestricted || isDateBasedRestricted)) {
        if (lightEntry) {
          // Usar el horario y zona específicos de esta entrada ligera
          const h = lightEntry.horario || [5, 16];
          dayHorario = `${String(h[0]).padStart(2,"0")}:00 a ${String(h[1]).padStart(2,"0")}:00`;
          const z = lightEntry.zona || "total";
          dayZona = `${z.slice(0,1).toUpperCase()}${z.slice(1)}`;
        } else {
          dayHorario = info.horario || castigos.horario || "Libre";
          dayZona = info.zona || castigos.zona || "Total";
        }
      }
    }
  }
  let html = `<strong>${dayName}, ${dt.getDate()} de ${MONTH_NAMES[month-1]}</strong><br/>`;
  html += `<span class="detail-label">Holograma ${holograma}:</span> ${dayHorario} | Zona: ${dayZona}<br/>`;
  if (matchedColors.length > 0) {
    const digitosRestringidos = [...new Set(
      matchedColors
        .flatMap(({ info }) => Array.isArray(info.placas) ? info.placas : [])
        .map(Number)
        .filter(d => !Number.isNaN(d))
    )].sort((a, b) => a - b);
    html += `<strong>Dígitos de placa restringidos:</strong> ${digitosRestringidos.join(", ") || "—"}`;
  } else {
    html += `<em>Sin restricciones activas.</em>`;
  }
  els.dayDetail.innerHTML = html;
}

// ─── Hybrid summary ──────────────────────────────────────────────────────────
function renderHybridSummary(result) {
  if (!els.hybridSummary) return;
  const meses = result?.mejor_solucion?.meses || result?.analytics?.por_mes || [];
  if (!meses.length) { els.hybridSummary.innerHTML = ""; return; }
  const m0 = meses[0];
  const fitness = result?.mejor_fitness ?? "—";
  const imeca = result?.parametros?.nivel_imeca ?? "—";
  const contLbl = { buena:"Buena", aceptable:"Aceptable", mala:"Mala", muy_mala:"Muy Mala", extrema:"Extrema" };
  const cont = m0?.contaminacion || "—";
  els.hybridSummary.innerHTML = `
    <h4>Resumen del Modelo</h4>
    <div class="hybrid-metrics">
      <span class="metric-chip">Fitness promedio: <strong>${typeof fitness === "number" ? fitness.toFixed(1) : fitness}</strong></span>
      <span class="metric-chip">IMECA: <strong>${imeca}</strong></span>
      <span class="metric-chip">Contaminación: <strong>${contLbl[cont] || cont}</strong></span>
      <span class="metric-chip">Meses: <strong>${meses.length}</strong></span>
    </div>`;
}

// ─── Stats strip ─────────────────────────────────────────────────────────────
// Muestra los días restringidos del color Azul (placas terminadas en 0 y 9).
function renderStatsStrip(result) {
  if (!result) return;
  const meses = result?.mejor_solucion?.meses || [];
  if (!meses.length) return;
  const m0 = meses[0];

  // Datos del color Azul (placas 0,9) en el primer mes
  const h0Azul = m0?.h0?.por_color?.Azul || {};
  const h1Azul = m0?.h1?.por_color?.Azul || {};
  const h2Azul = m0?.h2?.por_color?.Azul || {};

  // Zona y fitness
  if (els.statZona) {
    const z = h2Azul.zona || "total";
    els.statZona.textContent = z.charAt(0).toUpperCase() + z.slice(1);
  }
  if (els.statFitness) {
    els.statFitness.textContent =
      typeof result.mejor_fitness === "number" ? result.mejor_fitness.toFixed(1) : "—";
  }

  // Contar cuántos días de la semana (día fijo de Azul) hay en el mes
  // Ej: si Azul tiene dia_base="viernes" y el mes tiene 4 viernes → diasNorm=4
  const year     = m0?.year  || new Date().getFullYear();
  const mes      = m0?.mes   || (new Date().getMonth() + 1);
  const diaBase  = (h2Azul.dia_base || h1Azul.dia_base || "viernes").toLowerCase();
  const wdMap    = { lunes:1, martes:2, miercoles:3, jueves:4, viernes:5 };
  const targetWd = wdMap[diaBase] ?? 5;                     // getDay(): 1=lun … 5=vie
  let diasNorm   = 0;
  const totalDias = new Date(year, mes, 0).getDate();
  for (let d = 1; d <= totalDias; d++) {
    if (new Date(year, mes - 1, d).getDay() === targetWd) diasNorm++;
  }

  const DIAS_ES = { lunes:"Lun", martes:"Mar", miercoles:"Mié",
                    jueves:"Jue", viernes:"Vie" };
  const diaCorto = DIAS_ES[diaBase] || diaBase;

  // H0: días normales restringidos (contingencia)
  if (els.statH0) {
    const h0Dias = h0Azul.fechas_restriccion?.length ?? 0;
    els.statH0.textContent = h0Dias > 0 ? `${h0Dias} días (${diaCorto})` : "Libre";
  }

  // H1: días normales del mes + sábados
  if (els.statH1) {
    const sabs = h1Azul.sabados?.length ?? 0;
    els.statH1.textContent =
      `${diasNorm} días norm. + ${sabs} sáb.`;
  }

  // H2: días normales + sábados + días extra
  if (els.statH2) {
    const sabs   = h2Azul.sabados?.length ?? 0;
    const extras = (h2Azul.extras ?? h2Azul.fechas_restriccion ?? []).length;
    const extStr = extras > 0 ? ` + ${extras} ext.` : "";
    els.statH2.textContent =
      `${diasNorm} días norm. + ${sabs} sáb.${extStr}`;
  }
}

// ─── API helpers ─────────────────────────────────────────────────────────────
async function fetchJSON(url, opts) {
  try {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    return null;
  }
}

function updateEnvSummary() { /* reemplazado por panel ETL dinámico */ }

// ── Panel ETL dinámico ────────────────────────────────────────────────────

// Metadatos de cada tipo de archivo para la UI
const ETL_TIPOS = {
  verificacion:   { label: "Verificación automotriz",   accept: ".csv",        carpeta: "1.Factores de Emisión",              nombre: "verificacion_automotriz.csv" },
  ias:            { label: "Calidad del aire (IAS)",    accept: ".csv",        carpeta: "1.Factores de Emisión",              nombre: "ias_calidad_aire.csv" },
  vmrc:           { label: "Parque vehicular (VMRC)",   accept: ".csv",        carpeta: "2.Composición del Parque Vehicular", nombre: "vmrc_parque_vehicular.csv" },
  contaminantes:  { label: "Contaminantes",             accept: ".csv",        carpeta: "3.Curvas de Demanda y Tráfico",      nombre: "contaminantes.csv" },
  eod_semana_xlsx:{ label: "EOD entre semana (XLSX)",   accept: ".xlsx",       carpeta: "3.Curvas de Demanda y Tráfico",      nombre: "eod_entre_semana.xlsx" },
  eod_sabado:     { label: "EOD sábado (XLSX)",         accept: ".xlsx",       carpeta: "3.Curvas de Demanda y Tráfico",      nombre: "eod_sabado.xlsx" },
};

// Estado interno de cada archivo (ok/error/ausente + mensaje)
const etlState = {};

function renderEtlFileList(archivosBackend = {}) {
  const wrap = els.etlFileList;
  if (!wrap) return;
  wrap.innerHTML = "";

  Object.entries(ETL_TIPOS).forEach(([tipo, meta]) => {
    const info    = archivosBackend[tipo] || {};
    const existe  = info.existe ?? false;
    const tamKB   = info.tamaño_kb;
    const rowState = etlState[tipo];

    const rowClass = rowState?.ok === true  ? "ok"
                   : rowState?.ok === false ? "error"
                   : rowState?.loading      ? "loading"
                   : existe                 ? "ok" : "";

    const row = document.createElement("div");
    row.className = `etl-file-row ${rowClass}`;
    row.dataset.tipo = tipo;

    row.innerHTML = `
      <div class="etl-status-dot"></div>
      <div class="etl-file-info">
        <div class="etl-file-name">${meta.label}</div>
        <div class="etl-file-desc">${meta.carpeta}/<strong>${meta.nombre}</strong></div>
      </div>
      <div class="etl-file-size">${existe ? (tamKB > 1024 ? (tamKB/1024).toFixed(1)+" MB" : tamKB+" KB") : "no cargado"}</div>
      <label style="cursor:pointer">
        <input type="file" accept="${meta.accept}" style="display:none" data-tipo="${tipo}" />
        <span class="etl-upload-btn">Subir</span>
      </label>`;

    // Mensaje de estado (validación)
    if (rowState?.msg) {
      const msgDiv = document.createElement("div");
      msgDiv.className = `etl-msg ${rowState.ok ? "ok" : "err"}`;
      msgDiv.textContent = rowState.msg;
      row.appendChild(msgDiv);
    }

    // Evento al seleccionar archivo
    const fileInput = row.querySelector("input[type=file]");
    fileInput?.addEventListener("change", async e => {
      const file = e.target.files?.[0];
      if (!file) return;
      await subirArchivoEtl(tipo, file);
    });

    wrap.appendChild(row);
  });
}

async function subirArchivoEtl(tipo, file) {
  etlState[tipo] = { loading: true };
  renderEtlFileList(_etlArchivosBackend);

  const fd = new FormData();
  fd.append("archivo", file);
  fd.append("tipo", tipo);

  try {
    const resp = await fetch("/api/subir-archivo", { method: "POST", body: fd });
    const data = await resp.json();

    if (resp.ok && data.ok) {
      etlState[tipo] = { ok: true, msg: data.mensaje };
      // Actualizar tamaño en caché local
      if (_etlArchivosBackend[tipo]) {
        _etlArchivosBackend[tipo].existe = true;
        _etlArchivosBackend[tipo].tamaño_kb = Math.round(file.size / 1024 * 10) / 10;
      }
      // Si es IAS, también actualizar el entorno
      if (tipo === "ias") {
        await ejecutarEtlIas(etlState[tipo]);
      }
    } else {
      const errMsg = data.error || data.mensaje || `HTTP ${resp.status}`;
      etlState[tipo] = { ok: false, msg: errMsg };
    }
  } catch (err) {
    etlState[tipo] = { ok: false, msg: `Error de red: ${err.message}` };
  }

  renderEtlFileList(_etlArchivosBackend);
}

async function ejecutarEtlIas(estadoPrevio) {
  // El archivo IAS ya fue guardado en la ruta canónica; ahora pedimos al
  // backend que actualice entorno_cdmx.json con los nuevos datos
  try {
    const fd = new FormData();
    // Obtener el archivo canónico que ya fue guardado
    const resp = await fetch("/api/etl-ias", {
      method: "POST",
      body: (() => {
        // Usamos la ruta canónica ya guardada — el servidor sabe dónde está
        // Enviamos form vacío con señal para usar archivo guardado
        const f = new FormData();
        f.append("usar_canonico", "1");
        return f;
      })(),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.ajustes_mensuales) {
        renderIasPreview(data.ajustes_mensuales);
        if (els.iasBadge) {
          els.iasBadge.textContent = "Datos reales cargados";
          els.iasBadge.className = "ias-badge loaded";
        }
      }
    }
  } catch (_) { /* silencioso */ }
}

let _etlArchivosBackend = {};

async function cargarEstadoArchivos() {
  try {
    const data = await fetchJSON("/api/archivos");
    if (data && typeof data === "object") {
      _etlArchivosBackend = data;
      // Verificar si IAS ya tiene datos reales
      if (data.ias?.existe && els.iasBadge) {
        els.iasBadge.textContent = "Datos reales en servidor";
        els.iasBadge.className = "ias-badge loaded";
      }
      renderEtlFileList(data);
    }
  } catch (_) {
    renderEtlFileList({});
  }
}

async function verifyBackend() {
  const data = await fetchJSON("/api/config-inicial");
  if (data?.status === "ok") {
    els.demoStatusText.textContent = "Backend activo. Datos del entorno cargados.";
    applyConfigToUI(data);
    const lastResult = await fetchJSON("/api/ultimo-resultado");
    if (lastResult && (lastResult.mejor_solucion || lastResult.calendario_meses)) {
      state.result = normalizeResultForUI(lastResult);
      renderAll();
      setResultsVisible(true);
      renderAnalytics(state.result, lastResult.analytics);
    }
  } else {
    els.demoStatusText.textContent = "Backend no disponible. Inicia el servidor primero.";
  }
}

function buildFormData() {
  const fd = new FormData();
  const params = {
    pop_size:               parseInt(els.popSize?.value || "100", 10),
    generaciones:           parseInt(els.generaciones?.value || "120", 10),
    mutacion:               parseFloat(els.mutacion?.value || "0.05"),
    elitismo:               parseInt(els.elitismo?.value || "2", 10),
    peso_equidad:           parseFloat(els.pesoEquidad?.value || "1"),
    peso_ambiental_critico: parseFloat(els.pesoAmbiental?.value || "2.2"),
    peso_economico:         parseFloat(els.pesoEconomico?.value || "1.55"),
    nivel_imeca:            parseInt(els.imecaSlider?.value || "151", 10),
    start_month:            els.startMonth?.value || "2026-04",
    meses:                  parseInt(els.horizonteMeses?.value || "6", 10),
  };
  // Add strategy selections
  const selEl  = document.getElementById("estrategiaSel");
  const cruzEl = document.getElementById("estrategiaCruz");
  const mutEl  = document.getElementById("estrategiaMut");
  params.estrategia_seleccion = selEl?.value  || "ruleta";
  params.estrategia_cruza     = cruzEl?.value || "un_punto";
  params.estrategia_mutacion  = mutEl?.value  || "uniforme";
  fd.append("params", JSON.stringify(params));
  // Los archivos ETL ya se subieron individualmente vía /api/subir-archivo.
  // El backend los usa desde sus rutas canónicas al ejecutar el ETL.
  return fd;
}

async function runOptimization() {
  if (state.running) return;
  state.running = true;
  state.stopRequested = false;
  state.runController = new AbortController();
  setRunningUi(true, "Optimizando...");
  if (els.logBox) els.logBox.innerHTML = "<p>Iniciando optimización.</p><p>El AG puede tardar varios minutos según el número de generaciones.</p>";
  if (els.progressFill) els.progressFill.style.width = "0%";

  try {
    const fd = buildFormData();
    const generaciones = parseInt(els.generaciones?.value || "120", 10);

    // Progress simulation while waiting
    let progress = 0;
    const progressInterval = setInterval(() => {
      if (!state.running) { clearInterval(progressInterval); return; }
      progress = Math.min(progress + (100 / (generaciones * 0.9)), 92);
      if (els.progressFill) els.progressFill.style.width = `${progress}%`;
      const gen = Math.floor(progress / 100 * generaciones);
      if (els.generationLabel) els.generationLabel.textContent = `Generación: ~${gen} / ${generaciones}`;
    }, 600);

    const raw = await fetch("/api/run", {
      method: "POST",
      body: fd,
      signal: state.runController.signal,
    });

    clearInterval(progressInterval);
    if (els.progressFill) els.progressFill.style.width = "100%";

    if (!raw.ok) throw new Error(`HTTP ${raw.status}`);
    const data = await raw.json();
    if (data?.error) throw new Error(data.error);

    state.result = normalizeResultForUI(data);
    renderAll();
    setResultsVisible(true);
    renderAnalytics(state.result, data.analytics);
    setRunningUi(false, "Optimización completada");
    if (els.generationLabel) els.generationLabel.textContent = `Generación: ${generaciones} / ${generaciones}`;
    if (els.fitnessLabel && data.mejor_fitness != null) {
      els.fitnessLabel.textContent = `Mejor fitness: ${Number(data.mejor_fitness).toFixed(2)}`;
    }
    logLine("Resultado recibido y renderizado.");
  } catch (e) {
    if (e.name === "AbortError") {
      logLine("Optimización detenida por el usuario.");
      setRunningUi(false, "Detenido");
    } else {
      logLine(`Error: ${e.message}`);
      setRunningUi(false, "Error");
    }
  } finally {
    state.running = false;
    state.runController = null;
  }
}

function logLine(text) {
  if (!els.logBox) return;
  const p = document.createElement("p");
  p.textContent = text;
  els.logBox.appendChild(p);
  els.logBox.scrollTop = els.logBox.scrollHeight;
}

function renderAll() {
  if (!state.result) return;
  renderStatsStrip(state.result);
  renderHybridSummary(state.result);
  renderMonthTabs();
  renderCalendarGrid();
  renderDayDetail();
}

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYTICS — SECCIÓN 5
// ═══════════════════════════════════════════════════════════════════════════════
const analyticsState = {
  activeTab: "fitness",
  activeMesIdx: 0,
  charts: {},
};

const COLOR_MAP = {
  Verde:    { hex:"#16a34a", light:"rgba(22,163,74,0.15)",  border:"#16a34a" },
  Amarillo: { hex:"#eab308", light:"rgba(234,179,8,0.15)",  border:"#eab308" },
  Rosa:     { hex:"#ec4899", light:"rgba(236,72,153,0.15)", border:"#ec4899" },
  Rojo:     { hex:"#dc2626", light:"rgba(220,38,38,0.15)",  border:"#dc2626" },
  Azul:     { hex:"#2563eb", light:"rgba(37,99,235,0.15)",  border:"#2563eb" },
};
const GRUPOS_PLACA = { Verde:[1,2], Amarillo:[5,6], Rosa:[7,8], Rojo:[3,4], Azul:[9,0] };
const CONT_COLORS = {
  buena:"#16a34a", aceptable:"#eab308", mala:"#f97316",
  muy_mala:"#dc2626", extrema:"#7c3aed",
};
const CONT_LABELS = {
  buena:"Buena", aceptable:"Aceptable", mala:"Mala",
  muy_mala:"Muy Mala", extrema:"Extrema",
};
const DIAS_TITULO = { lunes:"Lunes", martes:"Martes", miercoles:"Miércoles", jueves:"Jueves", viernes:"Viernes" };

function destroyChart(id) {
  if (analyticsState.charts[id]) {
    analyticsState.charts[id].destroy();
    delete analyticsState.charts[id];
  }
}

function makeChart(id, config) {
  destroyChart(id);
  const canvas = document.getElementById(id);
  if (!canvas) return;
  analyticsState.charts[id] = new Chart(canvas, config);
}

function renderAnalytics(normalizedResult, rawAnalytics) {
  const section = document.getElementById("analyticsSection");
  if (!section) return;
  const anData = rawAnalytics?.por_mes || [];
  if (!anData.length) { section.classList.add("hidden"); return; }
  section.classList.remove("hidden");

  // Build month tabs
  const mesTabs = document.getElementById("analyticsMesTabs");
  if (mesTabs) {
    mesTabs.innerHTML = "";
    anData.forEach((m, i) => {
      const btn = document.createElement("button");
      btn.className = "analytics-mes-btn" + (i === analyticsState.activeMesIdx ? " active" : "");
      btn.textContent = `${MONTH_NAMES[m.mes - 1].slice(0,3)} ${m.year}`;
      btn.addEventListener("click", () => {
        analyticsState.activeMesIdx = i;
        mesTabs.querySelectorAll(".analytics-mes-btn").forEach((b,j) => b.classList.toggle("active", j===i));
        renderActiveTab(anData, normalizedResult);
      });
      mesTabs.appendChild(btn);
    });
  }

  // Tab click handlers
  document.querySelectorAll(".analytics-tab").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".analytics-tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      analyticsState.activeTab = btn.dataset.tab;
      document.querySelectorAll(".analytics-panel").forEach(p => p.classList.add("hidden"));
      const panel = document.getElementById(`tab${btn.dataset.tab.charAt(0).toUpperCase()}${btn.dataset.tab.slice(1)}`);
      if (panel) panel.classList.remove("hidden");
      renderActiveTab(anData, normalizedResult);
    };
  });

  // Show strategy info if available
  const stratDiv = document.getElementById("strategyInfo");
  if (stratDiv && normalizedResult?.estrategias_usadas) {
    const s = normalizedResult.estrategias_usadas;
    stratDiv.textContent = `Selección: ${s.seleccion} | Cruzamiento: ${s.cruza} | Mutación: ${s.mutacion}`;
    stratDiv.classList.remove("hidden");
  }

  renderActiveTab(anData, normalizedResult);
}

function renderActiveTab(anData, normalizedResult) {
  const mesData = anData[analyticsState.activeMesIdx];
  if (!mesData) return;
  switch (analyticsState.activeTab) {
    case "fitness":    renderFitnessChart(mesData); break;
    case "vars":       renderVarsCharts(mesData); break;
    case "esquema":    renderEsquema(anData, normalizedResult); break;
    case "co2":        renderCo2Charts(anData); break;
    case "individuo":  renderIndividuo(mesData, normalizedResult); break;
  }
}

// ── TAB 1: Evolución de Aptitud ──────────────────────────────────────────────
function renderFitnessChart(mesData) {
  const gens = mesData.historial_mejor?.length || 0;
  if (!gens) return;
  const labels = Array.from({ length: gens }, (_, i) => i + 1);
  const lbl = document.getElementById("fitnessMesLabel");
  if (lbl) lbl.textContent = `${MONTH_NAMES[(mesData.mes||1)-1]} ${mesData.year} · ${gens} generaciones`;

  injectDownloadBtn("tabFitness", makeDownloadBtn("Descargar PNG", () => downloadCanvas("chartFitness", `evolucion_aptitud_${MONTH_NAMES[(mesData.mes||1)-1]}_${mesData.year}`)));
  makeChart("chartFitness", {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Mejor Global",
          data: mesData.historial_mejor,
          borderColor: "#dc2626", backgroundColor: "rgba(220,38,38,0.08)",
          pointRadius: 1.5, pointHoverRadius: 4,
          borderWidth: 2, tension: 0.3, fill: false,
        },
        {
          label: "Promedio Generación",
          data: mesData.historial_promedio,
          borderColor: "#16a34a", backgroundColor: "rgba(22,163,74,0.08)",
          pointRadius: 1.5, pointHoverRadius: 4,
          borderWidth: 2, tension: 0.3, fill: false,
        },
        {
          label: "Peor Generación",
          data: mesData.historial_peor,
          borderColor: "#2563eb", backgroundColor: "rgba(37,99,235,0.06)",
          pointRadius: 1, pointHoverRadius: 3,
          borderWidth: 1.5, tension: 0.3, fill: false, borderDash: [3,3],
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { boxWidth: 14, font: { size: 12 } } },
        title: { display: false },
        tooltip: { mode: "index", intersect: false },
      },
      scales: {
        x: { title: { display: true, text: "Generación" } },
        y: { title: { display: true, text: "Aptitud (fitness)" } },
      },
      interaction: { mode: "nearest", axis: "x", intersect: false },
    },
  });
}

// ── TAB 2: Variables de Optimización ─────────────────────────────────────────
function renderVarsCharts(mesData) {
  const hvars = mesData.historial_vars || [];
  if (!hvars.length) return;
  const gens = hvars.map((_, i) => i + 1);
  const palette = ["#dc2626","#f97316","#16a34a","#2563eb","#9333ea","#0891b2"];

  injectDownloadBtn("tabVars", makeDownloadBtn("Descargar PNG (todas)", () =>
    downloadMultiCanvas(["chartVarH1","chartVarH2","chartVarExtra","chartVarH0","chartVarLH1","chartVarLH2"], "evolucion_variables")));
  const varsConfig = [
    { id: "chartVarH1",    key: "sabados_h1",       label: "Sábados H1",           max: 6  },
    { id: "chartVarH2",    key: "sabados_h2",        label: "Sábados H2",           max: 6  },
    { id: "chartVarExtra", key: "dias_extra_h2",     label: "Días Extra H2",        max: 3  },
    { id: "chartVarH0",    key: "h0_weekday_count",  label: "Días H0 Entre Semana", max: 3  },
    { id: "chartVarLH1",   key: "n_light_h1",        label: "Grupos Ligeros H1",    max: 5  },
    { id: "chartVarLH2",   key: "n_light_h2",        label: "Grupos Ligeros H2",    max: 5  },
  ];

  varsConfig.forEach(({ id, key, label, max }, ci) => {
    const data = hvars.map(v => v[key] ?? 0);
    makeChart(id, {
      type: "line",
      data: {
        labels: gens,
        datasets: [{
          label,
          data,
          borderColor: palette[ci],
          backgroundColor: palette[ci] + "22",
          pointRadius: 1.5, pointHoverRadius: 4,
          borderWidth: 2, tension: 0.2, fill: true,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, title: { display: true, text: label, font: { size: 12 } } },
        scales: {
          x: { title: { display: true, text: "Gen." }, ticks: { maxTicksLimit: 10 } },
          y: { min: 0, max, title: { display: true, text: "Valor" }, ticks: { stepSize: 1 } },
        },
      },
    });
  });
}

// ── TAB 3: Esquema de Restricción Óptimo ─────────────────────────────────────
function renderEsquema(anData, normalizedResult) {
  const wrap = document.getElementById("esquemaTable");
  if (!wrap) return;
  const colores = ["Verde", "Amarillo", "Rosa", "Rojo", "Azul"];
  const meses = normalizedResult?.mejor_solucion?.meses || [];

  let html = `<table class="esquema-table">
    <thead><tr>
      <th>Mes</th>
      <th>Contaminación</th>
      ${colores.map(c => `<th>
        <span style="color:${COLOR_MAP[c].hex}">●</span> ${c}<br/>
        <small style="font-weight:400">Pl. ${GRUPOS_PLACA[c].join(",")}</small>
      </th>`).join("")}
      <th>CO₂ Evitado</th>
    </tr></thead><tbody>`;

  meses.forEach((m, idx) => {
    const an = anData[idx] || {};
    const contColor = CONT_COLORS[m.contaminacion] || "#888";
    const contLabel = CONT_LABELS[m.contaminacion] || m.contaminacion;
    const yr = m.year; const mo = m.mes;
    const mesLabel = `${MONTH_NAMES[mo-1].slice(0,3)} ${yr}`;
    html += `<tr><td class="esquema-mes-cell">${mesLabel}</td>
      <td><span class="esquema-cont-badge" style="background:${contColor}">${contLabel}</span></td>`;

    colores.forEach(color => {
      const h2c = m?.h2?.por_color?.[color] || {};
      const hex = COLOR_MAP[color].hex;
      const dia = DIAS_TITULO[h2c.dia_base] || h2c.dia_base || "—";
      const sabs = h2c.sabados?.length ?? 0;
      const extras = h2c.fechas_restriccion?.length ?? 0;
      html += `<td style="color:#111;font-weight:600">
        ${dia}<br/><small style="font-weight:400;color:#555">${sabs} sáb.${extras ? ` +${extras}dx` : ""}</small>
      </td>`;
    });
    html += `<td class="co2-cell">${an.co2_evitado_ton != null ? Number(an.co2_evitado_ton).toLocaleString("es-MX",{maximumFractionDigits:0}) + " t" : "—"}</td></tr>`;
  });
  html += "</tbody></table>";
  wrap.innerHTML = html;
  injectDownloadBtn("tabEsquema", makeDownloadBtn("Descargar PNG", () => downloadDivAsImage("esquemaTable", "esquema_restriccion_optimo")));
}

// ── TAB 4: CO₂ / Costo-Beneficio ─────────────────────────────────────────────
function renderCo2Charts(anData) {
  const strip = document.getElementById("co2StatsStrip");

  // Totales del período
  const totalCo2Evit  = anData.reduce((s, m) => s + (m.co2_evitado_ton || 0), 0);
  const totalCo2Base  = anData.reduce((s, m) => s + (m.co2_base_ton || 0), 0);
  const avgAutos      = anData.reduce((s, m) => s + (m.autos_dia_millones || 0), 0) / (anData.length || 1);
  const totalCosto    = anData.reduce((s, m) => s + (m.costo_economico_millones || 0), 0);
  const avgImeca      = anData.reduce((s, m) => s + (m.imeca_promedio_real || m.nivel_imeca_efectivo || 0), 0) / (anData.length || 1);

  // CO2 real ahorrado (base − con restricción)
  const co2Ahorrado   = Math.max(0, totalCo2Base - totalCo2Evit);
  const reduccionPct  = totalCo2Base > 0 ? ((co2Ahorrado / totalCo2Base) * 100).toFixed(1) : "—";

  if (strip) {
    strip.innerHTML = `
      <div class="co2-stat">
        <span class="co2-stat-label">CO₂ Ahorrado</span>
        <span class="co2-stat-value">${co2Ahorrado.toLocaleString("es-MX",{maximumFractionDigits:0})}</span>
        <span class="co2-stat-unit">ton (vs. sin restricción)</span>
      </div>
      <div class="co2-stat">
        <span class="co2-stat-label">Reducción CO₂</span>
        <span class="co2-stat-value">${reduccionPct}%</span>
        <span class="co2-stat-unit">del total sin restricción</span>
      </div>
      <div class="co2-stat">
        <span class="co2-stat-label">Autos/día (prom.)</span>
        <span class="co2-stat-value">${avgAutos.toFixed(2)}M</span>
        <span class="co2-stat-unit">vehículos restringidos</span>
      </div>
      <div class="co2-stat">
        <span class="co2-stat-label">Costo económico</span>
        <span class="co2-stat-value">$${totalCosto.toLocaleString("es-MX",{maximumFractionDigits:0})}</span>
        <span class="co2-stat-unit">millones MXN (período)</span>
      </div>
      <div class="co2-stat">
        <span class="co2-stat-label">IMECA prom. real</span>
        <span class="co2-stat-value">${avgImeca.toFixed(0)}</span>
        <span class="co2-stat-unit">IAS_2024 SIMAT CDMX</span>
      </div>`;
  }

  const labels     = anData.map(m => `${MONTH_NAMES[(m.mes||1)-1].slice(0,3)} ${m.year}`);
  const co2EvitVals  = anData.map(m => m.co2_evitado_ton  || 0);
  const co2BaseVals  = anData.map(m => m.co2_base_ton     || 0);
  const co2AhorVals  = anData.map(m => Math.max(0, (m.co2_base_ton || 0) - (m.co2_evitado_ton || 0)));
  const autosVals    = anData.map(m => m.autos_dia_millones || 0);
  const costoVals    = anData.map(m => m.costo_economico_millones || 0);
  const imecaVals    = anData.map(m => m.imeca_promedio_real || m.nivel_imeca_efectivo || 0);

  injectDownloadBtn("tabCo2", makeDownloadBtn("Descargar PNG", () =>
    downloadMultiCanvas(["chartCo2","chartAutos"], "costo_beneficio_co2")));

  // Gráfica 1: Comparación CO₂ con restricción vs. sin restricción + CO₂ ahorrado
  makeChart("chartCo2", {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "CO₂ sin restricción (ton)",
          data: co2BaseVals,
          backgroundColor: "rgba(156,163,175,0.5)",
          borderColor: "#9ca3af", borderWidth: 1.5, borderRadius: 4,
          order: 2,
        },
        {
          label: "CO₂ con HNC (ton)",
          data: co2EvitVals,
          backgroundColor: "rgba(239,68,68,0.65)",
          borderColor: "#ef4444", borderWidth: 1.5, borderRadius: 4,
          order: 2,
        },
        {
          type: "line",
          label: "IMECA real (eje der.)",
          data: imecaVals,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245,158,11,0.12)",
          pointRadius: 5, pointHoverRadius: 7, borderWidth: 2,
          fill: false, tension: 0.35,
          yAxisID: "yImeca",
          order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: "top", labels: { font: { size: 11 } } },
        title: { display: true, text: "CO₂ Emitido: Con HNC vs. Sin Restricción + IMECA real", font: { size: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              if (ctx.dataset.label?.includes("IMECA")) return ` IMECA: ${ctx.raw.toFixed(0)} puntos`;
              return ` ${ctx.dataset.label}: ${Number(ctx.raw).toLocaleString("es-MX",{maximumFractionDigits:0})} ton`;
            },
          },
        },
      },
      scales: {
        y: {
          title: { display: true, text: "Toneladas CO₂" },
          beginAtZero: true,
          position: "left",
        },
        yImeca: {
          title: { display: true, text: "IMECA" },
          position: "right",
          grid: { drawOnChartArea: false },
          min: 0, max: 200,
        },
      },
    },
  });

  // Gráfica 2: Autos restringidos/día vs Costo económico (eje dual)
  makeChart("chartAutos", {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Autos restringidos/día (M)",
          data: autosVals,
          backgroundColor: "rgba(239,68,68,0.5)",
          borderColor: "#dc2626", borderWidth: 1.5, borderRadius: 4,
          yAxisID: "yAutos",
          order: 2,
        },
        {
          type: "line",
          label: "Costo económico (M MXN)",
          data: costoVals,
          borderColor: "#7c3aed",
          backgroundColor: "rgba(124,58,237,0.1)",
          pointRadius: 5, pointHoverRadius: 7, borderWidth: 2.5,
          fill: true, tension: 0.3,
          yAxisID: "yCosto",
          order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: "top", labels: { font: { size: 11 } } },
        title: { display: true, text: "Vehículos Restringidos/Día vs. Costo Económico Estimado", font: { size: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              if (ctx.dataset.label?.includes("Costo"))
                return ` Costo: $${Number(ctx.raw).toLocaleString("es-MX",{maximumFractionDigits:0})}M MXN`;
              return ` Autos: ${Number(ctx.raw).toFixed(2)}M`;
            },
          },
        },
      },
      scales: {
        yAutos: {
          title: { display: true, text: "Millones de autos/día" },
          beginAtZero: true, position: "left",
          ticks: { callback: v => v.toFixed(1) + "M" },
        },
        yCosto: {
          title: { display: true, text: "Costo (M MXN)" },
          beginAtZero: true, position: "right",
          grid: { drawOnChartArea: false },
          ticks: { callback: v => "$" + v.toLocaleString("es-MX",{maximumFractionDigits:0}) + "M" },
        },
      },
    },
  });
}

// ── TAB 5: Mejor Individuo ───────────────────────────────────────────────────
function renderIndividuo(mesData, normalizedResult) {
  const wrap = document.getElementById("individuoDetail");
  if (!wrap) return;
  const meses = normalizedResult?.mejor_solucion?.meses || [];
  const m = meses[analyticsState.activeMesIdx] || meses[0];
  if (!m) { wrap.innerHTML = "<em>Sin datos.</em>"; return; }

  const cont      = m.contaminacion || "—";
  const contLabel = CONT_LABELS[cont] || cont;
  const contColor = CONT_COLORS[cont] || "#888";
  const yr = m.year; const mo = m.mes;
  const COLORES   = ["Verde","Amarillo","Rosa","Rojo","Azul"];

  // ─── métricas de impacto ────────────────────────────────────────────────
  const co2     = mesData.co2_evitado_ton != null
                  ? Number(mesData.co2_evitado_ton).toLocaleString("es-MX",{maximumFractionDigits:0}) + " ton" : "—";
  const autosM  = mesData.autos_dia_millones != null
                  ? Number(mesData.autos_dia_millones).toFixed(2) + " M veh/día" : "—";
  const fitness = mesData.historial_mejor?.at(-1) != null
                  ? Number(mesData.historial_mejor.at(-1)).toFixed(3) : "—";

  // ─── tabla principal: una fila por color, columnas: H00 H0 H1 H2 ────────
  const tableRows = COLORES.map(color => {
    const hex   = COLOR_MAP[color].hex;
    const placas = (GRUPOS_PLACA[color] || []).join(", ");
    const h0c   = m?.h0?.por_color?.[color]  || {};
    const h1c   = m?.h1?.por_color?.[color]  || {};
    const h2c   = m?.h2?.por_color?.[color]  || {};
    const dia   = DIAS_TITULO[h2c.dia_base || h1c.dia_base] || "—";

    // H0
    const h0dias  = (h0c.fechas_restriccion || []).length;
    const h0str   = h0dias > 0
                    ? `${h0dias} día${h0dias>1?"s":""} L-V`
                    : `<span style="color:#888">Libre</span>`;

    // H1
    const h1sabs  = (h1c.sabados || []).length;
    const h1hora  = h1c.horario ? `${h1c.horario[0]}:00–${h1c.horario[1]}:00` : "05:00–22:00";
    const h1zona  = (h1c.zona||"total") === "centro" ? "Ctr." : "Tot.";
    const h1str   = h1sabs > 0
                    ? `${h1sabs} sáb. · ${h1hora} · ${h1zona}`
                    : `<span style="color:#888">—</span>`;

    // H2
    const h2sabs  = (h2c.sabados || []).length;
    const h2extra = (h2c.fechas_restriccion || []).length;
    const h2hora  = h2c.horario ? `${h2c.horario[0]}:00–${h2c.horario[1]}:00` : "05:00–22:00";
    const h2zona  = (h2c.zona||"total") === "centro" ? "Ctr." : "Tot.";
    const h2total = h2c.restriccion_total
                    ? `<strong style="color:#7a1414">Restricción Total</strong>`
                    : `${h2sabs} sáb.${h2extra>0?" + "+h2extra+" ext.":""} · ${h2hora} · ${h2zona}`;

    // intensidad = total días afectados (LV normales + sabs extra)
    const totalDias = 4 + h1sabs + h2sabs + h2extra + h0dias; // 4 = weekdays norm H1/H2
    const intLabel  = totalDias >= 14 ? "Fuerte" : totalDias >= 10 ? "Media" : totalDias >= 6 ? "Ligera" : "Mínima";
    const intColor  = {Fuerte:"#7a1414", Media:"#8b6215", Ligera:"#1a5c3a", Mínima:"#456070"}[intLabel];

    return `<tr>
      <td style="border-left:4px solid ${hex};padding-left:10px">
        <span style="background:${hex};color:#fff;border-radius:4px;padding:2px 8px;font-size:0.8rem;font-weight:700">${color}</span>
        <span style="display:block;font-size:0.75rem;color:#666;margin-top:2px">Pl. ${placas}</span>
      </td>
      <td style="font-weight:600;white-space:nowrap">${dia}</td>
      <td style="color:#888;font-size:0.8rem">Libre siempre</td>
      <td style="font-size:0.82rem">${h0str}</td>
      <td style="font-size:0.82rem">${h1str}</td>
      <td style="font-size:0.82rem">${h2total}</td>
      <td><span style="color:${intColor};font-weight:700;font-size:0.8rem">${intLabel}</span></td>
    </tr>`;
  }).join("");

  // ─── resumen de hologramas ────────────────────────────────────────────
  const verde     = { h0: m?.h0?.por_color?.Verde||{}, h1: m?.h1?.por_color?.Verde||{}, h2: m?.h2?.por_color?.Verde||{} };
  const tot_h0    = (verde.h0.fechas_restriccion||[]).length;
  const tot_h1s   = (verde.h1.sabados||[]).length;
  const tot_h2s   = (verde.h2.sabados||[]).length;
  const tot_h2ex  = (verde.h2.fechas_restriccion||[]).length;

  const HOLO_META = {
    H00: { label:"H00", badge:"#334155", detalle:"Libre — circulan todos los días sin restricción." },
    H0:  { label:"H0",  badge:"#334155", detalle: tot_h0>0 ? `${tot_h0} día${tot_h0>1?"s":""} L-V restringidos (contingencia)` : "Sin restricción este mes." },
    H1:  { label:"H1",  badge:"#334155", detalle:`L-V base + ${tot_h1s} sábado${tot_h1s!==1?"s":""} restringido${tot_h1s!==1?"s":""}` },
    H2:  { label:"H2",  badge:"#334155", detalle: verde.h2.restriccion_total ? "Restricción total (contingencia extrema)" : `L-V base + ${tot_h2s} sáb.${tot_h2ex>0?" + "+tot_h2ex+" días extra":""}` },
  };
  const holoRows = Object.entries(HOLO_META).map(([k,v]) => `
    <div style="display:flex;align-items:flex-start;gap:10px;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;flex:1;min-width:200px">
      <span style="background:#1a1a2e;color:#fff;border-radius:5px;padding:3px 10px;font-size:0.82rem;font-weight:800;white-space:nowrap;flex-shrink:0">${v.label}</span>
      <div>
        <div style="font-size:0.8rem;color:#64748b;margin-bottom:2px">${{H00:"Verificación 0-0",H0:"Holograma 0",H1:"Holograma 1",H2:"Holograma 2"}[k]}</div>
        <div style="font-size:0.85rem;font-weight:600;color:#1a2a35">${v.detalle}</div>
      </div>
    </div>`).join("");

  // ─── métricas impacto strip ───────────────────────────────────────────
  const impacto = [
    ["CO₂ evitado", co2],
    ["Veh. detenidos/día", autosM],
    ["Fitness final", fitness],
    ["Calidad del aire", `<span style="background:${contColor};color:#fff;border-radius:999px;padding:1px 9px;font-size:0.8rem">${contLabel}</span>`],
  ];
  const impactoStrip = impacto.map(([lbl, val]) => `
    <div style="flex:1;min-width:110px;border:1px solid #e2e8f0;border-radius:8px;padding:9px 12px;text-align:center;background:#fff">
      <span style="display:block;font-size:0.68rem;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;margin-bottom:4px">${lbl}</span>
      <span style="display:block;font-size:0.95rem;font-weight:700;color:#1a2a35">${val}</span>
    </div>`).join("");

  injectDownloadBtn("tabIndividuo", makeDownloadBtn("Descargar PNG", () => downloadDivAsImage("individuoDetail", "mejor_individuo")));

  wrap.innerHTML = `
  <div style="font-family:inherit;width:100%">

    <!-- Encabezado -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid #e2e8f0;flex-wrap:wrap">
      <div style="min-width:0">
        <div style="font-size:1.1rem;font-weight:800;color:#1a2a35;white-space:nowrap">Mejor Solución — ${MONTH_NAMES[mo-1]} ${yr}</div>
        <div style="font-size:0.8rem;color:#64748b;margin-top:2px">Programa Hoy No Circula optimizado para este mes</div>
      </div>
    </div>

    <!-- Layout 2 columnas: hologramas + tabla -->
    <div style="display:grid;grid-template-columns:1fr 2fr;gap:16px;margin-bottom:16px;align-items:start">

      <!-- Columna izq: resumen hologramas -->
      <div>
        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;margin-bottom:8px">Resumen por Holograma</div>
        <div style="display:flex;flex-direction:column;gap:8px">${holoRows}</div>
        <!-- Métricas impacto debajo -->
        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;margin:14px 0 8px">Impacto Estimado</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">${impactoStrip}</div>
      </div>

      <!-- Columna der: tabla por color -->
      <div style="overflow-x:auto">
        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;margin-bottom:8px">Asignación por Grupo de Color</div>
        <table style="width:100%;border-collapse:collapse;font-size:0.81rem">
          <thead>
            <tr style="background:#1a1a2e;color:#fff;text-align:left">
              <th style="padding:8px 10px;font-weight:600">Grupo</th>
              <th style="padding:8px 10px;font-weight:600">Día base</th>
              <th style="padding:8px 10px;font-weight:600">H00</th>
              <th style="padding:8px 10px;font-weight:600">H0</th>
              <th style="padding:8px 10px;font-weight:600">H1</th>
              <th style="padding:8px 10px;font-weight:600">H2</th>
              <th style="padding:8px 10px;font-weight:600">Intens.</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
        <p style="font-size:0.7rem;color:#94a3b8;margin-top:6px;line-height:1.5">
          Todos los grupos H1/H2 circulan en su día L-V asignado y se restringen en sábados seleccionados.
          H0 solo se restringe en contingencia ambiental. "Ctr." = Zona Centro · "Tot." = toda la ZMVM.
        </p>
      </div>

    </div>
  </div>`;
}


// ═══════════════════════════════════════════════════════════════════════════════
// DESCARGA DE GRÁFICAS
// ═══════════════════════════════════════════════════════════════════════════════

function downloadCanvas(canvasId, filename) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const link = document.createElement("a");
  link.download = filename + ".png";
  link.href = canvas.toDataURL("image/png", 1.0);
  link.click();
}

function downloadMultiCanvas(canvasIds, filename) {
  const canvases = canvasIds.map(id => document.getElementById(id)).filter(Boolean);
  if (!canvases.length) return;
  const cols = 3;
  const rows = Math.ceil(canvases.length / cols);
  const cw = canvases[0].width; const ch = canvases[0].height;
  const merged = document.createElement("canvas");
  merged.width = cw * cols; merged.height = ch * rows;
  const ctx = merged.getContext("2d");
  ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, merged.width, merged.height);
  canvases.forEach((c, i) => {
    const col = i % cols; const row = Math.floor(i / cols);
    ctx.drawImage(c, col * cw, row * ch);
  });
  const link = document.createElement("a");
  link.download = filename + ".png";
  link.href = merged.toDataURL("image/png", 1.0);
  link.click();
}

function downloadDivAsImage(divId, filename) {
  const div = document.getElementById(divId);
  if (!div) return;
  if (typeof html2canvas !== "undefined") {
    html2canvas(div, { backgroundColor: "#ffffff", scale: 2 }).then(canvas => {
      const link = document.createElement("a");
      link.download = filename + ".png";
      link.href = canvas.toDataURL("image/png");
      link.click();
    });
  } else {
    alert("Instala html2canvas para descarga directa. Por ahora usa Ctrl+P para imprimir esta sección.");
  }
}

function makeDownloadBtn(label, onClickFn) {
  const btn = document.createElement("button");
  btn.className = "ghost small-btn dl-btn";
  btn.textContent = label;
  btn.style.cssText = "font-size:0.78rem;padding:4px 10px;border-radius:6px;cursor:pointer;white-space:nowrap;flex-shrink:0;margin-left:auto";
  btn.addEventListener("click", onClickFn);
  return btn;
}

function injectDownloadBtn(panelId, btn) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  const header = panel.querySelector(".chart-header");
  if (!header) return;
  panel.querySelector(".dl-btn")?.remove();
  header.style.display = "flex";
  header.style.alignItems = "flex-start";
  header.style.justifyContent = "space-between";
  header.style.gap = "8px";
  header.appendChild(btn);
}

// ═══════════════════════════════════════════════════════════════════════════════
// IAS Panel
// ═══════════════════════════════════════════════════════════════════════════════

const IMECA_COLOR = imeca => {
  if (imeca <= 50)  return "#16a34a";
  if (imeca <= 100) return "#eab308";
  if (imeca <= 150) return "#f97316";
  if (imeca <= 200) return "#dc2626";
  return "#7c3aed";
};

const IMECA_LABEL = imeca => {
  if (imeca <= 50)  return "Buena";
  if (imeca <= 100) return "Aceptable";
  if (imeca <= 150) return "Mala";
  if (imeca <= 200) return "Muy Mala";
  return "Extrema";
};

function renderIasPreview(ajustesMensuales) {
  if (!els.iasPreview) return;
  const meses = Object.entries(ajustesMensuales).sort(([a], [b]) => +a - +b);
  const rows = meses.map(([key, d]) => {
    const imeca = d.imeca_promedio_real ?? "—";
    const factor = d.factor_contaminacion ?? "—";
    const nombre = d.nombre_mes || MONTH_NAMES[(+key) - 1] || key;
    const color = typeof imeca === "number" ? IMECA_COLOR(imeca) : "#9ca3af";
    const label = typeof imeca === "number" ? IMECA_LABEL(imeca) : "—";
    const barW = typeof imeca === "number" ? Math.min(60, (imeca / 200) * 60) : 0;
    return `<tr>
      <td style="font-weight:600">${nombre}</td>
      <td>
        <span style="color:${color};font-weight:700">${typeof imeca==="number" ? imeca.toFixed(1) : "—"}</span>
        <span class="ias-imeca-bar" style="width:${barW}px;background:${color}"></span>
      </td>
      <td><span class="ias-badge" style="background:${color}22;color:${color}">${label}</span></td>
      <td style="font-family:monospace">${typeof factor==="number" ? factor.toFixed(3)+"x" : "—"}</td>
    </tr>`;
  }).join("");
  els.iasPreview.innerHTML = `
    <table class="ias-table">
      <thead><tr>
        <th>Mes</th><th>IMECA promedio</th><th>Condición</th><th>Factor</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  els.iasPreview.classList.remove("hidden");
}

function setIasStatus(type, msg) {
  if (!els.iasStatus) return;
  els.iasStatus.className = `ias-status ${type}`;
  els.iasStatus.textContent = msg;
  els.iasStatus.classList.remove("hidden");
}

function initIasPanel() {
  els.fileIas?.addEventListener("change", e => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (els.iasFileName) els.iasFileName.textContent = file.name;
    if (els.btnImportarIas) els.btnImportarIas.disabled = false;
    els.iasStatus?.classList.add("hidden");
    els.iasPreview?.classList.add("hidden");
    if (els.iasBadge) {
      els.iasBadge.textContent = "Archivo listo";
      els.iasBadge.className = "ias-badge";
    }
  });

  els.btnImportarIas?.addEventListener("click", async () => {
    const file = els.fileIas?.files?.[0];
    if (!file) return;

    els.btnImportarIas.disabled = true;
    setIasStatus("loading", "⏳ Procesando CSV… esto puede tomar unos segundos.");
    if (els.iasBadge) { els.iasBadge.textContent = "Procesando…"; els.iasBadge.className = "ias-badge"; }

    const fd = new FormData();
    fd.append("ias_csv", file);

    try {
      const resp = await fetch("/api/etl-ias", { method: "POST", body: fd });
      const data = await resp.json();

      if (!resp.ok || data.error) throw new Error(data.error || `HTTP ${resp.status}`);

      const ajustes = data.ajustes_mensuales || {};
      const nMeses  = Object.keys(ajustes).length;
      const filas   = data.filas_procesadas ?? "?";
      setIasStatus("ok",
        `✅ ${typeof filas === "number" ? filas.toLocaleString() : filas} filas procesadas · ${nMeses} meses cargados · ` +
        (data.mensaje || "entorno actualizado")
      );
      if (els.iasBadge) { els.iasBadge.textContent = "Datos reales cargados"; els.iasBadge.className = "ias-badge loaded"; }
      renderIasPreview(ajustes);
      // Actualizar también el ETL file list
      if (_etlArchivosBackend.ias) {
        _etlArchivosBackend.ias.existe = true;
        etlState.ias = { ok: true, msg: "Importado vía panel IAS" };
        renderEtlFileList(_etlArchivosBackend);
      }
      setTimeout(verifyBackend, 800);

    } catch (err) {
      setIasStatus("err", `❌ Error: ${err.message}`);
      if (els.iasBadge) { els.iasBadge.textContent = "Error al importar"; els.iasBadge.className = "ias-badge error"; }
    } finally {
      els.btnImportarIas.disabled = false;
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// INIT & EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════════════════════

function init() {
  initializeDOM();

  // Default values
  applyConfigToUI(FALLBACK_DEFAULTS);

  // Mode tabs
  [els.tabDemo, els.tabAdvanced].forEach(tab => {
    if (!tab) return;
    tab.addEventListener("click", () => {
      [els.tabDemo, els.tabAdvanced].forEach(t => t?.classList.remove("active"));
      tab.classList.add("active");
      const isDemo = tab.dataset.mode === "demo";
      els.panelDemo?.classList.toggle("hidden", !isDemo);
      els.panelAdvanced?.classList.toggle("hidden", isDemo);
    });
  });

  // IMECA slider
  if (els.imecaSlider) {
    els.imecaSlider.addEventListener("input", () => syncClimateControls("imeca"));
  }
  if (els.pesoAmbiental) {
    els.pesoAmbiental.addEventListener("input", () => syncClimateControls("weight"));
  }

  // Panel ETL dinámico — carga estado de archivos desde el backend
  cargarEstadoArchivos();

  // IAS file input (panel separado)
  initIasPanel();

  // Reset defaults
  els.btnResetDefaults?.addEventListener("click", () => applyConfigToUI(state.defaults || FALLBACK_DEFAULTS));

  // Calendar filters
  [els.vehHolograma, els.vehDigito].forEach(el => {
    el?.addEventListener("change", () => { renderCalendarGrid(); renderDayDetail(); });
  });

  // Nav buttons
  document.getElementById("btnPrevMonth")?.addEventListener("click", () => {
    if (state.monthIndex > 0) selectMonth(state.monthIndex - 1);
  });
  document.getElementById("btnNextMonth")?.addEventListener("click", () => {
    if (state.monthIndex < state.monthKeys.length - 1) selectMonth(state.monthIndex + 1);
  });

  // Run / Stop
  els.btnRun?.addEventListener("click", runOptimization);
  els.btnStop?.addEventListener("click", () => {
    state.stopRequested = true;
    state.runController?.abort();
  });

  // Export
  els.btnExport?.addEventListener("click", () => {
    if (!state.result) return;
    const blob = new Blob([JSON.stringify(state.result, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `hnc_dictamen_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
  });

  // Verify backend on load
  verifyBackend();
}

document.addEventListener("DOMContentLoaded", init);
