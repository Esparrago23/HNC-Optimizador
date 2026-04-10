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
  ui: { imeca: 151, veh_holograma: "H1", veh_digito: "all", view_mode: "no-circula" },
};

const DAYS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"];
const DIGIT_COLOR = {
  0:"#2563eb", 9:"#2563eb", 1:"#16a34a", 2:"#16a34a", 3:"#dc2626", 4:"#dc2626",
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
  els.demoStatusIcon = document.getElementById("demoStatusIcon") || document.createElement("div");
  els.demoStatusText = document.getElementById("demoStatusText") || document.createElement("div");
  els.demoVehicleSummary = document.getElementById("demoVehicleSummary") || document.createElement("div");
  els.btnVerificar = document.getElementById("btnVerificar") || document.createElement("button");
  els.fileEodSemana = document.getElementById("fileEodSemana") || document.createElement("input");
  els.fileEodSabado = document.getElementById("fileEodSabado") || document.createElement("input");
  els.fileVmrc = document.getElementById("fileVmrc") || document.createElement("input");
  els.fileVerificacion = document.getElementById("fileVerificacion") || document.createElement("input");
  els.fileContaminantes = document.getElementById("fileContaminantes") || document.createElement("input");
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
  els.statH1 = document.getElementById("statH1") || document.createElement("div");
  els.statH2 = document.getElementById("statH2") || document.createElement("div");
  els.statH00 = document.getElementById("statH00") || document.createElement("div");
  els.hybridSummary = document.getElementById("hybridSummary") || document.createElement("div");
  els.vehHolograma = document.getElementById("vehHolograma") || document.createElement("select");
  els.vehDigito = document.getElementById("vehDigito") || document.createElement("select");
  els.viewMode = document.getElementById("viewMode") || document.createElement("select");
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
  if (els.viewMode) {
    els.viewMode.value = normalized.ui.view_mode;
  }
  syncClimateControls("imeca");
  updateEnvSummary();
}

function imecaClassify(value) {
  const imeca = Number(value);
  if (imeca <= 50) return { label: "Buena", color: "#16a34a" };
  if (imeca <= 100) return { label: "Aceptable", color: "#eab308" };
  if (imeca <= 150) return { label: "Mala", color: "#f97316" };
  if (imeca <= 200) return { label: "Muy Mala", color: "#dc2626" };
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
      castigosH1[color] = {
        placas: grupos[color] || [], dia_normal: diaNormal, dias_extra: [],
        sabados: Array.isArray(cfg.sabados) ? cfg.sabados : [],
        total_sabados_castigados: Array.isArray(cfg.sabados) ? cfg.sabados.length : 0,
        horario: horario,
        zona: zona,
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
      castigosH2[color] = {
        placas: grupos[color] || [], dia_normal: diaNormal,
        dias_extra: diasExtra, fechas_extra: Array.isArray(cfg.extras) ? cfg.extras : [],
        fechas_restriccion: Array.isArray(cfg.fechas_restriccion) ? cfg.fechas_restriccion : [],
        sabados: Array.isArray(cfg.sabados) ? cfg.sabados : [],
        restriccion_total: Boolean(cfg.restriccion_total),
        total_sabados_castigados: Array.isArray(cfg.sabados) ? cfg.sabados.length : 0,
        horario: horario,
        zona: zona,
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
    if (isDateOnlyHologram ? isDateBasedRestricted : (isNormalDay || isSaturdayRestricted || isExtraDay || isDateBasedRestricted)) {
      matchedColors.push({ color, info });
      if (isDateOnlyHologram ? isDateBasedRestricted : (isNormalDay || isSaturdayRestricted || isDateBasedRestricted)) {
        dayHorario = info.horario || castigos.horario || "Libre";
        dayZona = info.zona || castigos.zona || "Total";
      }
    }
  }
  let html = `<strong>${dayName}, ${dt.getDate()} de ${MONTH_NAMES[month-1]}</strong><br/>`;
  html += `<span class="detail-label">Holograma ${holograma}:</span> ${dayHorario} | Zona: ${dayZona}<br/>`;
  if (matchedColors.length > 0) {
    html += `<strong>Restricciones por color:</strong><br/>`;
    for (const { color, info } of matchedColors) {
      const placas = info.placas?.join(",") || "—";
      const iNormal = (!isDateOnlyHologram && info.dia_normal === dayName) ? " ✓" : "";
      const fechasExtra = Array.isArray(info.fechas_extra) ? info.fechas_extra : [];
      const fechasRestr = Array.isArray(info.fechas_restriccion) ? info.fechas_restriccion : [];
      const extrasTxt = fechasRestr.length
        ? ` | fechas: ${fechasRestr.join(", ")}`
        : (fechasExtra.length ? ` | extras: ${fechasExtra.join(", ")}` : "");
      const colorHorario = info.horario || "—";
      const colorZona = `${(info.zona||"total").slice(0,1).toUpperCase()}${(info.zona||"total").slice(1)}`;
      html += `<div class="detail-row">
        <span class="detail-label">${color}${iNormal}</span>
        <span class="detail-val">Placas: ${placas} | ${colorHorario} | ${colorZona}${extrasTxt}</span>
      </div>`;
    }
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
function renderStatsStrip(result) {
  if (!result) return;
  const meses = result?.mejor_solucion?.meses || [];
  if (!meses.length) return;
  const m0 = meses[0];
  const h1Verde = m0?.h1?.por_color?.Verde || {};
  const h2Verde = m0?.h2?.por_color?.Verde || {};
  const h0Verde = m0?.h0?.por_color?.Verde || {};
  if (els.statZona) els.statZona.textContent = `${(h2Verde.zona || "total").slice(0,1).toUpperCase()}${(h2Verde.zona||"total").slice(1)}`;
  if (els.statFitness) els.statFitness.textContent = typeof result.mejor_fitness === "number" ? result.mejor_fitness.toFixed(1) : "—";
  if (els.statH1) {
    const sabs = h1Verde.sabados?.length ?? 0;
    els.statH1.textContent = `${h1Verde.dia_base || "—"} | ${sabs} sáb.`;
  }
  if (els.statH2) {
    const sabs = h2Verde.sabados?.length ?? 0;
    const extras = h2Verde.fechas_restriccion?.length ?? 0;
    els.statH2.textContent = `${h2Verde.dia_base || "—"} | ${sabs} sáb.${extras ? ` +${extras}dx` : ""}`;
  }
  if (els.statH00) {
    const restr = h0Verde.fechas_restriccion?.length ?? 0;
    els.statH00.textContent = restr > 0 ? `${restr} días contingencia` : "Libre";
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

function updateEnvSummary() {
  if (!els.envSummary) return;
  const files = state.files;
  const loaded = Object.entries(files).filter(([,v]) => v).map(([k]) => k);
  els.envSummary.textContent = loaded.length
    ? `Fuentes cargadas: ${loaded.join(", ")}.`
    : "Sin fuentes ETL cargadas.";
}

async function verifyBackend() {
  if (!els.demoStatusIcon || !els.demoStatusText) return;
  const data = await fetchJSON("/api/config-inicial");
  if (data?.status === "ok") {
    els.demoStatusIcon.textContent = "✅";
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
    els.demoStatusIcon.textContent = "❌";
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
  if (state.files.eodSemana)     fd.append("eodEntreSemanaXlsx", state.files.eodSemana);
  if (state.files.eodSabado)     fd.append("eodSabado",           state.files.eodSabado);
  if (state.files.vmrc)          fd.append("vmrc",                 state.files.vmrc);
  if (state.files.verificacion)  fd.append("verificacion",         state.files.verificacion);
  if (state.files.contaminantes) fd.append("contaminantes",        state.files.contaminantes);
  return fd;
}

async function runOptimization() {
  if (state.running) return;
  state.running = true;
  state.stopRequested = false;
  state.runController = new AbortController();
  setRunningUi(true, "Optimizando...");
  if (els.logBox) els.logBox.innerHTML = "<p>🚀 Iniciando optimización...</p><p>⏳ El AG puede tardar varios minutos según el número de generaciones.</p>";
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
    setRunningUi(false, "✅ Optimización completada");
    if (els.generationLabel) els.generationLabel.textContent = `Generación: ${generaciones} / ${generaciones}`;
    if (els.fitnessLabel && data.mejor_fitness != null) {
      els.fitnessLabel.textContent = `Mejor fitness: ${Number(data.mejor_fitness).toFixed(2)}`;
    }
    logLine("✅ Resultado recibido y renderizado.");
  } catch (e) {
    if (e.name === "AbortError") {
      logLine("⏹ Optimización detenida por el usuario.");
      setRunningUi(false, "Detenido");
    } else {
      logLine(`❌ Error: ${e.message}`);
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
      html += `<td>
        <span class="color-chip" style="background:${hex}18;border-color:${hex};color:${hex}">
          ${dia}<br/><small style="font-weight:400">${sabs} sáb.${extras ? ` +${extras}dx` : ""}</small>
        </span></td>`;
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
  const totalCo2 = anData.reduce((s, m) => s + (m.co2_evitado_ton || 0), 0);
  const avgAutos = anData.reduce((s, m) => s + (m.autos_dia_millones || 0), 0) / (anData.length || 1);
  if (strip) {
    strip.innerHTML = `
      <div class="co2-stat"><span class="co2-stat-label">CO₂ Total 6 meses</span><span class="co2-stat-value">${totalCo2.toLocaleString("es-MX",{maximumFractionDigits:0})}</span><span class="co2-stat-unit">toneladas</span></div>
      <div class="co2-stat"><span class="co2-stat-label">Autos/día promedio</span><span class="co2-stat-value">${avgAutos.toFixed(2)}M</span><span class="co2-stat-unit">vehículos detenidos</span></div>
      <div class="co2-stat"><span class="co2-stat-label">CO₂ / mes (prom.)</span><span class="co2-stat-value">${(totalCo2/anData.length).toLocaleString("es-MX",{maximumFractionDigits:0})}</span><span class="co2-stat-unit">ton / mes</span></div>
      <div class="co2-stat"><span class="co2-stat-label">Efectividad estimada</span><span class="co2-stat-value">60%</span><span class="co2-stat-unit">conductores que omiten circular</span></div>`;
  }

  const labels = anData.map(m => `${MONTH_NAMES[(m.mes||1)-1].slice(0,3)}\n${m.year}`);
  const co2Vals = anData.map(m => m.co2_evitado_ton || 0);
  const autosVals = anData.map(m => m.autos_dia_millones || 0);

  injectDownloadBtn("tabCo2", makeDownloadBtn("Descargar PNG", () =>
    downloadMultiCanvas(["chartCo2","chartAutos"], "costo_beneficio_co2")));
  makeChart("chartCo2", {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "CO₂ evitado (ton)",
        data: co2Vals,
        backgroundColor: "rgba(22,163,74,0.75)",
        borderColor: "#16a34a", borderWidth: 1.5, borderRadius: 4,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: "CO₂ Evitado por Mes (toneladas)", font: { size: 12 } },
      },
      scales: { y: { title: { display: true, text: "Toneladas CO₂" }, beginAtZero: true } },
    },
  });

  makeChart("chartAutos", {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Autos detenidos/día (M)",
        data: autosVals,
        borderColor: "#dc2626", backgroundColor: "rgba(220,38,38,0.1)",
        pointRadius: 5, pointHoverRadius: 7, borderWidth: 2.5,
        fill: true, tension: 0.3,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: "Autos Detenidos/Día (millones)", font: { size: 12 } },
      },
      scales: {
        y: {
          title: { display: true, text: "Millones de autos" },
          ticks: { callback: v => v.toFixed(2) + "M" },
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

  const cont = m.contaminacion || "—";
  const contLabel = CONT_LABELS[cont] || cont;
  const contColor = CONT_COLORS[cont] || "#888";
  const yr = m.year; const mo = m.mes;
  const h2verde = m?.h2?.por_color?.Verde || {};
  const h1verde = m?.h1?.por_color?.Verde || {};
  const h0verde = m?.h0?.por_color?.Verde || {};
  const sabs_h2 = h2verde.sabados?.length ?? "—";
  const sabs_h1 = h1verde.sabados?.length ?? "—";
  const dias_h0 = h0verde.fechas_restriccion?.length ?? 0;
  const extras_h2 = h2verde.fechas_restriccion?.length ?? 0;
  const fitness = mesData.variables_optimas ? (mesData.variables_optimas.sabados_h2 != null ? "Disponible" : "—") : "—";

  const kvRows = [
    ["Mes", `${MONTH_NAMES[mo-1]} ${yr}`],
    ["Contaminación", `<span style="background:${contColor};color:#fff;border-radius:999px;padding:1px 8px;font-size:0.78rem">${contLabel}</span>`],
    ["Horario restricción", "05:00 – 22:00 hrs"],
    ["Zona de aplicación", `${((m?.h2?.por_color?.Verde?.zona || "total").slice(0,1).toUpperCase())}${(m?.h2?.por_color?.Verde?.zona || "total").slice(1)}`],
    ["H2 sábados restringidos", `${sabs_h2} sábados`],
    ["H1 sábados restringidos", `${sabs_h1} sábados`],
    ["H2 días extra por grupo", `${extras_h2} días`],
    ["Días contingencia H0", `${dias_h0} días`],
    ["CO₂ evitado (mes)", `${mesData.co2_evitado_ton != null ? Number(mesData.co2_evitado_ton).toLocaleString("es-MX",{maximumFractionDigits:0}) + " ton" : "—"}`],
    ["Autos detenidos/día", `${mesData.autos_dia_millones != null ? Number(mesData.autos_dia_millones).toFixed(2) + "M" : "—"}`],
  ];

  const colores = ["Verde","Amarillo","Rosa","Rojo","Azul"];
  const colorRows = colores.map(color => {
    const hex = COLOR_MAP[color].hex;
    const h2c = m?.h2?.por_color?.[color] || {};
    const dia = DIAS_TITULO[h2c.dia_base] || h2c.dia_base || "—";
    const sabs = h2c.sabados?.length ?? 0;
    const extras = h2c.fechas_restriccion || [];
    const placas = GRUPOS_PLACA[color] || [];
    return `<div class="color-row" style="background:${hex}10;border-color:${hex}55">
      <span class="color-row-name" style="color:${hex}">${color}</span>
      <span class="color-row-placas">Pl. ${placas.join(",")}</span>
      <span class="color-row-dia">${dia}</span>
      <span class="color-row-details">${sabs} sáb. H2</span>
      ${extras.length ? `<span class="color-row-extras">+${extras.length} días extra: ${extras.join(", ")}</span>` : ""}
    </div>`;
  }).join("");

  injectDownloadBtn("tabIndividuo", makeDownloadBtn("Descargar PNG", () => downloadDivAsImage("individuoDetail", "mejor_individuo")));
  wrap.innerHTML = `
    <div class="individuo-info">
      <div class="individuo-info-title">📊 Parámetros del Mejor Individuo</div>
      <div class="individuo-kv">
        ${kvRows.map(([k,v]) => `<div class="kv-row"><span class="kv-label">${k}</span><span class="kv-value">${v}</span></div>`).join("")}
      </div>
    </div>
    <div class="individuo-colors">
      <div class="colors-title">🎨 Asignación por Grupo de Color — H2</div>
      ${colorRows}
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
  // Merge multiple canvases into one wide image and download
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
  // Uses html2canvas if available, otherwise falls back to plain PNG
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
    // Fallback: open print dialog for the section
    alert("Instala html2canvas para descarga directa. Por ahora usa Ctrl+P para imprimir esta sección.");
  }
}

function makeDownloadBtn(label, onClickFn) {
  const btn = document.createElement("button");
  btn.className = "ghost small-btn dl-btn";
  btn.innerHTML = "⬇ " + label;
  btn.style.cssText = "font-size:0.78rem;padding:4px 10px;border-radius:6px;cursor:pointer;white-space:nowrap;flex-shrink:0;margin-left:auto";
  btn.addEventListener("click", onClickFn);
  return btn;
}

function injectDownloadBtn(panelId, btn) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  const header = panel.querySelector(".chart-header");
  if (!header) return;
  // Remove existing download btn
  panel.querySelector(".dl-btn")?.remove();
  header.style.display = "flex";
  header.style.alignItems = "flex-start";
  header.style.justifyContent = "space-between";
  header.style.gap = "8px";
  header.appendChild(btn);
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

  // File inputs
  const fileMap = {
    fileEodSemana: "eodSemana", fileEodSabado: "eodSabado",
    fileVmrc: "vmrc", fileVerificacion: "verificacion", fileContaminantes: "contaminantes",
  };
  Object.entries(fileMap).forEach(([elKey, stateKey]) => {
    els[elKey]?.addEventListener("change", e => {
      state.files[stateKey] = e.target.files?.[0] || null;
      updateEnvSummary();
    });
  });

  // Reset defaults
  els.btnResetDefaults?.addEventListener("click", () => applyConfigToUI(state.defaults || FALLBACK_DEFAULTS));

  // Calendar filters
  [els.vehHolograma, els.vehDigito, els.viewMode].forEach(el => {
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
