const state = {
  files: { eodSemana: null, eodSabado: null, vmrc: null, verificacion: null, contaminantes: null },
  running: false, stopRequested: false, result: null, runController: null,
  monthKeys: [], monthIndex: 0, selectedDate: null,
  defaults: null,
};

const FALLBACK_DEFAULTS = {
  params: {
    pop_size: 100,
    generaciones: 120,
    mutacion: 0.05,
    elitismo: 2,
    peso_equidad: 1,
    peso_ambiental_critico: 2.2,
    peso_economico: 1.55,
    nivel_imeca: 150,
    start_month: "2026-04",
    meses: 6,
  },
  ui: {
    imeca: 151,
    veh_holograma: "H1",
    veh_digito: "all",
    view_mode: "no-circula",
  },
};

const DAYS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"];
const DIGIT_COLOR = {
  0:"#2563eb", 9:"#2563eb", // Azul
  1:"#16a34a", 2:"#16a34a", // Verde
  3:"#dc2626", 4:"#dc2626", // Rojo
  5:"#eab308", 6:"#eab308", // Amarillo
  7:"#ec4899", 8:"#ec4899", // Rosa
};
const MONTH_NAMES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

const els = {
  // Tab mode
  tabDemo: document.getElementById("tabDemo"),
  tabAdvanced: document.getElementById("tabAdvanced"),
  panelDemo: document.getElementById("panelDemo"),
  panelAdvanced: document.getElementById("panelAdvanced"),
  demoStatusIcon: document.getElementById("demoStatusIcon"),
  demoStatusText: document.getElementById("demoStatusText"),
  demoVehicleSummary: document.getElementById("demoVehicleSummary"),
  btnVerificar: document.getElementById("btnVerificar"),
  
  // Files
  fileEodSemana: document.getElementById("fileEodSemana"),
  fileEodSabado: document.getElementById("fileEodSabado"),
  fileVmrc: document.getElementById("fileVmrc"),
  fileVerificacion: document.getElementById("fileVerificacion"),
  fileContaminantes: document.getElementById("fileContaminantes"),
  
  // Config
  startMonth: document.getElementById("startMonth"),
  horizonteMeses: document.getElementById("horizonteMeses"),
  envSummary: document.getElementById("envSummary"),
  imecaSlider: document.getElementById("imecaSlider"),
  imecaBadge: document.getElementById("imecaBadge"),
  popSize: document.getElementById("popSize"),
  generaciones: document.getElementById("generaciones"),
  mutacion: document.getElementById("mutacion"),
  elitismo: document.getElementById("elitismo"),
  pesoEquidad: document.getElementById("pesoEquidad"),
  pesoAmbiental: document.getElementById("pesoAmbiental"),
  pesoEconomico: document.getElementById("pesoEconomico"),
  btnResetDefaults: document.getElementById("btnResetDefaults"),
  
  // Execution
  btnRun: document.getElementById("btnRun"),
  btnStop: document.getElementById("btnStop"),
  generationLabel: document.getElementById("generationLabel"),
  fitnessLabel: document.getElementById("fitnessLabel"),
  progressFill: document.getElementById("progressFill"),
  logBox: document.getElementById("logBox"),
  globalStatus: document.getElementById("globalStatus"),
  btnExport: document.getElementById("btnExport"),
  
  // Stats
  statsStrip: document.getElementById("statsStrip"),
  statZona: document.getElementById("statZona"),
  statFitness: document.getElementById("statFitness"),
  statH1: document.getElementById("statH1"),
  statH2: document.getElementById("statH2"),
  statH00: document.getElementById("statH00"),
  
  // Hybrid summary
  hybridSummary: document.getElementById("hybridSummary"),
  
  // Calendar
  vehHolograma: document.getElementById("vehHolograma"),
  vehDigito: document.getElementById("vehDigito"),
  viewMode: document.getElementById("viewMode"),
  calendarPanel: document.getElementById("calendarPanel"),
  calendarTitle: document.getElementById("calendarTitle"),
  calendarGrid: document.getElementById("calendarGrid"),
  dayDetail: document.getElementById("dayDetail"),
  monthTabsWrap: document.getElementById("monthTabsWrap"),
  btnPrevMonth: document.getElementById("btnPrevMonth"),
  btnNextMonth: document.getElementById("btnNextMonth"),
  resultsContainer: document.getElementById("resultsContainer"),
};

console.log("✓ Elementos del DOM identificados");

// ── UTILS ─────────────────────────────────────────────────────────────────────
function log(msg) {
  const ts = new Date().toLocaleTimeString();
  if (els.logBox) {
    els.logBox.textContent += `[${ts}] ${msg}\n`;
    els.logBox.scrollTop = els.logBox.scrollHeight;
  }
}
function updateStatus(t) { 
  if (els.globalStatus) els.globalStatus.textContent = t; 
}
function readFileAsText(file) {
  return new Promise((res, rej) => {
    const reader = new FileReader();
    reader.onload = () => res(reader.result);
    reader.onerror = rej;
    reader.readAsText(file);
  });
}

// ── IMECA ─────────────────────────────────────────────────────────────────────
function imecaToWeight(v) {
  v = Number(v);
  if (v <= 50)  return 0.8;
  if (v <= 100) return 1.2;
  if (v <= 150) return 1.8;
  if (v <= 200) return 2.5;
  if (v <= 300) return 3.5;
  return Math.min(5.0, 4.0 + (v - 300) / 100 * 0.5);
}

function imecaClassify(v) {
  v = Number(v);
  if (v <= 50)  return { label:"Buena",                 color:"#0284c7" };
  if (v <= 100) return { label:"Aceptable",             color:"#0d9488" };
  if (v <= 150) return { label:"Regular",               color:"#ca8a04" };
  if (v <= 200) return { label:"Mala",                  color:"#ea580c" };
  if (v <= 300) return { label:"Muy Mala",              color:"#dc2626" };
  return        { label:"Extremadamente Mala",         color:"#7c3aed" };
}

function syncImecaSlider() {
  if (!els.imecaSlider || !els.imecaBadge || !els.pesoAmbiental) return;
  const val = els.imecaSlider.value;
  const cls = imecaClassify(val);
  els.imecaBadge.textContent = `${cls.label} — ${val}`;
  els.imecaBadge.style.background = cls.color;
  els.pesoAmbiental.value = imecaToWeight(val).toFixed(2);
}

function updateImecaBadgeOnly(value) {
  if (!els.imecaSlider || !els.imecaBadge) return;
  const cls = imecaClassify(value);
  els.imecaBadge.textContent = `${cls.label} — ${value}`;
  els.imecaBadge.style.background = cls.color;
}

function applyDefaultFormValues(defaults) {
  const params = defaults?.params || FALLBACK_DEFAULTS.params;
  const ui = defaults?.ui || FALLBACK_DEFAULTS.ui;

  if (els.popSize) els.popSize.value = params.pop_size;
  if (els.generaciones) els.generaciones.value = params.generaciones;
  if (els.mutacion) els.mutacion.value = params.mutacion;
  if (els.elitismo) els.elitismo.value = params.elitismo;
  if (els.pesoEquidad) els.pesoEquidad.value = params.peso_equidad;
  if (els.pesoAmbiental) els.pesoAmbiental.value = params.peso_ambiental_critico;
  if (els.pesoEconomico) els.pesoEconomico.value = params.peso_economico;
  if (els.startMonth) els.startMonth.value = params.start_month;
  if (els.horizonteMeses) els.horizonteMeses.value = params.meses;

  if (els.imecaSlider) els.imecaSlider.value = ui.imeca;
  updateImecaBadgeOnly(ui.imeca);
  if (els.pesoAmbiental) els.pesoAmbiental.value = params.peso_ambiental_critico;

  if (els.vehHolograma) els.vehHolograma.value = ui.veh_holograma || "H1";
  if (els.vehDigito) els.vehDigito.value = ui.veh_digito || "all";
  if (els.viewMode) els.viewMode.value = ui.view_mode || "no-circula";
}

async function cargarConfiguracionInicial() {
  try {
    const res = await fetch("/api/config-inicial");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.defaults = data.defaults || FALLBACK_DEFAULTS;
    applyDefaultFormValues(state.defaults);
  } catch (e) {
    state.defaults = FALLBACK_DEFAULTS;
    applyDefaultFormValues(state.defaults);
    log(`Usando valores por defecto locales: ${e.message}`);
  }
}

// ── DEMO MODE ─────────────────────────────────────────────────────────────────
async function verificarEntorno() {
  if (!els.demoStatusIcon || !els.demoStatusText) return;
  els.demoStatusIcon.textContent = "...";
  els.demoStatusText.textContent = "Conectando con el backend...";
  if (els.demoVehicleSummary) els.demoVehicleSummary.classList.add("hidden");
  try {
    const res = await fetch("/api/config-inicial");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.status === "ok") {
      els.demoStatusIcon.textContent = "✓";
      els.demoStatusText.textContent = "Backend activo. Sistema listo.";
    } else {
      els.demoStatusIcon.textContent = "⚠";
      els.demoStatusText.textContent = "Backend: " + (data.message || "estado incierto");
    }
  } catch (e) {
    els.demoStatusIcon.textContent = "✗";
    els.demoStatusText.textContent = `Error: ${e.message}`;
  }
}

function bindModeTabs() {
  if (!els.tabDemo || !els.tabAdvanced) return;
  [els.tabDemo, els.tabAdvanced].forEach(tab => {
    tab.addEventListener("click", (e) => {
      document.querySelectorAll(".mode-tab").forEach(t => t.classList.remove("active"));
      e.target.classList.add("active");
      if (els.panelDemo) els.panelDemo.classList.toggle("hidden");
      if (els.panelAdvanced) els.panelAdvanced.classList.toggle("hidden");
    });
  });
  if (els.btnVerificar) {
    els.btnVerificar.addEventListener("click", verificarEntorno);
  }
  setTimeout(verificarEntorno, 600);
}

// ── FILES ─────────────────────────────────────────────────────────────────────
function bindFiles() {
  const inputs = [
    [els.fileEodSemana, "eodSemana"],
    [els.fileEodSabado, "eodSabado"],
    [els.fileVmrc, "vmrc"],
    [els.fileVerificacion, "verificacion"],
    [els.fileContaminantes, "contaminantes"]
  ];
  inputs.forEach(([input, key]) => {
    if (input) {
      input.addEventListener("change", (e) => {
        state.files[key] = e.target.files[0];
        refreshEnvSummary();
      });
    }
  });
}

function refreshEnvSummary() {
  if (!els.envSummary) return;
  const labels = {
    eodSemana: "EOD semana",
    eodSabado: "EOD sábado",
    vmrc: "VMRC",
    verificacion: "Verificación",
    contaminantes: "Contaminantes",
  };
  const loaded = Object.entries(state.files).filter(([,v]) => v).map(([k,v]) => `${labels[k] || k}: ${v.name}`);
  const missing = getMissingEtlSources();
  if (loaded.length) {
    const missingTxt = missing.length ? ` | Faltan: ${missing.join(", ")}` : " | Todas las fuentes cargadas";
    els.envSummary.textContent = `Fuentes ETL cargadas (${loaded.length}/5): ${loaded.join(" | ")}${missingTxt}`;
  } else {
    els.envSummary.textContent = `Sin fuentes ETL cargadas. Faltan: ${missing.join(", ")}`;
  }
}

function getMissingEtlSources() {
  const labels = {
    eodSemana: "EOD semana",
    eodSabado: "EOD sábado",
    vmrc: "VMRC",
    verificacion: "Verificación",
    contaminantes: "Contaminantes",
  };
  return Object.entries(state.files)
    .filter(([, value]) => !value)
    .map(([key]) => labels[key] || key);
}

// ── PARAMS ────────────────────────────────────────────────────────────────────
function getParams() {
  return {
    pop_size: Number(els.popSize?.value || 100),
    generaciones: Number(els.generaciones?.value || 120),
    mutacion: Number(els.mutacion?.value || 0.05),
    elitismo: Number(els.elitismo?.value || 2),
    peso_equidad: Number(els.pesoEquidad?.value || 1.0),
    peso_ambiental_critico: Number(els.pesoAmbiental?.value || 2.2),
    peso_economico: Number(els.pesoEconomico?.value || 1.55),
    nivel_imeca: Number(els.imecaSlider?.value || 150),
    start_month: els.startMonth?.value || "2026-04",
    meses: Number(els.horizonteMeses?.value || 6),
  };
}

// ── STATS STRIP ───────────────────────────────────────────────────────────────
function renderStatsStrip(result) {
  if (!result) return;
  const fitness = result.mejor_fitness || 0;
  if (els.statZona) els.statZona.textContent = "CDMX Total";
  if (els.statFitness) els.statFitness.textContent = fitness.toFixed(4);
  if (els.statH1) els.statH1.textContent = "100%";
  if (els.statH2) els.statH2.textContent = "100%";
  if (els.statH00) els.statH00.textContent = "Libre";
  if (els.statsStrip) els.statsStrip.classList.remove("hidden");
}

// ── HYBRID SUMMARY ────────────────────────────────────────────────────────────
function renderHybridSummary(result) {
  if (!result || !els.hybridSummary) {
    if (els.hybridSummary) els.hybridSummary.classList.add("hidden");
    return;
  }
  const p = result.parametros || {};
  const html = `<h4>Configuración del AG Evolutivo</h4>
    <div class="hybrid-metrics">
      <span class="metric-chip">Población: ${p.pop_size || 100}</span>
      <span class="metric-chip">Generaciones: ${p.generaciones || 120}</span>
      <span class="metric-chip">Mutación: ${(p.mutacion || 0.05).toFixed(3)}</span>
      <span class="metric-chip">Peso ambiental: ${(p.peso_ambiental_critico || 2.2).toFixed(2)}</span>
    </div>`;
  els.hybridSummary.innerHTML = html;
  els.hybridSummary.classList.remove("hidden");
}

// ── DIGIT OPTIONS ─────────────────────────────────────────────────────────────
function fillDigitOptions() {
  if (!els.vehDigito) return;
  els.vehDigito.innerHTML = "";
  const all = document.createElement("option");
  all.value = "all"; 
  all.textContent = "Todos";
  els.vehDigito.appendChild(all);
  for (let d = 0; d <= 9; d++) {
    const opt = document.createElement("option");
    opt.value = String(d); 
    opt.textContent = String(d);
    els.vehDigito.appendChild(opt);
  }
}

function getSaturdayNumber(dt) {
  let count = 0;
  for (let day = 1; day <= dt.getDate(); day++) {
    const current = new Date(dt.getFullYear(), dt.getMonth(), day);
    if (current.getDay() === 6) count += 1;
  }
  return count;
}

function getRestrictedDigitsForDay(monthData, holograma, dt) {
  const dayName = DAYS[dt.getDay() === 0 ? 6 : dt.getDay() - 1];
  const isoDate = dt.toISOString().split("T")[0];
  const castigos = monthData?.castigos_hologramas?.[holograma] || {};
  const colores = castigos.colores || {};
  const saturdayNumber = getSaturdayNumber(dt);
  const restrictedDigits = [];

  for (const info of Object.values(colores)) {
    const diaNormal = info?.dia_normal;
    const diasExtra = Array.isArray(info?.dias_extra) ? info.dias_extra : [];
    const fechasExtra = Array.isArray(info?.fechas_extra) ? info.fechas_extra : [];
    const sabadosCastigados = Number(info?.total_sabados_castigados || 0);
    const placas = Array.isArray(info?.placas) ? info.placas : [];

    const isSaturdayRestricted = dt.getDay() === 6 && saturdayNumber <= sabadosCastigados;
    const isExactExtraRestricted = fechasExtra.includes(isoDate);
    const hasExactExtras = fechasExtra.length > 0;
    const isWeekdayExtraFallback = !hasExactExtras && diasExtra.includes(dayName);
    const isWeekdayRestricted = dayName === diaNormal || isExactExtraRestricted || isWeekdayExtraFallback;

    if (isSaturdayRestricted || isWeekdayRestricted) {
      restrictedDigits.push(...placas.map(Number).filter(v => !Number.isNaN(v)));
    }
  }

  return [...new Set(restrictedDigits)].sort((a, b) => a - b);
}

function normalizeResultForUI(result) {
  if (!result) return null;

  const meses = result?.mejor_solucion?.meses;
  if (!Array.isArray(meses)) {
    return result?.calendario_meses ? result : null;
  }

  const grupos = {
    Amarillo: [5, 6],
    Rosa: [7, 8],
    Rojo: [3, 4],
    Verde: [1, 2],
    Azul: [9, 0],
  };

  const calendario = {};
  for (const mesData of meses) {
    const key = `${mesData.year}-${String(mesData.mes).padStart(2, "0")}`;
    const castigosH1 = {};
    const castigosH2 = {};

    for (const [color, cfg] of Object.entries(mesData?.h1?.por_color || {})) {
      const dia = (cfg.dia_base || "").toLowerCase();
      const diaNormal = dia === "miercoles" ? "Miércoles" : `${dia.slice(0, 1).toUpperCase()}${dia.slice(1)}`;
      castigosH1[color] = {
        placas: grupos[color] || [],
        dia_normal: diaNormal,
        dias_extra: [],
        total_sabados_castigados: Array.isArray(cfg.sabados) ? cfg.sabados.length : 0,
      };
    }

    for (const [color, cfg] of Object.entries(mesData?.h2?.por_color || {})) {
      const dia = (cfg.dia_base || "").toLowerCase();
      const diaNormal = dia === "miercoles" ? "Miércoles" : `${dia.slice(0, 1).toUpperCase()}${dia.slice(1)}`;
      const diasExtra = (cfg.extras || []).map(iso => {
        const dt = new Date(`${iso}T00:00:00`);
        const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1;
        return DAYS[idx];
      });
      castigosH2[color] = {
        placas: grupos[color] || [],
        dia_normal: diaNormal,
        dias_extra: diasExtra,
        fechas_extra: Array.isArray(cfg.extras) ? cfg.extras : [],
        total_sabados_castigados: Array.isArray(cfg.sabados) ? cfg.sabados.length : 0,
      };
    }

    const h1Verde = mesData?.h1?.por_color?.Verde || { horario: [5, 22], zona: "total" };
    const h2Verde = mesData?.h2?.por_color?.Verde || { horario: [5, 22], zona: "total" };
    const estado = mesData.contaminacion || "normal";

    calendario[key] = {
      estado_contaminacion: `${estado.slice(0, 1).toUpperCase()}${estado.slice(1)}`,
      castigos_hologramas: {
        H00: { regla: "Ninguno. Circulan libremente." },
        H0: { regla: "Ninguno. Circulan libremente." },
        H1: {
          horario: `${String(h1Verde.horario?.[0] ?? 5).padStart(2, "0")}:00 a ${String(h1Verde.horario?.[1] ?? 22).padStart(2, "0")}:00`,
          zona: `${(h1Verde.zona || "total").slice(0, 1).toUpperCase()}${(h1Verde.zona || "total").slice(1)}`,
          colores: castigosH1,
        },
        H2: {
          horario: `${String(h2Verde.horario?.[0] ?? 5).padStart(2, "0")}:00 a ${String(h2Verde.horario?.[1] ?? 22).padStart(2, "0")}:00`,
          zona: `${(h2Verde.zona || "total").slice(0, 1).toUpperCase()}${(h2Verde.zona || "total").slice(1)}`,
          colores: castigosH2,
        },
      },
    };
  }

  return { ...result, calendario_meses: calendario };
}

// ── MONTH TABS ────────────────────────────────────────────────────────────────
function renderMonthTabs() {
  if (!els.monthTabsWrap || !state.monthKeys.length) return;
  els.monthTabsWrap.innerHTML = "";
  state.monthKeys.forEach((key, idx) => {
    const btn = document.createElement("button");
    btn.className = `month-tab-btn ${idx === state.monthIndex ? "active" : ""}`;
    btn.textContent = key;
    btn.addEventListener("click", () => {
      state.monthIndex = idx;
      renderMonthTabs();
      renderCalendarMonth();
    });
    els.monthTabsWrap.appendChild(btn);
  });
}

// ── CALENDAR ──────────────────────────────────────────────────────────────────
function renderCalendarMonth() {
  if (!state.result || !state.monthKeys.length || !els.calendarGrid) {
    if (els.calendarPanel) els.calendarPanel.classList.add("hidden");
    return;
  }
  
  const monthKey = state.monthKeys[state.monthIndex];
  const monthData = state.result.calendario_meses?.[monthKey];
  if (!monthData) return;

  const [year, month] = monthKey.split("-").map(Number);
  
  if (els.calendarTitle) {
    els.calendarTitle.textContent = `${MONTH_NAMES[month - 1]} ${year}`;
  }

  els.calendarGrid.innerHTML = "";
  
  // Headers
  const headers = ["L", "M", "M", "J", "V", "S", "D"];
  headers.forEach(h => {
    const div = document.createElement("div");
    div.className = "weekday";
    div.textContent = h;
    els.calendarGrid.appendChild(div);
  });

  // Días anteriores
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();

  for (let i = 0; i < (firstDay === 0 ? 6 : firstDay - 1); i++) {
    const div = document.createElement("div");
    div.className = "day-cell outside";
    els.calendarGrid.appendChild(div);
  }

  // Días del mes
  const holograma = els.vehHolograma?.value || "H1";
  const selectedDigitRaw = els.vehDigito?.value || "all";
  const viewMode = els.viewMode?.value || "no-circula";
  
  for (let d = 1; d <= daysInMonth; d++) {
    const cell = document.createElement("div");
    cell.className = "day-cell allowed";
    const dt = new Date(year, month - 1, d);
    const restrictedDigits = getRestrictedDigitsForDay(monthData, holograma, dt);
    const selectedDigit = selectedDigitRaw === "all" ? null : Number(selectedDigitRaw);
    const matchesSelection = selectedDigit == null
      ? restrictedDigits.length > 0
      : restrictedDigits.includes(selectedDigit);
    const isRestricted = matchesSelection;

    if (viewMode === "no-circula") {
      cell.className = isRestricted ? "day-cell blocked" : "day-cell allowed";
    } else {
      cell.className = "day-cell allowed";
    }

    const visibleDots = selectedDigit == null
      ? restrictedDigits
      : (restrictedDigits.includes(selectedDigit) ? [selectedDigit] : []);

    const dotsHtml = visibleDots
      .map(digit => `<span class="day-dot" title="Dígito ${digit}" style="background:${DIGIT_COLOR[digit] || "#64748b"};"></span>`)
      .join("");

    cell.innerHTML = `
      <span class="day-number">${d}</span>
      <span class="day-dot-wrap">${dotsHtml}</span>
    `;
    
    cell.addEventListener("click", () => {
      state.selectedDate = new Date(year, month - 1, d).toISOString().split("T")[0];
      renderDayDetail();
    });
    
    els.calendarGrid.appendChild(cell);
  }

  if (els.calendarPanel) els.calendarPanel.classList.remove("hidden");
}

// ── DAY DETAIL ────────────────────────────────────────────────────────────────
function renderDayDetail() {
  if (!state.selectedDate || !els.dayDetail) {
    if (els.dayDetail) els.dayDetail.textContent = "Selecciona un día para ver el detalle.";
    return;
  }

  const dt = new Date(state.selectedDate);
  const dayName = DAYS[dt.getDay() === 0 ? 6 : dt.getDay() - 1];
  const year = dt.getFullYear();
  const month = dt.getMonth() + 1;
  const monthKey = `${year}-${String(month).padStart(2, "0")}`;
  
  const monthData = state.result?.calendario_meses?.[monthKey];
  if (!monthData) {
    els.dayDetail.innerHTML = "<strong>Sin información para esta fecha.</strong>";
    return;
  }

  const holograma = els.vehHolograma?.value || "H1";
  const castigos = monthData.castigos_hologramas?.[holograma] || {};
  const horario = castigos.horario || "Libre";
  const zona = castigos.zona || "Total";

  let html = `<strong>${dayName}, ${dt.getDate()} de ${MONTH_NAMES[month - 1]}</strong><br/>`;
  html += `<span class="detail-label">Holograma ${holograma}:</span> ${horario} | Zona: ${zona}<br/>`;

  const colores = castigos.colores || {};
  if (Object.keys(colores).length > 0) {
    html += `<strong>Restricciones por color:</strong><br/>`;
    for (const [color, info] of Object.entries(colores)) {
      const placas = info.placas?.join(",") || "—";
      const iNormal = info.dia_normal === dayName ? " ✓" : "";
      const fechasExtra = Array.isArray(info.fechas_extra) ? info.fechas_extra : [];
      const extrasTxt = fechasExtra.length ? ` | extras: ${fechasExtra.join(", ")}` : "";
      html += `  <span class="bloque-tag">${color} (placas ${placas})${iNormal}${extrasTxt}</span>`;
    }
  } else {
    html += `<span style="color: var(--muted);">Sin restricciones específicas.</span>`;
  }

  els.dayDetail.innerHTML = html;
}

// ── RESULTS ───────────────────────────────────────────────────────────────────
function renderResults(result) {
  const normalized = normalizeResultForUI(result);
  if (!normalized || !normalized.calendario_meses) {
    if (els.resultsContainer) els.resultsContainer.innerHTML = '<div class="results-empty">Ejecuta el modelo para ver el calendario óptimo.</div>';
    return;
  }

  state.result = normalized;
  state.monthKeys = Object.keys(normalized.calendario_meses).sort();
  state.monthIndex = 0;

  renderStatsStrip(normalized);
  renderHybridSummary(normalized);
  renderMonthTabs();
  renderCalendarMonth();

  if (els.resultsContainer) els.resultsContainer.innerHTML = "";
  if (els.btnExport) els.btnExport.disabled = false;
}

// ── EXPORT ────────────────────────────────────────────────────────────────────
function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── RUN ───────────────────────────────────────────────────────────────────────
async function runSimulation() {
  if (state.running) return;
  state.running = true;
  state.stopRequested = false;

  if (els.btnRun) els.btnRun.disabled = true;
  if (els.btnStop) els.btnStop.disabled = false;
  if (els.logBox) els.logBox.textContent = "";
  updateStatus("Ejecutando AG...");

  try {
    const missingFiles = getMissingEtlSources();
    if (missingFiles.length) {
      const message = `Faltan fuentes ETL: ${missingFiles.join(", ")}`;
      log(`✗ ${message}`);
      updateStatus("Faltan fuentes ETL");
      throw new Error(message);
    }

    const params = getParams();
    log("Iniciando optimización...");
    log(`Parámetros: Pop=${params.pop_size}, Gen=${params.generaciones}, IMECA=${params.nivel_imeca}`);

    const formData = new FormData();
    formData.append("params", JSON.stringify(params));
    if (state.files.eodSemana) {
      const name = state.files.eodSemana.name.toLowerCase();
      if (name.endsWith(".csv")) {
        formData.append("eodEntreSemanaCsv", state.files.eodSemana);
      } else {
        formData.append("eodEntreSemanaXlsx", state.files.eodSemana);
      }
    }
    if (state.files.eodSabado) formData.append("eodSabado", state.files.eodSabado);
    if (state.files.vmrc) formData.append("vmrc", state.files.vmrc);
    if (state.files.verificacion) formData.append("verificacion", state.files.verificacion);
    if (state.files.contaminantes) formData.append("contaminantes", state.files.contaminantes);

    const response = await fetch("/api/run", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    const result = await response.json();
    log("✓ Optimización completada");
    log(`Mejor fitness: ${(result.mejor_fitness || 0).toFixed(6)}`);
    let finalStatus = "Listo";
    if (result.etl_regenerado) {
      const fuentes = Array.isArray(result.fuentes_etl) && result.fuentes_etl.length
        ? ` (${result.fuentes_etl.join(", ")})`
        : "";
      log(`✓ ETL regenerado con archivos subidos${fuentes}`);
      finalStatus = "ETL regenerado y AG ejecutado";
    }

    renderResults(result);
    updateStatus(finalStatus);
  } catch (e) {
    log(`✗ Error: ${e.message}`);
    updateStatus("Error");
  } finally {
    state.running = false;
    if (els.btnRun) els.btnRun.disabled = false;
    if (els.btnStop) els.btnStop.disabled = true;
  }
}

// ── AUTO-CARGA ÚLTIMO RESULTADO ───────────────────────────────────────────────
async function cargarUltimoResultado() {
  try {
    const res = await fetch("/api/ultimo-resultado");
    if (!res.ok) return;
    const result = await res.json();
    if (result) {
      log("Resultado anterior cargado automáticamente");
      renderResults(result);
    }
  } catch (e) {
    // Silencioso
  }
}

// ── BIND ALL ──────────────────────────────────────────────────────────────────
function bindActions() {
  if (els.btnRun) els.btnRun.addEventListener("click", runSimulation);
  if (els.btnResetDefaults) {
    els.btnResetDefaults.addEventListener("click", () => {
      applyDefaultFormValues(state.defaults || FALLBACK_DEFAULTS);
      log("Valores por defecto restaurados");
    });
  }
  if (els.btnStop) {
    els.btnStop.addEventListener("click", () => {
      state.stopRequested = true;
      els.btnStop.disabled = true;
    });
  }
  if (els.btnExport) {
    els.btnExport.addEventListener("click", () => {
      if (state.result) {
        downloadJson("resultado_ag_hnc.json", state.result);
        log("Resultado exportado como JSON");
      }
    });
  }
  
  if (els.btnPrevMonth) {
    els.btnPrevMonth.addEventListener("click", () => {
      if (state.monthIndex > 0) {
        state.monthIndex--;
        renderMonthTabs();
        renderCalendarMonth();
      }
    });
  }
  if (els.btnNextMonth) {
    els.btnNextMonth.addEventListener("click", () => {
      if (state.monthIndex < state.monthKeys.length - 1) {
        state.monthIndex++;
        renderMonthTabs();
        renderCalendarMonth();
      }
    });
  }
}

// ── INIT ──────────────────────────────────────────────────────────────────────
bindFiles();
fillDigitOptions();
bindActions();
bindModeTabs();
refreshEnvSummary();
loadInitialUI();

console.log("🟢 Inicializando UI...");
async function loadInitialUI() {
  await cargarConfiguracionInicial();
  if (els.imecaSlider) els.imecaSlider.addEventListener("input", syncImecaSlider);
  if (els.vehHolograma) els.vehHolograma.addEventListener("change", renderCalendarMonth);
  if (els.vehDigito) els.vehDigito.addEventListener("change", renderCalendarMonth);
  if (els.viewMode) els.viewMode.addEventListener("change", renderCalendarMonth);
  setTimeout(() => {
    cargarUltimoResultado();
  }, 500);
}
