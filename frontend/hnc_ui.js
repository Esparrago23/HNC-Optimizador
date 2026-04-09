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
      const colorZona = info.zona || "—";
      html += `  <span class="bloque-tag">${color} (placas ${placas})${iNormal} | ${colorHorario} | ${colorZona}${extrasTxt}</span>`;
    }
  } else {
    html += `<span style="color: var(--muted);">Sin restricciones específicas.</span>`;
  }
  els.dayDetail.innerHTML = html;
}

function loadFiles() {
  const files = {
    eodSemana: els.fileEodSemana?.files?.[0],
    eodSabado: els.fileEodSabado?.files?.[0],
    vmrc: els.fileVmrc?.files?.[0],
    verificacion: els.fileVerificacion?.files?.[0],
    contaminantes: els.fileContaminantes?.files?.[0],
  };
  for (const [key, file] of Object.entries(files)) {
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          state.files[key] = JSON.parse(e.target.result);
        } catch (err) {
          console.error(`Error parsing ${key}:`, err);
        }
      };
      reader.readAsText(file);
    }
  }
}

function updateEnvSummary() {
  if (!els.envSummary) return;
  const imeca = els.imecaSlider?.value || 150;
  const nivel = imecaClassify(imeca).label;
  els.envSummary.textContent = `IMECA: ${imeca} (${nivel})`;
  updateImecaBadgeOnly(imeca);
}

function gatherRunParams() {
  return {
    pop_size: parseInt(els.popSize?.value || 100),
    generaciones: parseInt(els.generaciones?.value || 120),
    mutacion: parseFloat(els.mutacion?.value || 0.05),
    elitismo: parseInt(els.elitismo?.value || 2),
    peso_equidad: parseFloat(els.pesoEquidad?.value || 1),
    peso_ambiental_critico: parseFloat(els.pesoAmbiental?.value || 2.2),
    peso_economico: parseFloat(els.pesoEconomico?.value || 1.55),
    nivel_imeca: parseInt(els.imecaSlider?.value || 150),
    start_month: els.startMonth?.value || "2026-04",
    meses: parseInt(els.horizonteMeses?.value || 6),
  };
}

async function runAlgorithm() {
  if (state.running) return;
  loadFiles();
  state.running = true;
  state.stopRequested = false;
  setRunningUi(true, "Optimizando...");
  const params = gatherRunParams();
  const formData = new FormData();
  formData.append("params", JSON.stringify(params));
  if (els.fileEodSemana?.files?.[0]) formData.append("eodEntreSemanaCsv", els.fileEodSemana.files[0]);
  if (els.fileEodSabado?.files?.[0]) formData.append("eodSabado", els.fileEodSabado.files[0]);
  if (els.fileVmrc?.files?.[0]) formData.append("vmrc", els.fileVmrc.files[0]);
  if (els.fileVerificacion?.files?.[0]) formData.append("verificacion", els.fileVerificacion.files[0]);
  if (els.fileContaminantes?.files?.[0]) formData.append("contaminantes", els.fileContaminantes.files[0]);
  state.runController = new AbortController();
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      body: formData,
      signal: state.runController.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!state.stopRequested) {
      state.result = normalizeResultForUI(data);
      if (els.logBox) {
        els.logBox.innerHTML += "<p>Optimización terminada.</p>";
      }
      renderMonthTabs();
      renderCalendarGrid();
      renderDayDetail();
      updateStats();
      setResultsVisible(true);
      if (els.globalStatus) {
        els.globalStatus.textContent = `Optimización completada. Meses generados: ${state.result?.calendario_meses ? Object.keys(state.result.calendario_meses).length : 0}`;
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      console.error("Run error:", err);
      if (els.logBox) els.logBox.innerHTML += `<p style="color:red;">Error: ${err.message}</p>`;
      if (els.globalStatus) {
        els.globalStatus.textContent = `Error en la optimización: ${err.message}`;
      }
    }
  }
  state.running = false;
  setRunningUi(false, state.stopRequested ? "Optimización detenida" : "Listo");
  if (!state.stopRequested && !state.result) {
    await fetchLastResult();
  }
}

function updateProgressFromSSE(data) {
  if (data.generacion !== undefined) {
    if (els.generationLabel) els.generationLabel.textContent = `Gen: ${data.generacion}`;
    if (els.progressFill && data.generaciones_totales) {
      const pct = (data.generacion / data.generaciones_totales) * 100;
      els.progressFill.style.width = `${pct}%`;
    }
  }
  if (data.fitness !== undefined && els.fitnessLabel) {
    els.fitnessLabel.textContent = `Fitness: ${data.fitness.toFixed(4)}`;
  }
  if (data.status) {
    if (els.logBox) {
      const p = document.createElement("p");
      p.textContent = data.status;
      els.logBox.appendChild(p);
      els.logBox.scrollTop = els.logBox.scrollHeight;
    }
  }
}

async function stopAlgorithm() {
  state.stopRequested = true;
  if (state.runController) {
    state.runController.abort();
  }
}

async function fetchLastResult() {
  try {
    const resp = await fetch("/api/ultimo-resultado");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    state.result = normalizeResultForUI(data);
    if (state.result) {
      setResultsVisible(true);
    }
    renderMonthTabs();
    renderCalendarGrid();
    renderDayDetail();
    updateStats();
    if (els.globalStatus) {
      els.globalStatus.textContent = "Resultado cargado.";
    }
  } catch (err) {
    console.error("Fetch result error:", err);
    if (els.globalStatus) {
      els.globalStatus.textContent = `Error: ${err.message}`;
    }
  }
}

function updateStats() {
  if (!state.result?.calendario_meses) return;
  let countH00 = 0, countH1 = 0, countH2 = 0;
  for (const monthData of Object.values(state.result.calendario_meses)) {
    const h00Cols = monthData?.castigos_hologramas?.H00?.colores || {};
    const h1Cols = monthData?.castigos_hologramas?.H1?.colores || {};
    const h2Cols = monthData?.castigos_hologramas?.H2?.colores || {};
    for (const info of Object.values(h00Cols)) {
      countH00 += Array.isArray(info.fechas_restriccion) ? info.fechas_restriccion.length : 0;
    }
    for (const info of Object.values(h1Cols)) {
      countH1 += info.total_sabados_castigados || 0;
    }
    for (const info of Object.values(h2Cols)) {
      countH2 += info.total_sabados_castigados || 0;
    }
  }
  if (els.statZona) els.statZona.textContent = `Zona: Total`;
  if (els.statFitness) els.statFitness.textContent = `Fitness: ${Number(state.result?.mejor_fitness || 0).toFixed(4)}`;
  if (els.statH1) els.statH1.textContent = `H1 Sáb: ${countH1}`;
  if (els.statH2) els.statH2.textContent = `H2 Sáb: ${countH2}`;
  if (els.statH00) els.statH00.textContent = countH00 > 0 ? `H00 Fechas: ${countH00}` : "H00: Libre";
  if (els.fitnessLabel) els.fitnessLabel.textContent = `Mejor fitness: ${Number(state.result?.mejor_fitness || 0).toFixed(4)}`;
}

function resetDefaults() {
  applyConfigToUI(state.defaults || FALLBACK_DEFAULTS);
}

function exportResult() {
  if (!state.result) {
    alert("No hay resultado para exportar.");
    return;
  }
  const json = JSON.stringify(state.result, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `hnc-resultado-${new Date().toISOString().split("T")[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function setupEventListeners() {
  if (els.btnRun) els.btnRun.addEventListener("click", runAlgorithm);
  if (els.btnStop) els.btnStop.addEventListener("click", stopAlgorithm);
  if (els.btnResetDefaults) els.btnResetDefaults.addEventListener("click", resetDefaults);
  if (els.btnExport) els.btnExport.addEventListener("click", exportResult);
  if (els.imecaSlider) els.imecaSlider.addEventListener("input", () => syncClimateControls("imeca"));
  if (els.pesoAmbiental) els.pesoAmbiental.addEventListener("input", () => syncClimateControls("weight"));
  if (els.vehHolograma) els.vehHolograma.addEventListener("change", () => {
    renderCalendarGrid();
    renderDayDetail();
  });
  if (els.vehDigito) els.vehDigito.addEventListener("change", () => {
    renderCalendarGrid();
    renderDayDetail();
  });
}

async function loadInitialConfig() {
  try {
    const resp = await fetch("/api/config-inicial");
    if (resp.ok) {
      const data = await resp.json();
      applyConfigToUI(data);
    } else {
      applyConfigToUI(FALLBACK_DEFAULTS);
    }
  } catch (err) {
    console.error("Error loading config:", err);
    applyConfigToUI(FALLBACK_DEFAULTS);
  }
}

async function init() {
  initializeDOM();
  setupEventListeners();
  setResultsVisible(false);
  await loadInitialConfig();
  await fetchLastResult();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
