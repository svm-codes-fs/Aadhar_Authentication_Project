/* =========================================================================
   Small, reusable Chart.js helpers. Each page passes data computed in Python
   (never hard-coded numbers) and calls one of these functions.
   All rates arrive as fractions (0.123) and are shown as percentages (12.3%).
   ========================================================================= */

// One palette for every chart. Teal and orange are the same in both themes;
// the neutral colours are read from style.css so charts follow light/dark mode.
const COLORS = {
  navy: "#1F3A5F",      // labels and threshold line (replaced by --heading)
  teal: "#2A8C82",      // success / best group
  orange: "#D9692B",    // failure / worst group
  slate: "#5D6B7E",     // system failures
  grey: "#B7C0CA",      // all other bars
  gridLine: "#E6EAEE",
  text: "#4A5563",
};

/** Read a colour token from style.css, keeping the default if it is missing. */
function cssToken(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** Refresh the neutral chart colours from the current light/dark theme. */
function applyThemeColors() {
  COLORS.navy = cssToken("--heading", COLORS.navy);
  COLORS.slate = cssToken("--chart-slate", COLORS.slate);
  COLORS.grey = cssToken("--chart-grey", COLORS.grey);
  COLORS.gridLine = cssToken("--grey-100", COLORS.gridLine);
  COLORS.text = cssToken("--grey-700", COLORS.text);
  Chart.defaults.color = COLORS.text;
}

Chart.defaults.font.family = "Inter, 'Noto Sans', system-ui, sans-serif";
Chart.defaults.animation.duration = 500;
applyThemeColors();

/** Format a fraction as a percentage with 1 decimal place. */
function pct(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return (value * 100).toFixed(1) + "%";
}

/** Replace a chart canvas with a friendly "no data" message. */
function showEmpty(canvasId, message) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) { return; }
  const box = document.createElement("div");
  box.className = "empty-state";
  box.textContent = message || "No data for this filter";
  canvas.parentElement.replaceWith(box);
}

/** True when a chart has nothing to draw (no labels or every value missing). */
function hasNoData(labels, values) {
  if (!labels || labels.length === 0) { return true; }
  return values.every(function (value) { return value === null; });
}

/**
 * Plugin: writes each bar's value above it, so readers do not need colour
 * or the axis to read the number. `formatter` turns a value into text.
 */
function valueLabels(formatter) {
  return {
    id: "valueLabels",
    afterDatasetsDraw: function (chart) {
      const ctx = chart.ctx;
      ctx.save();
      ctx.font = "600 11px Inter, sans-serif";
      ctx.fillStyle = COLORS.navy;
      ctx.textAlign = "center";
      chart.data.datasets.forEach(function (dataset, datasetIndex) {
        const meta = chart.getDatasetMeta(datasetIndex);
        if (meta.hidden) { return; }
        meta.data.forEach(function (bar, index) {
          const value = dataset.data[index];
          if (value === null || value === undefined) { return; }
          const horizontal = chart.options.indexAxis === "y";
          if (horizontal) {
            ctx.textAlign = "left";
            ctx.fillText(formatter(value), bar.x + 4, bar.y + 4);
          } else {
            ctx.fillText(formatter(value), bar.x, bar.y - 5);
          }
        });
      });
      ctx.restore();
    },
  };
}

/** Standard percentage axis (0% upward). */
function percentAxis(title, suggestedMax) {
  return {
    beginAtZero: true,
    suggestedMax: suggestedMax,
    title: { display: true, text: title, font: { weight: "600" } },
    ticks: { callback: function (value) { return pct(value); } },
    grid: { color: COLORS.gridLine },
  };
}

/** Plain category axis with a title. */
function categoryAxis(title) {
  return {
    title: { display: true, text: title, font: { weight: "600" } },
    grid: { display: false },
  };
}

/**
 * Bar chart for one attribute (e.g. denial rate by age group).
 * The best group is teal, the worst orange, the rest grey. The words
 * "(best)" and "(worst)" are added to the labels so colour is not needed.
 */
function groupBarChart(canvasId, chart, xTitle, yTitle) {
  if (hasNoData(chart.labels, chart.values)) { showEmpty(canvasId); return; }
  const colours = [];
  const labels = [];
  chart.labels.forEach(function (label) {
    if (label === chart.worst) {
      colours.push(COLORS.orange);
      labels.push(label + " (worst)");
    } else if (label === chart.best) {
      colours.push(COLORS.teal);
      labels.push(label + " (best)");
    } else {
      colours.push(COLORS.grey);
      labels.push(label);
    }
  });
  const biggest = Math.max.apply(null, chart.values.filter(function (v) { return v !== null; }));
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{ label: chart.metric, data: chart.values, backgroundColor: colours, borderRadius: 4 }],
    },
    options: {
      maintainAspectRatio: false,
      layout: { padding: { top: 18 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function (item) {
              return chart.metric + ": " + pct(item.raw) + " (n = " + chart.counts[item.dataIndex].toLocaleString() + ")";
            },
          },
        },
      },
      scales: {
        x: categoryAxis(xTitle),
        y: percentAxis(yTitle || chart.metric, biggest * 1.15),
      },
    },
    plugins: [valueLabels(pct)],
  });
}

/** Simple single-colour bar chart for percentages. */
function simpleBarChart(canvasId, labels, values, colour, xTitle, yTitle, counts) {
  if (hasNoData(labels, values)) { showEmpty(canvasId); return; }
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: { labels: labels, datasets: [{ label: yTitle, data: values, backgroundColor: colour, borderRadius: 4 }] },
    options: {
      maintainAspectRatio: false,
      layout: { padding: { top: 18 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function (item) {
              let text = yTitle + ": " + pct(item.raw);
              if (counts) { text += " (n = " + counts[item.dataIndex].toLocaleString() + ")"; }
              return text;
            },
          },
        },
      },
      scales: { x: categoryAxis(xTitle), y: percentAxis(yTitle) },
    },
    plugins: [valueLabels(pct)],
  });
}

/** Stacked bars: biometric failures (orange) on top of system failures (slate). */
function failureFamilyChart(canvasId, rows, xTitle) {
  const labels = rows.map(function (row) { return row.group || row.band; });
  const biometric = rows.map(function (row) { return row.biometric_rate; });
  const system = rows.map(function (row) { return row.system_rate; });
  if (hasNoData(labels, biometric)) { showEmpty(canvasId); return; }
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        { label: "System failure (network / device)", data: system, backgroundColor: COLORS.slate, borderRadius: 2 },
        { label: "Biometric failure (mismatch / poor capture)", data: biometric, backgroundColor: COLORS.orange, borderRadius: 2 },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { label: function (item) { return item.dataset.label + ": " + pct(item.raw); } } },
      },
      scales: {
        x: Object.assign(categoryAxis(xTitle), { stacked: true }),
        y: Object.assign(percentAxis("Genuine attempts failed"), { stacked: true }),
      },
    },
  });
}

/** Scatter of biometric quality vs match score with the threshold drawn. */
function qualityScatter(canvasId, scatter, threshold) {
  if (scatter.genuine.length === 0 && scatter.impostor.length === 0) { showEmpty(canvasId); return; }
  new Chart(document.getElementById(canvasId), {
    type: "scatter",
    data: {
      datasets: [
        { label: "Genuine user", data: scatter.genuine, backgroundColor: "rgba(42,140,130,0.28)", pointRadius: 2, pointStyle: "circle" },
        { label: "Impostor", data: scatter.impostor, backgroundColor: "rgba(217,105,43,0.85)", pointRadius: 3, pointStyle: "triangle" },
        {
          label: "Match threshold (" + threshold.toFixed(2) + ")",
          type: "line",
          data: [{ x: 0, y: threshold }, { x: 100, y: threshold }],
          borderColor: COLORS.navy, borderDash: [6, 4], borderWidth: 2, pointRadius: 0,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { label: function (item) { return "Quality " + item.raw.x.toFixed(1) + ", score " + item.raw.y.toFixed(3); } } },
      },
      scales: {
        x: { min: 0, max: 100, title: { display: true, text: "Biometric quality (0-100)", font: { weight: "600" } }, grid: { color: COLORS.gridLine } },
        y: { min: 0, max: 1, title: { display: true, text: "Match score (0-1)", font: { weight: "600" } }, grid: { color: COLORS.gridLine } },
      },
    },
  });
}

/** Horizontal bars of failure reasons; biometric in orange, system in slate. */
function reasonChart(canvasId, rows) {
  // Two-line labels (reason, then family) so long names are not cut off.
  const labels = rows.map(function (row) { return [row.reason, "(" + row.family + ")"]; });
  const values = rows.map(function (row) { return row.share; });
  if (hasNoData(labels, values)) { showEmpty(canvasId); return; }
  const colours = rows.map(function (row) { return row.family === "Biometric" ? COLORS.orange : COLORS.slate; });
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: { labels: labels, datasets: [{ label: "Share of failures", data: values, backgroundColor: colours, borderRadius: 4 }] },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      layout: { padding: { right: 50 } },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: function (item) { return pct(item.raw) + " of failures (" + rows[item.dataIndex].count.toLocaleString() + " attempts)"; } } },
      },
      scales: {
        x: percentAxis("Share of all failed attempts"),
        y: { title: { display: true, text: "Failure reason", font: { weight: "600" } }, grid: { display: false }, ticks: { autoSkip: false } },
      },
    },
    plugins: [valueLabels(pct)],
  });
}

/** Odds ratios on a log scale: above 1 (orange) raises failure odds, below 1 (teal) lowers them. */
function oddsRatioChart(canvasId, oddsRatios) {
  if (!oddsRatios || oddsRatios.length === 0) { showEmpty(canvasId, "Not enough data to fit the model for this filter"); return; }
  const labels = oddsRatios.map(function (item) { return item.factor + ": " + item.label; });
  const values = oddsRatios.map(function (item) { return item.odds_ratio; });
  const colours = values.map(function (value) { return value >= 1 ? COLORS.orange : COLORS.teal; });
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: { labels: labels, datasets: [{ label: "Odds ratio", data: values, backgroundColor: colours, borderRadius: 3, base: 1 }] },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      layout: { padding: { right: 50 } },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: function (item) { return "Odds ratio: " + item.raw.toFixed(2) + "x"; } } },
      },
      scales: {
        x: {
          type: "logarithmic",
          title: { display: true, text: "Odds ratio of a failed first attempt (log scale, 1 = no effect)", font: { weight: "600" } },
          ticks: { callback: function (value) { return [0.25, 0.5, 1, 2, 4, 8, 16].includes(value) ? value + "x" : ""; } },
          grid: { color: COLORS.gridLine },
        },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
    },
    plugins: [valueLabels(function (value) { return value.toFixed(2) + "x"; })],
  });
}
