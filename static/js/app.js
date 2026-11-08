(() => {
  "use strict";

  const state = { cases: [], profile: {}, regimes: [], charts: {}, activeCase: null, importBatch: null, importRows: [], caseStep: 1 };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const money = value => value == null || Number.isNaN(Number(value)) ? "—" : new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN", maximumFractionDigits: 0 }).format(Number(value));
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const regimeColors = Object.freeze({ NRUS: "#A9CFE8", RER: "#F2D28B", RMT: "#A9D6C1", RG: "#E3B8CE" });
  const regimeName = code => ({ NRUS: "Nuevo RUS", RER: "Régimen Especial", RMT: "Régimen MYPE Tributario", RG: "Régimen General" }[code] || code || "Pendiente");
  const regimeColor = code => regimeColors[code] || "#777777";
  const compactCell = value => {
    const text = String(value ?? "");
    return `<span class="compare-cell-summary" title="${escapeHtml(text)}">${escapeHtml(text)}</span>`;
  };
  let toastTimer;

  async function api(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(payload?.error || `Error al consultar el servidor (${response.status}).`);
    return payload;
  }

  function notify(message, error = false) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.toggle("error", error);
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 3600);
  }

  function navigate(view) {
    if (!$(`#view-${view}`)) return;
    $$(".view").forEach(section => {
      const active = section.id === `view-${view}`;
      section.classList.toggle("active", active);
      section.hidden = !active;
    });
    $$(".nav-link").forEach(button => button.classList.toggle("active", button.dataset.view === view));
    $("#page-crumb").textContent = ({ dashboard: "Dashboard", cases: "Registro y análisis", regimes: "Regímenes tributarios", guide: "Guía tributaria", profile: "Perfil y créditos" })[view];
    $("#sidebar").classList.remove("open");
    if (view === "dashboard") renderDashboard();
    if (view === "regimes") {
      populateAnalysisPicker();
      renderRegimeCards();
    }
    if (view === "cases") renderCases();
  }

  async function refresh() {
    const data = await api("/api/bootstrap");
    state.cases = data.cases;
    state.profile = data.profile;
    state.regimes = data.regimes;
    $("#welcome-title").textContent = `¡Hola${state.profile.full_name ? `, ${state.profile.full_name.split(/\s+/)[0]}` : ""}!`;
    const initials = state.profile.full_name ? state.profile.full_name.split(/\s+/).slice(0, 2).map(name => name[0]).join("").toUpperCase() : "TA";
    $("#sidebar-name").textContent = state.profile.full_name || "Estudiante";
    $("#sidebar-avatar").textContent = initials;
    $("#top-avatar").textContent = initials;
    $("#top-profile-name").textContent = state.profile.full_name || "Estudiante";
    $("#top-profile-email").textContent = state.profile.email || "Cuenta personal";
    $("#case-count-chip").textContent = state.cases.length;
    fillProfile();
    renderDashboard();
    renderCases();
    populateAnalysisPicker();
    renderRegimeCards();
    document.body.classList.toggle("dark", state.profile.theme === "dark");
  }

  function chart(id, type, labels, values, colors, options = {}) {
    const canvas = $(`#${id}`);
    if (!canvas) return;
    const chartDataExists = labels.length > 0;
    const empty = $(`#empty-${id.replace("chart-", "")}`);
    if (empty) empty.hidden = chartDataExists;
    canvas.hidden = !chartDataExists;
    if (state.charts[id]) state.charts[id].destroy();
    if (!chartDataExists) return;
    if (typeof Chart === "undefined") {
      if (empty) {
        empty.textContent = "Los gráficos requieren conexión a Internet para cargar Chart.js.";
        empty.hidden = false;
      }
      canvas.hidden = true;
      return;
    }
    const axisTicks = { color: "#9B8790", font: { size: 8 } };
    const scales = options.indexAxis === "y"
      ? {
          x: { beginAtZero: true, grid: { color: "#F1EAED" }, ticks: axisTicks },
          y: { grid: { display: false }, ticks: axisTicks },
        }
      : {
          x: { grid: { display: false }, ticks: axisTicks },
          y: { beginAtZero: true, grid: { color: "#F1EAED" }, ticks: { ...axisTicks, callback: value => options.currency ? `S/${value}` : value } },
        };
    state.charts[id] = new Chart(canvas, {
      type,
      data: { labels, datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: type === "line" && Array.isArray(colors) ? "#5D3542" : colors,
        borderWidth: type === "line" ? 2 : 0,
        borderRadius: type === "bar" ? 5 : 0,
        fill: type === "line" ? false : undefined,
        tension: .35,
        pointBackgroundColor: type === "line" && Array.isArray(colors) ? colors : undefined,
        pointBorderColor: type === "line" && Array.isArray(colors) ? "#6D4A56" : undefined,
        pointRadius: type === "line" && Array.isArray(colors) ? 4 : undefined,
        pointHoverRadius: type === "line" && Array.isArray(colors) ? 6 : undefined,
        segment: type === "line" && Array.isArray(colors)
          ? { borderColor: context => colors[context.p0DataIndex] || "#777777" }
          : undefined,
      }] },
      plugins: id === "chart-recommendations" ? [{
        id: "recommendation-center-label",
        afterDraw(currentChart) {
          const area = currentChart.chartArea;
          if (!area) return;
          const count = values.reduce((sum, value) => sum + (Number(value) || 0), 0);
          const centerX = (area.left + area.right) / 2;
          const centerY = (area.top + area.bottom) / 2;
          const { ctx } = currentChart;
          ctx.save();
          ctx.textAlign = "center";
          ctx.fillStyle = "#74163A";
          ctx.font = "700 22px Manrope, sans-serif";
          ctx.fillText(String(count), centerX, centerY - 1);
          ctx.fillStyle = "#5D3542";
          ctx.font = "500 9px 'DM Sans', sans-serif";
          ctx.fillText("casos", centerX, centerY + 13);
          ctx.restore();
        },
      }] : [],
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: type === "doughnut", position: "right", labels: { boxWidth: 8, usePointStyle: true, pointStyle: "circle", color: "#806C75", font: { size: 9 } } }, tooltip: { callbacks: { label: item => `${item.label || ""}: ${options.currency ? money(item.raw) : item.raw}` } } },
        scales: type === "doughnut" ? {} : scales,
        ...options,
      },
    });
  }

  async function renderDashboard() {
    try {
      const data = await api("/api/dashboard");
      $("#stat-total").textContent = data.total;
      $("#stat-analyzed").textContent = data.analyzed;
      $("#stat-regimes").textContent = data.regimes_evaluated;
      $("#stat-recommendations").textContent = data.recommendations;
      const alertCount = data.alerts.reduce((count, entry) => count + entry.items.length, 0);
      $("#notification-count").textContent = alertCount ? String(alertCount) : "";
      $("#notification-count").hidden = !alertCount;
      $(".notification-button").setAttribute("aria-label", alertCount ? `Ver ${alertCount} alertas tributarias` : "Ver alertas tributarias");
      const analysisRate = data.total ? Math.round((data.analyzed / data.total) * 100) : 0;
      $("#analysis-rate").textContent = `${analysisRate}%`;
      $("#analysis-rate-label").textContent = `${data.analyzed} de ${data.total} casos analizados`;
      $("#analysis-progress").style.setProperty("--progress", `${analysisRate}%`);
      const rec = Object.entries(data.recommended);
      chart("chart-recommendations", "doughnut", rec.map(item => regimeName(item[0])), rec.map(item => item[1]), rec.map(item => regimeColor(item[0])), { cutout: "68%" });
      const burdens = Object.entries(data.burden);
      chart("chart-burden", "bar", burdens.map(item => item[0]), burdens.map(item => item[1]), burdens.map(item => regimeColor(item[0])), { currency: true });
      const statuses = Object.entries(data.status).map(([key, value]) => [key === "pending" ? "Pendientes" : "Analizados", value, key === "pending" ? "#F2D28B" : "#A9D6C1"]);
      chart("chart-status", "bar", statuses.map(item => item[0]), statuses.map(item => item[1]), statuses.map(item => item[2]), { indexAxis: "y", plugins: { legend: { display: false } } });
      chart("chart-compare", "line", burdens.map(item => item[0]), burdens.map(item => item[1]), burdens.map(item => regimeColor(item[0])), { currency: true, plugins: { legend: { display: false } } });
      $("#recent-cases").innerHTML = data.recent.map(row => `<tr><td><span class="company-cell"><span class="company-mark">${escapeHtml((row.business_name || "?")[0].toUpperCase())}</span>${escapeHtml(row.business_name)}</span></td><td>${escapeHtml(row.ruc)}</td><td><span class="status-pill ${row.latest_evaluation ? "done" : ""}">${row.latest_evaluation ? "Analizado" : "Pendiente"}</span></td><td>${escapeHtml(regimeName(row.recommended_regime))}</td><td><button class="text-button" data-action="open-case-analysis" data-id="${row.id}">Ver →</button></td></tr>`).join("");
      $("#recent-empty").style.display = data.recent.length ? "none" : "block";
      $("#dashboard-alerts").innerHTML = data.alerts.length ? data.alerts.flatMap(entry => entry.items.map(text => `<div class="alert-row"><span class="alert-dot"></span><span><b>${escapeHtml(entry.case)}:</b> ${escapeHtml(text)}</span></div>`)).join("") : '<div class="blank-state compact">No hay alertas. Las proyecciones aparecerán aquí.</div>';
      $("#pending-list").innerHTML = data.pending.length ? data.pending.slice(0, 4).map(row => `<div class="pending-row"><span class="company-mark">${escapeHtml((row.business_name || "?")[0].toUpperCase())}</span><span><b>${escapeHtml(row.business_name)}</b><br>Requiere evaluación</span><button class="text-button" data-action="evaluate-case" data-id="${row.id}">Evaluar</button></div>`).join("") : '<div class="blank-state compact">Todo al día.</div>';
      $("#activity-list").innerHTML = data.recent.length ? data.recent.slice(0, 4).map(row => `<div class="pending-row"><span class="company-mark">${row.latest_evaluation ? "✓" : "+"}</span><span><b>${escapeHtml(row.business_name)}</b><br>${row.latest_evaluation ? "Evaluación guardada" : "Caso registrado"} · ${escapeHtml((row.updated_at || "").slice(0, 10))}</span></div>`).join("") : '<div class="blank-state compact">Sin actividad registrada.</div>';
    } catch (error) {
      notify(error.message, true);
    }
  }

  function setCaseTab(tab) {
    $$(".mode-tab").forEach(button => button.classList.toggle("active", button.dataset.caseTab === tab));
    $$(".case-tab-panel").forEach(panel => {
      const active = panel.id === `case-tab-${tab}`;
      panel.hidden = !active;
      panel.classList.toggle("active", active);
    });
    if (tab === "directory") renderCases();
  }

  function renderCases() {
    const search = ($("#case-search")?.value || "").trim().toLowerCase();
    const filter = $("#status-filter")?.value || "";
    const rows = state.cases.filter(item => (!filter || item.status === filter) && (!search || `${item.business_name} ${item.ruc}`.toLowerCase().includes(search)));
    $("#all-cases").innerHTML = rows.map(row => `<tr>
      <td><span class="company-cell"><span class="company-mark">${escapeHtml((row.business_name || "?")[0].toUpperCase())}</span>${escapeHtml(row.business_name)}</span></td>
      <td>${escapeHtml(row.ruc)}</td><td>${escapeHtml(row.data.activity || "—")}</td><td>${escapeHtml(row.data.current_regime || "—")}</td>
      <td><span class="status-pill ${row.latest_evaluation ? "done" : ""}">${row.latest_evaluation ? "Analizado" : "Pendiente"}</span></td>
      <td>${escapeHtml((row.updated_at || "").slice(0, 10))}</td>
      <td><div class="row-actions"><button type="button" data-action="evaluate-case" data-id="${row.id}">${row.latest_evaluation ? "Reevaluar" : "Evaluar"}</button><button type="button" data-action="edit-case" data-id="${row.id}">Editar</button><button type="button" data-action="history-case" data-id="${row.id}">Historial</button><button class="danger" type="button" data-action="delete-case" data-id="${row.id}">Eliminar</button></div></td>
    </tr>`).join("");
    $("#cases-empty").style.display = rows.length ? "none" : "block";
    $("#case-count-chip").textContent = state.cases.length;
  }

  function setCaseStep(step) {
    state.caseStep = Math.min(4, Math.max(1, step));
    $$("#case-form [data-form-step]").forEach(section => {
      section.hidden = Number(section.dataset.formStep) !== state.caseStep;
    });
    $$(".wizard-dot").forEach(dot => {
      const current = Number(dot.dataset.formGoto);
      dot.classList.toggle("active", current === state.caseStep);
      dot.classList.toggle("complete", current < state.caseStep);
    });
    $$("[data-guidance-step]").forEach(item => {
      const current = Number(item.dataset.guidanceStep);
      item.classList.toggle("active", current === state.caseStep);
      item.classList.toggle("complete", current < state.caseStep);
    });
    const percent = state.caseStep * 25;
    $("#wizard-progress-fill").style.width = `${percent}%`;
    $("#wizard-progress-percent").textContent = `${percent}%`;
    $("#previous-form-step").disabled = state.caseStep === 1;
    $("#next-form-step").hidden = state.caseStep === 4;
    $("#save-case").hidden = state.caseStep !== 4;
  }

  function validateCaseStep(step) {
    const section = $(`#case-form [data-form-step="${step}"]`);
    const invalidField = section.querySelector(":invalid");
    if (!invalidField) return true;
    invalidField.reportValidity();
    return false;
  }

  function goToCaseStep(step) {
    const target = Math.min(4, Math.max(1, step));
    if (target > state.caseStep) {
      for (let current = state.caseStep; current < target; current += 1) {
        if (!validateCaseStep(current)) return;
      }
    }
    setCaseStep(target);
    $("#case-form-title").textContent = $("#case-form").elements.case_id.value ? "Editar caso" : "Registro de nuevo caso";
  }

  function fillCaseForm(data = {}) {
    const form = $("#case-form");
    form.reset();
    form.elements.case_id.value = data.id || "";
    setCaseStep(1);
    const plans = data.data?.plans || {};
    for (const [key, value] of Object.entries(data.data || {})) {
      const field = form.elements[key];
      if (!field || key === "plans") continue;
      if (field.type === "checkbox") field.checked = Boolean(value);
      else if (field.type !== "hidden" && value != null) field.value = value;
    }
    for (const [key, value] of Object.entries(plans)) {
      const field = form.elements[`plans_${key}`];
      if (field) field.checked = Boolean(value);
    }
    if (data.data?.plans?.import && form.elements.plans_import) form.elements.plans_import.checked = true;
    $("#case-form-title").textContent = data.id ? "Editar caso" : "Registro de nuevo caso";
    $("#save-case").innerHTML = data.id ? "Guardar cambios <span>→</span>" : "Guardar caso <span>→</span>";
    $("#cancel-edit").hidden = !data.id;
  }

  function caseDataFromForm(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.excluded_activity = form.elements.excluded_activity.checked;
    data.plans = {};
    ["increase_income", "exceed_limits", "hire_workers", "add_branches", "import", "export", "add_activities", "grow_company", "excluded_activity"].forEach(key => {
      data.plans[key] = form.elements[`plans_${key}`].checked;
    });
    return data;
  }

  async function saveCase(event) {
    event.preventDefault();
    const form = event.currentTarget;
    for (let step = 1; step <= 4; step += 1) {
      setCaseStep(step);
      if (!validateCaseStep(step)) return;
    }
    const data = caseDataFromForm(form);
    const id = form.elements.case_id.value;
    try {
      await api(id ? `/api/cases/${id}` : "/api/cases", {
        method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
      });
      notify(id ? "Los cambios del caso fueron guardados." : "El caso quedó registrado en SQLite.");
      fillCaseForm();
      await refresh();
      setCaseTab("directory");
    } catch (error) {
      notify(error.message, true);
    }
  }

  function populateAnalysisPicker() {
    const picker = $("#analysis-case");
    const selected = picker.value || state.activeCase;
    picker.innerHTML = '<option value="">Selecciona un caso registrado</option>' + state.cases.map(item => `<option value="${item.id}">${escapeHtml(item.business_name)} · ${escapeHtml(item.ruc)}</option>`).join("");
    if (selected && state.cases.some(item => String(item.id) === String(selected))) picker.value = selected;
  }

  const regimeSunatPages = {
    NRUS: { url: "https://orientacion.sunat.gob.pe/nuevo-regimen-unico-simplificado-nuevo-rus", label: "Nuevo RUS: concepto y reglas" },
    RER: { url: "https://orientacion.sunat.gob.pe/2932-concepto-del-regimen-especial", label: "RER: concepto del régimen" },
    RMT: { url: "https://orientacion.sunat.gob.pe/6825-01-personas-comprendidas", label: "RMT: personas comprendidas" },
    RG: { url: "https://orientacion.sunat.gob.pe/concepto-del-impuesto-a-la-renta-regimen-general", label: "Régimen General: concepto" },
  };

  const regimeIcons = {
    NRUS: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M4 13 7 6h18l3 7v3a3 3 0 0 1-5 2 3 3 0 0 1-5 0 3 3 0 0 1-5 0 3 3 0 0 1-5 0 3 3 0 0 1-4-2v-3Z"/><path d="M7 18v10h18V18M12 28v-6h8v6"/></svg>',
    RER: '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="4" y="11" width="24" height="17" rx="3"/><path d="M11 11V8a5 5 0 0 1 10 0v3M4 17h24M14 17v3h4v-3"/></svg>',
    RMT: '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="9" r="5"/><circle cx="6" cy="13" r="3.5"/><circle cx="26" cy="13" r="3.5"/><path d="M7 28v-3a9 9 0 0 1 18 0v3M1 27v-3a5 5 0 0 1 6-5M31 27v-3a5 5 0 0 0-6-5"/></svg>',
    RG: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M7 28V5h18v23M4 28h24M12 10h3m5 0h1m-9 5h3m5 0h1m-9 5h3m5 0h1m-7 8v-5h4v5"/></svg>',
  };

  function renderRegimeCards() {
    $("#regime-cards").innerHTML = state.regimes.map(item => {
      const source = regimeSunatPages[item.code];
      return `<article class="regime-card regime-card-${escapeHtml(item.code)}"><div class="regime-card-heading"><span class="regime-code" aria-hidden="true">${regimeIcons[item.code] || ""}</span><div><h3>${escapeHtml(item.code)}</h3><b>${escapeHtml(item.name)}</b></div></div><p>${escapeHtml(item.description)}</p><a class="regime-sunat-link" href="${source.url}" target="_blank" rel="noopener noreferrer" aria-label="Abrir en SUNAT: ${escapeHtml(source.label)}">Consultar en SUNAT <span aria-hidden="true">↗</span></a></article>`;
    }).join("");
  }

  function compareHtml(item) {
    const regime = item.latest_evaluation;
    if (!regime) return '<div class="blank-state"><span class="blank-icon">◫</span><h3>Este caso todavía no tiene evaluación</h3><p>Ejecuta el motor de reglas para revisar elegibilidad, estimaciones y riesgos futuros.</p><button class="button button-primary" type="button" data-action="evaluate-case" data-id="' + item.id + '">Evaluar este caso</button></div>';
    const result = regime;
    const codes = Object.keys(result.regimes);
    const criteria = [
      ["Elegibilidad", code => {
        const status = result.regimes[code].eligibility_status;
        if (status === "unknown") return '<span class="eligibility-unknown">● No verificada</span>';
        return status === "eligible" ? '<span class="eligibility-yes">● Elegible</span>' : '<span class="eligibility-no">● No elegible</span>';
      }],
      ["Motivo", code => compactCell(result.regimes[code].reasons.length ? result.regimes[code].reasons.join(" ") : "Sin observaciones")],
      ["Ingresos anuales", code => { const r = state.regimes.find(reg => reg.code === code); return r?.effective_income_limit ? money(r.effective_income_limit) : "Sin límite"; }],
      ["Tope de compras", code => { const r = state.regimes.find(reg => reg.code === code); return r?.purchase_limit ? money(r.purchase_limit) : "Sin límite"; }],
      ["Activos / trabajadores", code => { const r = state.regimes.find(reg => reg.code === code); return `${r?.asset_limit ? money(r.asset_limit) : "Sin límite"} / ${r?.workers_limit || "Sin límite"}`; }],
      ["Renta anual est.", code => money(result.regimes[code].estimated_annual_income_tax)],
      ["IGV anual est.", code => money(result.regimes[code].estimated_annual_igv)],
      ["Total anual est.", code => money(result.regimes[code].estimated_annual_total)],
      ["Puntaje", code => result.decision_scores?.[code] ? `${Math.round(result.decision_scores[code].total_score * 100)} / 100` : "—"],
      ["Renta mensual est.", code => money(result.regimes[code].estimated_monthly_income_tax)],
      ["IGV / comprobantes", code => { const r = state.regimes.find(reg => reg.code === code); return compactCell(`${r?.igv || ""} ${r?.receipts || ""}`); }],
      ["Libros", code => compactCell(state.regimes.find(reg => reg.code === code)?.books || "")],
      ["Obligaciones", code => compactCell(state.regimes.find(reg => reg.code === code)?.obligations || "")],
      ["Normativa", code => compactCell(result.regimes[code].legal_source)],
    ];
    const table = `<div class="table-scroll"><table class="compare-table"><thead><tr><th>CRITERIO</th>${codes.map(code => `<th><a class="regime-table-link" href="${regimeSunatPages[code].url}" target="_blank" rel="noopener noreferrer" aria-label="Consultar ${escapeHtml(regimeSunatPages[code].label)} en SUNAT">${escapeHtml(code)} ↗</a></th>`).join("")}</tr></thead><tbody>${criteria.map(([label, value]) => `<tr><td><b>${escapeHtml(label)}</b></td>${codes.map(code => `<td>${value(code)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    const recommendation = escapeHtml(regimeName(result.recommendation));
    const risks = [...(result.alerts || []), ...(result.missing_or_caveats || [])];
    const future = result.future_projection || [];
    return `<div class="analysis-result">
      <div class="analysis-case-head"><div><span class="eyebrow">RESULTADO DE EVALUACIÓN · ${escapeHtml(item.code)}</span><h2>${escapeHtml(item.business_name)}</h2><p>RUC ${escapeHtml(item.ruc)} · ${escapeHtml(item.data.person_type === "juridica" ? "Persona jurídica" : "Persona natural")} · ${escapeHtml(item.data.activity || "Actividad no especificada")}</p></div>
      <div class="analysis-actions"><button class="button button-outline" data-action="edit-case" data-id="${item.id}">Editar</button><button class="button button-outline" data-action="evaluate-case" data-id="${item.id}">↻ Reevaluar</button><a class="button button-outline" href="/api/cases/${item.id}/comparison.xlsx">↓ Excel</a><a class="button button-primary" href="/api/cases/${item.id}/report.pdf">↓ Informe PDF</a></div></div>
      <div class="analysis-metrics"><div class="metric-box"><span>Ingresos proyectados</span><b>${money(item.data.projected_annual_income)}</b></div><div class="metric-box"><span>Compras proyectadas</span><b>${money(item.data.projected_annual_purchases)}</b></div><div class="metric-box"><span>Costos y gastos</span><b>${money(Number(item.data.annual_costs || 0) + Number(item.data.annual_expenses || 0))}</b></div><div class="metric-box"><span>Regímenes elegibles</span><b>${result.eligible_regimes.length} de 4</b></div></div>
      ${table}
      <div class="recommendation-card"><div class="recommendation-seal">✦</div><div><span class="eyebrow">RÉGIMEN RECOMENDADO</span><h3>${recommendation}</h3><a class="recommendation-sunat-link" href="${regimeSunatPages[result.recommendation].url}" target="_blank" rel="noopener noreferrer">Abrir este régimen en SUNAT ↗</a><p>${escapeHtml(result.recommendation_reason)}</p><p><b>Método de selección:</b> ${escapeHtml(result.decision_method || "")}</p></div></div>
      <div class="result-columns"><div class="result-box"><h4>Ventajas del régimen recomendado</h4><ul><li>${escapeHtml(result.recommendation_benefits)}</li></ul><h4 style="margin-top:12px">Obligaciones principales</h4><ul><li>${escapeHtml(result.recommendation_obligations)}</li></ul></div><div class="result-box"><h4>Proyección de crecimiento</h4><ul>${future.map(text => `<li>${escapeHtml(text)}</li>`).join("")}</ul></div><div class="result-box"><h4>Alternativas y limitaciones</h4>${result.alternatives_considered?.length ? `<ul>${result.alternatives_considered.map(row => `<li>${escapeHtml(regimeName(row.regime))}: ${escapeHtml(money(row.estimated_total))} estimado. ${escapeHtml(row.reason_not_selected)}</li>`).join("")}</ul>` : "<p>No hay alternativas adicionales elegibles con los datos actuales.</p>"}<p><b>Limitaciones:</b> ${escapeHtml(result.recommendation_limitations || "Revisa las exclusiones aplicables antes de decidir.")}</p></div><div class="result-box"><h4>Alertas y riesgos</h4>${risks.length ? `<ul>${risks.map(text => `<li>${escapeHtml(text)}</li>`).join("")}</ul>` : '<ul><li>No se detectaron alertas con los datos declarados.</li></ul>'}</div></div>
      <div class="result-caveat"><b>Simulación, no declaración oficial.</b> ${result.assumptions.map(escapeHtml).join(" ")}</div>
    </div>`;
  }

  function emptyComparisonHtml() {
    const illustration = $("#regime-detail").dataset.emptyImage === "true"
      ? '<img src="/static/images/imagenes_regimenes/comparacion_vacia.png" alt="" aria-hidden="true">'
      : '<span class="comparison-empty-icon" aria-hidden="true"><svg viewBox="0 0 120 100"><path d="M25 15h55a8 8 0 0 1 8 8v62H32a12 12 0 0 1-12-12V23a8 8 0 0 1 5-8Z"/><path d="M20 74a12 12 0 0 1 12-12h56M36 32h35M36 43h28M35 64l9-13 9 7 11-17"/><circle cx="77" cy="68" r="15"/><path d="m88 79 15 15"/></svg></span>';
    return `<div class="comparison-empty">${illustration}<div class="comparison-empty-copy"><h2>Elige un caso para comparar</h2><p>El resultado se mostrará aquí sin crear un apartado adicional.</p><button class="button button-primary" type="button" data-view="cases"><span class="button-plus">＋</span> Registrar un caso</button></div></div>`;
  }

  function renderAnalysis(caseId) {
    state.activeCase = String(caseId || "");
    const item = state.cases.find(entry => String(entry.id) === state.activeCase);
    const target = $("#regime-detail");
    if (!item) {
      target.innerHTML = emptyComparisonHtml();
      return;
    }
    target.innerHTML = compareHtml(item);
  }

  async function evaluateCase(id) {
    try {
      await api(`/api/cases/${id}/evaluate`, { method: "POST" });
      await refresh();
      navigate("regimes");
      $("#analysis-case").value = String(id);
      renderAnalysis(id);
      notify("Evaluación guardada en el historial del caso.");
    } catch (error) {
      notify(error.message, true);
    }
  }

  function fillProfile() {
    const form = $("#profile-form");
    if (!form) return;
    for (const key of ["full_name", "email", "career", "academic_cycle", "uit", "theme"]) {
      const field = form.elements[key];
      if (field) field.value = state.profile[key] ?? (key === "career" ? "Contabilidad y Finanzas" : "");
    }
  }

  function profileData() {
    const form = $("#profile-form");
    return Object.fromEntries(new FormData(form).entries());
  }

  async function saveProfile(event) {
    event?.preventDefault();
    try {
      state.profile = await api("/api/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profileData()) });
      document.body.classList.toggle("dark", state.profile.theme === "dark");
      await refresh();
      notify("Perfil y configuración guardados.");
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function logout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
      window.location.assign("/");
    } catch (error) {
      notify(error.message, true);
    }
  }

  const sources = [
    { category: "General", name: "Texto Único Ordenado de la Ley del Impuesto a la Renta", number: "D. S. N.° 179-2004-EF", date: "08 oct. 2004", articles: "Arts. 28, 37, 55, 85 y disposiciones de regímenes especiales", topic: "Rentas empresariales de tercera categoría, determinación de la renta neta, tasa anual y pagos a cuenta.", explanation: "Base legal general para evaluar la renta empresarial. Debe consultarse el texto actualizado y las modificaciones vigentes.", url: "https://www.sunat.gob.pe/legislacion/" },
    { category: "NRUS", name: "Nuevo Régimen Único Simplificado", number: "Decreto Legislativo N.° 937", date: "14 dic. 2003", articles: "Régimen, sujetos comprendidos, categorías y exclusiones", topic: "Reglas especiales del Nuevo RUS para pequeños contribuyentes.", explanation: "Consulta el apartado de orientación SUNAT sobre el concepto del Nuevo RUS.", url: regimeSunatPages.NRUS.url },
    { category: "RER", name: "Régimen Especial del Impuesto a la Renta", number: "D. S. N.° 179-2004-EF (TUO de la LIR)", date: "08 oct. 2004", articles: "Arts. 117 al 124", topic: "Sujetos comprendidos, acogimiento, obligaciones, cuotas y exclusiones del RER.", explanation: "Consulta el apartado de orientación SUNAT sobre el concepto y las actividades comprendidas en el RER.", url: regimeSunatPages.RER.url },
    { category: "RMT", name: "Régimen MYPE Tributario del Impuesto a la Renta", number: "Decreto Legislativo N.° 1269", date: "20 dic. 2016", articles: "Arts. 1 al 10", topic: "Ámbito de aplicación, acogimiento, tasa anual, pagos a cuenta y exclusiones del RMT.", explanation: "Consulta el apartado de orientación SUNAT sobre los contribuyentes comprendidos en el RMT.", url: regimeSunatPages.RMT.url },
    { category: "RMT", name: "Reglamento del Régimen MYPE Tributario", number: "D. S. N.° 403-2016-EF", date: "31 dic. 2016", articles: "Disposiciones reglamentarias del D. Leg. 1269", topic: "Aplicación de las reglas del Régimen MYPE Tributario.", explanation: "Verifica el texto oficial y disposiciones posteriores en el portal de normas legales del MEF.", url: "https://www.gob.pe/institucion/mef/normas-legales" },
    { category: "IGV", name: "TUO de la Ley del Impuesto General a las Ventas e ISC", number: "D. S. N.° 055-99-EF", date: "15 abr. 1999", articles: "Arts. 1, 18, 19 y 33 (referenciales)", topic: "Operaciones gravadas, crédito fiscal y exportación.", explanation: "El uso del crédito fiscal depende del cumplimiento de requisitos formales y sustanciales; verifica el texto actualizado.", url: "https://www.sunat.gob.pe/legislacion/" },
    { category: "RG", name: "Régimen General del Impuesto a la Renta", number: "Orientación SUNAT", date: "Consulta en línea", articles: "Concepto y sujetos comprendidos", topic: "Contribuyentes comprendidos y características del Régimen General.", explanation: "Consulta el apartado de orientación SUNAT sobre el concepto del Régimen General.", url: regimeSunatPages.RG.url },
    { category: "IGV", name: "Consulta de normas legales del Ministerio de Economía y Finanzas", number: "Repositorio institucional", date: "Consulta en línea", articles: "Buscador oficial de dispositivos legales", topic: "Verificación de decretos supremos, reglamentos y disposiciones tributarias.", explanation: "Busca el número exacto de la norma y revisa sus modificatorias y vigencia.", url: "https://www.gob.pe/institucion/mef/normas-legales" },
  ];

  function renderGuide() {
    const query = ($("#guide-search").value || "").toLowerCase();
    const category = $("#guide-category").value;
    const matching = sources.filter(item => (!category || item.category === category) && (!query || `${item.name} ${item.number} ${item.articles} ${item.topic} ${item.explanation}`.toLowerCase().includes(query)));
    $("#guide-result-count").textContent = `${matching.length} ${matching.length === 1 ? "referencia" : "referencias"}`;
    $("#guide-cards").innerHTML = matching.length ? matching.map(item => `<article class="panel guide-card" data-category="${escapeHtml(item.category)}"><div class="guide-card-top"><span class="guide-tag">${escapeHtml(item.category)}</span><span class="guide-meta guide-date"><svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3.5" width="12" height="11" rx="1.5"/><path d="M5 2v3M11 2v3M2 7h12"/></svg>${escapeHtml(item.date)}</span></div><div class="guide-card-title"><span class="guide-document-icon" aria-hidden="true"><svg viewBox="0 0 20 22"><path d="M4 1.5h8l4 4V20a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5z"/><path d="M12 1.5v4h4M7 10h6M7 13h6M7 16h6"/></svg></span><h3>${escapeHtml(item.name)}</h3></div><div class="guide-reference"><span>REFERENCIA</span><b>${escapeHtml(item.number)}</b><small>${escapeHtml(item.articles)}</small></div><div class="guide-topic"><b>Tema</b><p>${escapeHtml(item.topic)}</p></div><p class="article-note">${escapeHtml(item.explanation)}</p><a class="guide-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">Consultar fuente oficial <span aria-hidden="true">↗</span></a></article>`).join("") : '<div class="panel blank-state"><h3>No se encontraron referencias</h3><p>Prueba otros términos o una categoría diferente.</p></div>';
  }

  async function previewExcel(event) {
    event.preventDefault();
    const input = $("#excel-file");
    if (!input.files.length) return;
    const formData = new FormData();
    formData.append("file", input.files[0]);
    try {
      const preview = await api("/api/import/preview", { method: "POST", body: formData });
      state.importBatch = preview.batch_id;
      state.importRows = preview.rows;
      renderImportPreview();
    } catch (error) {
      notify(error.message, true);
    }
  }

  function renderImportPreview() {
    const root = $("#import-preview");
    const rows = state.importRows;
    const requiredText = ["business_name", "ruc", "person_type", "activity"];
    const requiredNumbers = ["monthly_income", "projected_annual_income", "monthly_purchases", "projected_annual_purchases", "annual_costs", "annual_expenses", "fixed_assets", "taxable_share", "workers", "workers_per_shift"];
    const optionalNumbers = ["nrus_exempt_assets"];
    const validRuc = value => {
      const digits = String(value || "").replace(/\s/g, "");
      if (!/^\d{11}$/.test(digits)) return false;
      const total = [...digits.slice(0, 10)].reduce((sum, digit, index) => sum + Number(digit) * [5, 4, 3, 2, 7, 6, 5, 4, 3, 2][index], 0);
      let check = (11 - total % 11) % 11;
      if (check === 10) check = 0;
      return check === Number(digits[10]);
    };
    const validateRows = () => {
      const seen = new Set(state.cases.map(item => String(item.ruc)));
      rows.forEach(row => {
        const data = row.data;
        const issues = [];
        requiredText.forEach(key => { if (!String(data[key] || "").trim()) issues.push(`Falta ${key}.`); });
        if (!validRuc(data.ruc)) issues.push("RUC o dígito verificador no válido.");
        if (!["natural", "juridica"].includes(String(data.person_type))) issues.push("Tipo de persona no válido.");
        requiredNumbers.forEach(key => {
          const value = Number(data[key]);
          if (data[key] === "" || data[key] == null || !Number.isFinite(value) || value < 0) issues.push(`Revisa ${key}.`);
        });
        optionalNumbers.forEach(key => {
          if (data[key] !== "" && data[key] != null && (!Number.isFinite(Number(data[key])) || Number(data[key]) < 0)) issues.push(`Revisa ${key}.`);
        });
        if (Number(data.taxable_share) > 1) issues.push("La proporción gravada debe estar entre 0 y 1.");
        if (Number(data.nrus_exempt_assets || 0) > Number(data.fixed_assets || 0)) issues.push("Los activos que podrían excluirse superan el total de activos fijos.");
        if (String(data.business_name || "").toLowerCase().startsWith("ejemplo académico")) issues.push("Fila demostrativa: elimínala antes de importar.");
        if (seen.has(String(data.ruc))) issues.push("RUC duplicado.");
        seen.add(String(data.ruc));
        row.issues = issues;
      });
    };
    const fields = [
      ["business_name", "NEGOCIO", "text"], ["ruc", "RUC", "text"], ["person_type", "PERSONA", "select"],
      ["activity", "ACTIVIDAD", "text"], ["monthly_income", "INGRESO MES", "number"],
      ["projected_annual_income", "INGRESO AÑO", "number"], ["monthly_purchases", "COMPRAS MES", "number"],
      ["projected_annual_purchases", "COMPRAS AÑO", "number"], ["annual_costs", "COSTOS AÑO", "number"],
      ["annual_expenses", "GASTOS AÑO", "number"], ["fixed_assets", "ACTIVOS", "number"], ["nrus_exempt_assets", "ACTIVOS EXCLUIBLES", "number"],
      ["taxable_share", "GRAVADO 0–1", "number"], ["workers", "TRABAJADORES", "number"],
      ["workers_per_shift", "MÁX. TURNO", "number"],
    ];
    validateRows();
    const invalid = rows.filter(row => row.issues.length).length;
    root.hidden = false;
    root.innerHTML = `<h3>Vista previa · ${rows.length} registro(s) ${invalid ? `· <span class="preview-error">${invalid} con observaciones</span>` : "· listos para importar"}</h3><p class="form-feedback">Corrige las celdas editables aquí; si una observación corresponde a otra columna, corrígela en Excel y vuelve a subirlo.</p><div class="table-scroll"><table><thead><tr><th>FILA</th>${fields.map(field => `<th>${field[1]}</th>`).join("")}<th>VALIDACIÓN</th></tr></thead><tbody>${rows.map((row, index) => `<tr><td>${row.row}</td>${fields.map(([key, , type]) => `<td>${type === "select" ? `<select data-import-index="${index}" data-import-key="${key}"><option value="natural" ${row.data[key] === "natural" ? "selected" : ""}>Natural</option><option value="juridica" ${row.data[key] === "juridica" ? "selected" : ""}>Jurídica</option></select>` : `<input data-import-index="${index}" data-import-key="${key}" type="${type}" value="${escapeHtml(row.data[key] ?? "")}" ${key === "ruc" ? 'maxlength="11"' : type === "number" ? 'min="0" step="any"' : ""} style="min-width:${type === "number" ? "82px" : "125px"}">`}</td>`).join("")}<td class="${row.issues.length ? "preview-error" : ""}">${row.issues.length ? escapeHtml(row.issues.join(" ")) : "Correcto"}</td></tr>`).join("")}</tbody></table></div><div class="form-actions"><span class="form-feedback">No se guardará ningún registro hasta confirmar la importación.</span><button class="button button-primary" type="button" id="confirm-import" ${invalid ? "disabled" : ""}>Confirmar importación <span>→</span></button></div>`;
    $$("[data-import-index]", root).forEach(input => input.addEventListener("change", () => {
      const index = Number(input.dataset.importIndex);
      const key = input.dataset.importKey;
      state.importRows[index].data[key] = input.type === "number" ? input.value : input.value.trim();
      renderImportPreview();
    }));
    $("#confirm-import")?.addEventListener("click", confirmImport);
  }

  async function confirmImport() {
    try {
      const result = await api("/api/import/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ batch_id: state.importBatch, rows: state.importRows }) });
      notify(`${result.imported} caso(s) importado(s) correctamente.`);
      state.importBatch = null;
      state.importRows = [];
      $("#import-preview").hidden = true;
      $("#import-form").reset();
      await refresh();
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function showHistory(id) {
    try {
      const history = await api(`/api/cases/${id}/history`);
      const item = state.cases.find(row => String(row.id) === String(id));
      $("#regime-dialog-content").innerHTML = `<span class="eyebrow">HISTORIAL DEL CASO</span><h2>${escapeHtml(item?.business_name || "Evaluaciones")}</h2>${history.length ? history.map((entry, index) => `<div class="result-box" style="margin-top:9px"><h4>Evaluación ${history.length - index} · ${escapeHtml(entry.created_at)}</h4><p><b>${entry.result.recommendation ? `Recomendación: ${escapeHtml(regimeName(entry.result.recommendation))}` : "Evaluación histórica anterior al motor actual"}</b></p><p>${escapeHtml(entry.result.recommendation_reason)}</p></div>`).join("") : "<p>Este caso aún no tiene evaluaciones guardadas.</p>"}`;
      $("#regime-dialog").showModal();
    } catch (error) {
      notify(error.message, true);
    }
  }

  document.addEventListener("click", async event => {
    const viewButton = event.target.closest("[data-view]");
    if (viewButton) { navigate(viewButton.dataset.view); return; }
    const tab = event.target.closest("[data-case-tab]");
    if (tab) { setCaseTab(tab.dataset.caseTab); return; }
    const formStep = event.target.closest("[data-form-goto]");
    if (formStep) { goToCaseStep(Number(formStep.dataset.formGoto)); return; }
    const action = event.target.closest("[data-action]");
    if (!action) return;
    const id = action.dataset.id;
    switch (action.dataset.action) {
      case "new-case":
        navigate("cases"); setCaseTab("manual"); fillCaseForm(); $("#case-form").scrollIntoView({ behavior: "smooth", block: "start" }); break;
      case "refresh":
        await refresh(); notify("Panel actualizado con los registros de SQLite."); break;
      case "show-alerts":
        if (!$("#view-dashboard").classList.contains("active")) navigate("dashboard");
        $("#dashboard-alert-panel").scrollIntoView({ behavior: "smooth", block: "center" });
        break;
      case "evaluate-case":
        await evaluateCase(id); break;
      case "open-case-analysis":
        navigate("regimes"); $("#analysis-case").value = id; renderAnalysis(id); break;
      case "edit-case": {
        const row = state.cases.find(item => String(item.id) === String(id));
        if (row) { navigate("cases"); setCaseTab("manual"); fillCaseForm(row); $("#case-form").scrollIntoView({ behavior: "smooth", block: "start" }); }
        break;
      }
      case "delete-case":
        if (window.confirm("¿Eliminar este caso y todo su historial de evaluaciones? Esta acción no se puede deshacer.")) {
          try { await api(`/api/cases/${id}`, { method: "DELETE" }); await refresh(); notify("Caso e historial eliminados."); }
          catch (error) { notify(error.message, true); }
        }
        break;
      case "history-case":
        await showHistory(id); break;
    }
  });

  $("#mobile-menu").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  $("#case-form").addEventListener("submit", saveCase);
  $("#next-form-step").addEventListener("click", () => goToCaseStep(state.caseStep + 1));
  $("#previous-form-step").addEventListener("click", () => setCaseStep(state.caseStep - 1));
  $("#cancel-edit").addEventListener("click", () => fillCaseForm());
  $("#case-search").addEventListener("input", renderCases);
  $("#status-filter").addEventListener("change", renderCases);
  $("#analysis-case").addEventListener("change", event => renderAnalysis(event.target.value));
  $("#profile-form").addEventListener("submit", saveProfile);
  $("#logout-button").addEventListener("click", logout);
  $("#show-columns").addEventListener("click", () => {
    const panel = $("#columns-panel");
    panel.hidden = !panel.hidden;
    panel.textContent = `Obligatorias: business_name, ruc, person_type, projected_annual_income, projected_annual_purchases. Opcionales: ${state.regimes.length ? "monthly_income, monthly_purchases, annual_costs, annual_expenses, fixed_assets, taxable_share, workers, activity, ciiu, locales, branches, current_regime, excluded_activity y columnas plans_*." : ""}`;
  });
  $("#import-form").addEventListener("submit", previewExcel);
  const uploadZone = $("#import-form");
  ["dragenter", "dragover"].forEach(name => uploadZone.addEventListener(name, event => {
    event.preventDefault();
    uploadZone.classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach(name => uploadZone.addEventListener(name, event => {
    event.preventDefault();
    uploadZone.classList.remove("dragging");
  }));
  uploadZone.addEventListener("drop", event => {
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    $("#excel-file").files = files;
    $("#excel-file").dispatchEvent(new Event("change", { bubbles: true }));
  });
  $("#excel-file").addEventListener("change", event => {
    const label = $("#import-form label b");
    if (event.target.files?.length) label.textContent = event.target.files[0].name;
  });
  $("#guide-search").addEventListener("input", renderGuide);
  $("#guide-category").addEventListener("change", renderGuide);
  $$("[data-close-dialog]").forEach(button => button.addEventListener("click", () => $("#regime-dialog").close()));
  $("#regime-dialog").addEventListener("click", event => { if (event.target === $("#regime-dialog")) $("#regime-dialog").close(); });

  refresh().then(renderGuide).catch(error => notify(error.message, true));
})();
