/* =========================================================================
   Static-edition shell.
   * Analysis pages: HTML pre-rendered by the Flask app for every filter
     combination (pages/<page>.json). This file only picks the right one.
   * Simulator: a JavaScript port of simulate_visit() from
     data/generate_aadhaar_auth_dataset.py, using its exported ASSUMPTIONS.
   * Data Explorer: filters and pages through attempts.csv in the browser.
   ========================================================================= */

const VIEW = document.getElementById("view");
const FILTERED_ROUTES = ["overview", "bias", "quality", "system", "repeated", "fairness"];
const ALL_ROUTES = FILTERED_ROUTES.concat(["simulator", "methodology", "explorer"]);

// Flask URLs that appear inside pre-rendered pages, mapped to routes here.
const PATH_TO_ROUTE = {
  "/": "overview", "/bias": "bias", "/quality": "quality", "/system": "system",
  "/repeated": "repeated", "/fairness": "fairness", "/simulator": "simulator",
  "/methodology": "methodology", "/explorer": "explorer",
};

// The global filters (state, area type, service), shared by analysis pages.
let filters = { state: "", area_type: "", service_type: "" };
let currentRoute = null;
const jsonCache = {};

/* ---------------------------------------------------------------- helpers */

/** Escape text before putting it into HTML. */
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Load a JSON file published next to the page (cached after the first load). */
async function loadJson(path) {
  if (!jsonCache[path]) {
    jsonCache[path] = fetch(path).then(function (response) {
      if (!response.ok) { throw new Error(path + " could not be loaded"); }
      return response.json();
    });
  }
  return jsonCache[path];
}

/** Remove charts from the previous page before drawing new ones. */
function destroyCharts() {
  Object.values(Chart.instances).forEach(function (chart) { chart.destroy(); });
}

/** Run a pre-rendered page's script in its own scope. */
function runPageScript(code) {
  const script = document.createElement("script");
  script.textContent = "(function () {\n" + code + "\n})();";
  document.body.appendChild(script);
  script.remove();
}

function filterKey() {
  return [filters.state, filters.area_type, filters.service_type].join("|");
}

function showError(message) {
  VIEW.innerHTML = '<div class="empty-state">' + escapeHtml(message) + "</div>";
}

/* -------------------------------------------------------------- routing */

function markActiveNav(route) {
  document.querySelectorAll(".nav a").forEach(function (link) {
    link.classList.toggle("active", link.dataset.route === route);
  });
}

async function showRoute(route) {
  const changedPage = route !== currentRoute;
  currentRoute = route;
  markActiveNav(route);
  applyThemeColors();
  destroyCharts();
  try {
    if (FILTERED_ROUTES.includes(route)) {
      const pages = await loadJson("pages/" + route + ".json");
      showFragment(pages[filterKey()]);
    } else if (route === "methodology") {
      showFragment(await loadJson("pages/methodology.json"));
    } else if (route === "simulator") {
      await showSimulator();
    } else if (route === "explorer") {
      await showExplorer();
    }
  } catch (error) {
    showError("This page could not be loaded. Please reload. (" + error.message + ")");
  }
  if (changedPage) { window.scrollTo(0, 0); }
}

function showFragment(fragment) {
  if (!fragment) { showError("No data for this filter"); return; }
  VIEW.innerHTML = fragment.body;
  fragment.scripts.forEach(runPageScript);
}

function routeFromHash() {
  const name = location.hash.replace("#", "");
  return ALL_ROUTES.includes(name) ? name : "overview";
}

function goTo(route) {
  if (location.hash === "#" + route) {
    showRoute(route);
  } else {
    location.hash = route;   // triggers hashchange -> showRoute
  }
}

window.addEventListener("hashchange", function () { showRoute(routeFromHash()); });

/** Links inside pre-rendered pages still point at Flask URLs: translate them. */
document.addEventListener("click", function (event) {
  const link = event.target.closest("a");
  if (!link) { return; }
  const href = link.getAttribute("href") || "";
  if (!href.startsWith("/")) { return; }
  const parts = href.split("?");
  const route = PATH_TO_ROUTE[parts[0]];
  if (!route) { return; }
  event.preventDefault();
  if (FILTERED_ROUTES.includes(route)) {
    const query = new URLSearchParams(parts[1] || "");
    filters = {
      state: query.get("state") || "",
      area_type: query.get("area_type") || "",
      service_type: query.get("service_type") || "",
    };
  }
  goTo(route);
});

/** Global filter bar: read the three drop-downs and redraw the page. */
function readFilterBar(form) {
  filters = {
    state: form.elements.state.value,
    area_type: form.elements.area_type.value,
    service_type: form.elements.service_type.value,
  };
  showRoute(currentRoute);
}

VIEW.addEventListener("submit", function (event) {
  const form = event.target;
  if (form.classList.contains("filter-bar") && FILTERED_ROUTES.includes(currentRoute)) {
    event.preventDefault();
    readFilterBar(form);
  }
});

VIEW.addEventListener("change", function (event) {
  const form = event.target.form;
  if (form && form.classList.contains("filter-bar") && FILTERED_ROUTES.includes(currentRoute)) {
    readFilterBar(form);
  }
});

// Charts take their neutral colours from the theme; redraw if it changes.
if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    showRoute(currentRoute);
  });
}

/* ------------------------------------------------------------ dataset (CSV) */

let attemptsPromise = null;

/** Load attempts.csv once and turn each line into an object. */
function loadAttempts() {
  if (!attemptsPromise) {
    attemptsPromise = fetch("attempts.csv")
      .then(function (response) { return response.text(); })
      .then(parseCsv);
  }
  return attemptsPromise;
}

/** The CSV has no quoted fields, so splitting on commas is safe here. */
function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(",");
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split(",");
    const row = {};
    header.forEach(function (column, index) { row[column] = cells[index]; });
    rows.push(row);
  }
  return { header: header, rows: rows };
}

function rowMatchesGlobalFilters(row) {
  return (!filters.state || row.state === filters.state)
    && (!filters.area_type || row.area_type === filters.area_type)
    && (!filters.service_type || row.service_type === filters.service_type);
}

/* The quality page's scatter is drawn from the CSV in the browser (storing
   ~7,000 points for each of the 140 filter views would make the site huge). */
const drawScatterFromData = qualityScatter;
qualityScatter = function (canvasId, scatter, threshold) {
  if (!scatter.client_side) {
    drawScatterFromData(canvasId, scatter, threshold);
    return;
  }
  loadAttempts().then(function (data) {
    if (!document.getElementById(canvasId)) { return; }   // page changed meanwhile
    const points = { genuine: [], impostor: [] };
    data.rows.forEach(function (row) {
      if (row.match_score === "" || !rowMatchesGlobalFilters(row)) { return; }
      const point = { x: Number(row.biometric_quality), y: Number(row.match_score) };
      if (row.is_genuine_user === "True") { points.genuine.push(point); } else { points.impostor.push(point); }
    });
    drawScatterFromData(canvasId, points, threshold);
  });
};

/* -------------------------------------------------------------- simulator */
/* A line-by-line port of simulate_attempt / simulate_visit in
   data/generate_aadhaar_auth_dataset.py. Same assumptions, same order of checks. */

let SIM = null;   // settings exported from Python (simulator.json)
let simProfile = null;

/** Random number from a normal distribution (Box-Muller method). */
function randomNormal(mean, sd) {
  const u = 1 - Math.random();
  const v = Math.random();
  return mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function clip(value, low, high) {
  return Math.min(high, Math.max(low, value));
}

function roundTo(value, places) {
  const factor = Math.pow(10, places);
  return Math.round(value * factor) / factor;
}

function expectedFingerprintQuality(profile, a) {
  let quality = a.fingerprint_base_quality;
  quality += a.occupation_quality_effect[profile.occupation];
  quality += a.device_quality_effect[profile.device_quality];
  quality += a.environment_quality_effect[profile.environment];
  quality -= Math.max(0, profile.age - a.age_decline_starts_at) * a.age_decline_per_year;
  return quality;
}

function simulateAttempt(profile, visitOffset, attemptNo, a) {
  let quality;
  if (profile.auth_method === "Iris") {
    quality = randomNormal(a.iris_quality_mean, a.iris_quality_sd);
  } else {
    quality = expectedFingerprintQuality(profile, a) + visitOffset
      + a.retry_quality_gain * (attemptNo - 1)
      + randomNormal(0, a.attempt_noise_sd);
  }
  quality = roundTo(clip(quality, 0, 100), 1);
  const result = { attempt_no: attemptNo, biometric_quality: quality, match_score: null };

  // Infrastructure failures first: no match score is produced.
  if (Math.random() < a.network_timeout_probability[profile.network]) {
    result.outcome = "Failure"; result.failure_reason = "Network timeout"; return result;
  }
  if (Math.random() < a.device_error_probability[profile.device_quality]) {
    result.outcome = "Failure"; result.failure_reason = "Device error"; return result;
  }
  // Biometric comparison.
  const score = a.match_intercept + a.match_slope_per_quality_point * quality
    + randomNormal(0, a.match_noise_sd);
  result.match_score = roundTo(clip(score, 0, 1), 3);
  if (quality < a.min_capture_quality) {
    result.outcome = "Failure"; result.failure_reason = "Poor quality capture";
  } else if (result.match_score < a.match_threshold) {
    result.outcome = "Failure"; result.failure_reason = "Biometric mismatch";
  } else {
    result.outcome = "Success"; result.failure_reason = "No failure";
  }
  return result;
}

/** One visit by a random person with this profile: up to 3 attempts. */
function simulateVisit(profile, a) {
  const personOffset = randomNormal(0, a.person_noise_sd);
  const visitOffset = personOffset + randomNormal(0, a.visit_noise_sd);
  const attempts = [];
  for (let attemptNo = 1; attemptNo <= a.max_attempts_per_visit; attemptNo++) {
    const attempt = simulateAttempt(profile, visitOffset, attemptNo, a);
    attempts.push(attempt);
    if (attempt.outcome === "Success") { break; }
  }
  return attempts;
}

function visitWasDenied(attempts) {
  return attempts.every(function (attempt) { return attempt.outcome === "Failure"; });
}

function estimateDenialProbability(profile, runs, a) {
  let denied = 0;
  for (let i = 0; i < runs; i++) {
    if (visitWasDenied(simulateVisit(profile, a))) { denied += 1; }
  }
  return denied / runs;
}

function simulateProfile(profile) {
  const a = SIM.assumptions;
  const attempts = simulateVisit(profile, a);
  const denied = visitWasDenied(attempts);
  return {
    profile: profile, attempts: attempts, denied: denied,
    finalMessage: denied ? "Service denied" : "Ration received",
    denialProbability: estimateDenialProbability(profile, SIM.runs, a),
  };
}

function formatPct(value) { return (value * 100).toFixed(1) + "%"; }

function visitPanelHtml(result, heading) {
  const a = SIM.assumptions;
  const p = result.profile;
  let html = '<section class="card"><h2>' + escapeHtml(heading) + "</h2>";
  html += '<p class="profile-list">Age ' + p.age + " · " + escapeHtml(p.occupation) + " · " + escapeHtml(p.area_type)
    + " · " + escapeHtml(p.device_quality) + " device · " + escapeHtml(p.network) + " network · "
    + escapeHtml(p.environment) + " · " + escapeHtml(p.auth_method) + "</p>";

  result.attempts.forEach(function (attempt, index) {
    const delay = (index * 0.9).toFixed(1) + "s";
    const success = attempt.outcome === "Success";
    html += '<div class="attempt ' + (success ? "success" : "failure") + '" style="animation-delay:' + delay + '">';
    html += '<div class="attempt-head"><span>Attempt ' + attempt.attempt_no + "</span><span>"
      + (success ? '<span class="tag pass">SUCCESS</span>'
        : '<span class="tag fail">FAILED: ' + escapeHtml(attempt.failure_reason) + "</span>")
      + "</span></div>";
    html += '<div class="meter-label"><span>Capture quality: <strong>' + attempt.biometric_quality.toFixed(1)
      + "</strong> / 100</span><span>minimum " + a.min_capture_quality + "</span></div>";
    html += '<div class="meter"><div class="fill ' + (attempt.biometric_quality >= a.min_capture_quality ? "ok" : "low")
      + '" style="width:' + attempt.biometric_quality + "%;animation-delay:" + delay + '"></div>'
      + '<div class="marker" style="left:' + a.min_capture_quality + '%" title="Minimum capture quality"></div></div>';
    if (attempt.match_score === null) {
      html += '<div class="meter-label"><span>Match score: <strong>not computed</strong>, the attempt stopped at '
        + (attempt.failure_reason === "Network timeout" ? "the network" : "the device") + ".</span></div>";
    } else {
      html += '<div class="meter-label"><span>Match score: <strong>' + attempt.match_score.toFixed(3)
        + "</strong></span><span>threshold " + a.match_threshold.toFixed(2) + "</span></div>";
      html += '<div class="meter"><div class="fill ' + (attempt.match_score >= a.match_threshold ? "ok" : "low")
        + '" style="width:' + (attempt.match_score * 100) + "%;animation-delay:" + delay + '"></div>'
        + '<div class="marker" style="left:' + (a.match_threshold * 100) + '%" title="Match threshold"></div></div>';
    }
    html += "</div>";
  });

  html += '<div class="final ' + (result.denied ? "denied" : "received") + '" style="animation-delay:'
    + (result.attempts.length * 0.9).toFixed(1) + 's">' + result.finalMessage + "</div>";
  html += '<p class="probability">Estimated denial probability over ' + SIM.runs.toLocaleString()
    + " simulated visits: <b>" + formatPct(result.denialProbability) + "</b></p></section>";
  return html;
}

function simulatorFormHtml(profile) {
  const fields = [["occupation", "Occupation"], ["area_type", "Area type"], ["device_quality", "Device quality"],
    ["network", "Network"], ["environment", "Environment"], ["auth_method", "Authentication method"]];
  const c = SIM.comparison_profile;
  let html = '<section class="page-header"><h1>Authentication Simulator</h1>'
    + "<p>Pick a profile and simulate one visit to a ration shop. The simulator uses <strong>the same rules as the data "
    + "generator</strong>: quality depends on age, occupation, device and environment; a network or device can fail first; "
    + "the match score must clear the threshold; up to three attempts are allowed. "
    + "No Aadhaar number or real biometric is ever requested.</p></section>";
  html += '<section class="card"><form id="sim-form"><div class="sim-form">';
  html += '<label for="sim-age">Age<input id="sim-age" type="number" name="age" min="' + SIM.min_age + '" max="'
    + SIM.max_age + '" value="' + profile.age + '" required></label>';
  fields.forEach(function (field) {
    const name = field[0];
    html += '<label for="sim-' + name + '">' + field[1] + '<select id="sim-' + name + '" name="' + name + '">';
    SIM.form_options[name].forEach(function (option) {
      html += '<option value="' + escapeHtml(option) + '"' + (profile[name] === option ? " selected" : "") + ">"
        + escapeHtml(option) + "</option>";
    });
    html += "</select></label>";
  });
  html += '</div><div class="sim-actions">'
    + '<button class="btn" type="submit" value="single">Simulate visit</button>'
    + '<button class="btn accent" type="submit" value="compare">Compare with a young office worker</button></div>'
    + '<p class="caption">Area type has no direct effect in the model: it changes outcomes only by making low-quality devices '
    + "and poor networks more likely. Here you choose the device and network directly. The comparison person is age "
    + c.age + ", " + escapeHtml(c.occupation) + ", " + escapeHtml(c.area_type) + ", " + escapeHtml(c.device_quality)
    + " device, " + escapeHtml(c.network) + " network, " + escapeHtml(c.environment) + " conditions.</p></form></section>";
  html += '<div id="sim-results"></div>';
  return html;
}

/** Read the form safely: anything unexpected falls back to the default profile. */
function readSimulatorForm(form) {
  const profile = Object.assign({}, SIM.default_profile);
  const age = parseInt(form.elements.age.value, 10);
  if (!Number.isNaN(age)) { profile.age = clip(age, SIM.min_age, SIM.max_age); }
  Object.keys(SIM.form_options).forEach(function (name) {
    const value = form.elements[name].value;
    if (SIM.form_options[name].includes(value)) { profile[name] = value; }
  });
  return profile;
}

function runSimulation(profile, compare) {
  const results = document.getElementById("sim-results");
  const mine = simulateProfile(profile);
  if (!compare) {
    results.innerHTML = visitPanelHtml(mine, "Simulated visit");
    return;
  }
  const other = simulateProfile(SIM.comparison_profile);
  let sentence;
  if (other.denialProbability > 0) {
    sentence = "Your profile is denied in " + formatPct(mine.denialProbability) + " of simulated visits, which is "
      + (mine.denialProbability / other.denialProbability).toFixed(1) + " times the comparison person's "
      + formatPct(other.denialProbability) + ".";
  } else {
    sentence = "Your profile is denied in " + formatPct(mine.denialProbability)
      + " of simulated visits; the comparison person was denied in " + formatPct(other.denialProbability)
      + " of " + SIM.runs.toLocaleString() + " visits.";
  }
  results.innerHTML = '<div class="grid grid-2">' + visitPanelHtml(mine, "Your profile")
    + visitPanelHtml(other, "Comparison: young office worker") + '</div><p class="sentence">' + sentence + "</p>";
}

async function showSimulator() {
  SIM = await loadJson("simulator.json");
  if (!simProfile) { simProfile = Object.assign({}, SIM.default_profile); }
  VIEW.innerHTML = simulatorFormHtml(simProfile);
  const form = document.getElementById("sim-form");
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    simProfile = readSimulatorForm(form);
    const button = event.submitter;
    runSimulation(simProfile, button && button.value === "compare");
  });
  // Open in a working state: the example profile compared with the office worker.
  runSimulation(simProfile, true);
}

/* ---------------------------------------------------------- data explorer */

const EXPLORER_FILTERS = [
  ["state", "State"], ["area_type", "Area type"], ["age_group", "Age group"], ["occupation", "Occupation"],
  ["service_type", "Service"], ["auth_method", "Authentication method"], ["outcome", "Outcome"],
  ["failure_reason", "Failure reason"],
];
const EXPLORER_PAGE_SIZE = 25;
const NUMERIC_COLUMNS = ["age", "biometric_quality", "match_score", "threshold", "attempt_no"];
let explorerChoices = {};
let explorerPage = 1;
let downloadsApi = null;

function explorerRows(data) {
  return data.rows.filter(function (row) {
    return EXPLORER_FILTERS.every(function (item) {
      const chosen = explorerChoices[item[0]];
      return !chosen || row[item[0]] === chosen;
    });
  });
}

function uniqueSorted(rows, column) {
  return Array.from(new Set(rows.map(function (row) { return row[column]; }))).sort();
}

async function showExplorer() {
  VIEW.innerHTML = '<div class="loading">Loading the dataset…</div>';
  const data = await loadAttempts();
  let html = '<section class="page-header"><h1>Data Explorer</h1>'
    + "<p>Browse the raw synthetic log: one row per authentication attempt. Use the filters, then save exactly what you see.</p></section>";
  html += '<form class="filter-bar" id="explorer-form">';
  EXPLORER_FILTERS.forEach(function (item) {
    const column = item[0];
    html += '<label for="ex-' + column + '">' + item[1] + '<select id="ex-' + column + '" name="' + column
      + '"><option value="">All</option>';
    uniqueSorted(data.rows, column).forEach(function (choice) {
      html += '<option value="' + escapeHtml(choice) + '"' + (explorerChoices[column] === choice ? " selected" : "")
        + ">" + escapeHtml(choice) + "</option>";
    });
    html += "</select></label>";
  });
  html += '<button class="btn secondary" type="button" id="explorer-reset">Reset</button>'
    + '<button class="btn accent" type="button" id="explorer-save" hidden>Download filtered CSV</button>'
    + '<span class="save-status" id="explorer-save-status"></span></form>';
  html += '<section class="card" id="explorer-table"></section>';
  VIEW.innerHTML = html;

  const form = document.getElementById("explorer-form");
  form.addEventListener("change", function () {
    EXPLORER_FILTERS.forEach(function (item) { explorerChoices[item[0]] = form.elements[item[0]].value; });
    explorerPage = 1;
    drawExplorerTable(data);
  });
  document.getElementById("explorer-reset").addEventListener("click", function () {
    explorerChoices = {};
    explorerPage = 1;
    showExplorer();
  });
  setUpDownload(data);
  drawExplorerTable(data);
}

function drawExplorerTable(data) {
  const rows = explorerRows(data);
  const totalPages = Math.max(1, Math.ceil(rows.length / EXPLORER_PAGE_SIZE));
  explorerPage = clip(explorerPage, 1, totalPages);
  const start = (explorerPage - 1) * EXPLORER_PAGE_SIZE;
  const pageRows = rows.slice(start, start + EXPLORER_PAGE_SIZE);
  const box = document.getElementById("explorer-table");

  let html = '<p class="explorer-count"><span><strong>' + rows.length.toLocaleString()
    + "</strong> matching attempts</span><span>page " + explorerPage + " of " + totalPages + "</span></p>";
  if (pageRows.length === 0) {
    box.innerHTML = html + '<div class="empty-state">No data for this filter</div>';
    return;
  }
  html += '<div class="table-wrap"><table><thead><tr>';
  data.header.forEach(function (column) { html += "<th>" + escapeHtml(column) + "</th>"; });
  html += "</tr></thead><tbody>";
  pageRows.forEach(function (row) {
    html += "<tr>";
    data.header.forEach(function (column) {
      const value = row[column] === "" ? "—" : row[column];
      html += '<td class="' + (NUMERIC_COLUMNS.includes(column) ? "num" : "") + '">' + escapeHtml(value) + "</td>";
    });
    html += "</tr>";
  });
  html += '</tbody></table></div><div class="pager">'
    + '<button class="btn secondary" type="button" id="explorer-prev"' + (explorerPage <= 1 ? " disabled" : "") + ">← Previous</button>"
    + "<span>Page " + explorerPage + " of " + totalPages + "</span>"
    + '<button class="btn secondary" type="button" id="explorer-next"' + (explorerPage >= totalPages ? " disabled" : "") + ">Next →</button></div>";
  box.innerHTML = html;
  document.getElementById("explorer-prev").addEventListener("click", function () { explorerPage -= 1; drawExplorerTable(data); });
  document.getElementById("explorer-next").addEventListener("click", function () { explorerPage += 1; drawExplorerTable(data); });
}

/** The "Download filtered CSV" button uses the viewer's downloads capability. */
async function setUpDownload(data) {
  const button = document.getElementById("explorer-save");
  const status = document.getElementById("explorer-save-status");
  if (!downloadsApi && window.claude && window.claude.use) {
    downloadsApi = await window.claude.use("downloads");
  }
  if (!downloadsApi || !button) { return; }   // not available here: keep the button hidden
  button.hidden = false;
  button.addEventListener("click", async function () {
    const rows = explorerRows(data);
    if (rows.length === 0) { status.textContent = "No rows to save for this filter."; return; }
    const lines = [data.header.join(",")];
    rows.forEach(function (row) {
      lines.push(data.header.map(function (column) { return row[column]; }).join(","));
    });
    try {
      await downloadsApi.save({ filename: "filtered_attempts.csv", data: lines.join("\n") + "\n" });
      status.textContent = "Saved " + rows.length.toLocaleString() + " rows.";
    } catch (error) {
      if (error && error.code === "declined") {
        status.textContent = "Download cancelled.";
      } else if (error && error.code === "rate_limited") {
        status.textContent = "A save is already waiting for your answer.";
      } else {
        status.textContent = "Saving files is not available here.";
        button.hidden = true;
      }
    }
  });
}

/* ------------------------------------------------------------------ start */
showRoute(routeFromHash());
