// Finance overview: Chart.js charts drawn from CSS tokens (so they follow the theme),
// plus the claims ledger's search, filters, sorting and CSV export.
(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("dash-data").textContent);
  var nf = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
  var taka = function (v) { return "৳ " + nf.format(v); };
  var compact = function (v) { return v >= 1000 ? nf.format(v / 1000) + "K" : nf.format(v); };
  var css = function (name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); };
  var charts = [];

  // Value printed on top of each column (used where every value matters, e.g. aging buckets).
  var capLabels = {
    id: "capLabels",
    afterDatasetsDraw: function (chart) {
      if (!chart.options.plugins.capLabels) return;
      var ctx = chart.ctx;
      ctx.save();
      ctx.font = "500 12px " + css("--mono");
      ctx.fillStyle = css("--muted");
      ctx.textAlign = "center";
      chart.getDatasetMeta(0).data.forEach(function (bar, i) {
        var v = chart.data.datasets[0].data[i];
        if (v) ctx.fillText(compact(v), bar.x, bar.y - 8);
      });
      ctx.restore();
    }
  };

  function draw() {
    if (!window.Chart) return; // CDN blocked: the legends and tables still carry every number
    charts.forEach(function (c) { c.destroy(); });
    var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    var muted = css("--muted"), grid = css("--border"), surface = css("--surface");
    Chart.defaults.font.family = css("--font");
    Chart.defaults.font.size = 12;
    Chart.defaults.color = muted;
    var tooltip = {
      backgroundColor: surface, borderColor: css("--border-strong"), borderWidth: 1, padding: 10, cornerRadius: 8,
      titleColor: css("--text"), bodyColor: css("--text"), footerColor: css("--text"),
      titleFont: { weight: "600" }, footerFont: { weight: "600" }, boxPadding: 4, usePointStyle: true
    };
    var axes = function (stacked) {
      return {
        x: { stacked: stacked, grid: { display: false }, border: { color: css("--border-strong") }, ticks: { color: muted } },
        y: { stacked: stacked, beginAtZero: true, grid: { color: grid }, border: { display: false },
             ticks: { color: muted, maxTicksLimit: 5, callback: compact } }
      };
    };

    // Stacked columns: one dataset per category, colour fixed to the category (never its rank).
    var sets = data.stacked;
    var isTop = function (di, i) { // round only the top end of each column
      for (var k = di + 1; k < sets.length; k++) if (sets[k].data[i]) return false;
      return true;
    };
    charts.push(new Chart(document.getElementById("spend-chart"), {
      type: "bar",
      data: {
        labels: data.months,
        datasets: sets.map(function (s, di) {
          return {
            label: s.label, data: s.data, backgroundColor: css("--s" + s.slot),
            borderColor: surface, borderWidth: { top: 2 }, borderSkipped: "bottom", maxBarThickness: 28,
            borderRadius: function (ctx) { return isTop(di, ctx.dataIndex) ? { topLeft: 4, topRight: 4 } : 0; }
          };
        })
      },
      options: {
        maintainAspectRatio: false, animation: reduce ? false : { duration: 700, easing: "easeOutQuart" },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false }, // HTML legend above the chart
          tooltip: Object.assign({}, tooltip, {
            filter: function (item) { return item.parsed.y > 0; },
            itemSort: function (a, b) { return b.datasetIndex - a.datasetIndex; },
            callbacks: {
              label: function (c) { return " " + c.dataset.label + ": " + taka(c.parsed.y); },
              footer: function (items) { return "Total: " + taka(items.reduce(function (t, i) { return t + i.parsed.y; }, 0)); }
            }
          })
        },
        scales: axes(true)
      }
    }));

    // Aging: one ordered measure, so an ordinal ramp of one hue (older = darker / stronger).
    charts.push(new Chart(document.getElementById("aging-chart"), {
      type: "bar",
      data: {
        labels: data.aging.map(function (a) { return a.label.replace(" days", "d").replace("Over 30d", "30d+"); }),
        datasets: [{ data: data.aging.map(function (a) { return a.total; }), maxBarThickness: 28, borderRadius: { topLeft: 4, topRight: 4 },
          borderSkipped: "bottom", backgroundColor: data.aging.map(function (_, i) { return css("--o" + i); }) }]
      },
      options: {
        maintainAspectRatio: false, animation: reduce ? false : { duration: 700 },
        layout: { padding: { top: 22 } },
        plugins: {
          legend: { display: false }, capLabels: true,
          tooltip: Object.assign({}, tooltip, { callbacks: {
            title: function (items) { return data.aging[items[0].dataIndex].label; },
            label: function (c) { var a = data.aging[c.dataIndex]; return " " + taka(a.total) + " · " + a.count + " claim" + (a.count === 1 ? "" : "s"); }
          } })
        },
        scales: axes(false)
      },
      plugins: [capLabels]
    }));
  }

  window.addEventListener("load", draw);
  new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // ---- Claims ledger ----
  var table = document.querySelector("[data-sortable]");
  if (!table) return;
  var body = table.tBodies[0];
  var rows = Array.prototype.slice.call(body.rows);
  var filters = document.querySelectorAll("[data-filter]");
  var search = document.querySelector("[data-search]");
  var count = document.querySelector("[data-table-count]");
  var total = document.querySelector("[data-table-total]");
  var none = document.querySelector("[data-table-none]");

  function apply() {
    var q = search.value.trim().toLowerCase(), shown = 0, sum = 0;
    rows.forEach(function (row) {
      var ok = (!q || row.dataset.text.indexOf(q) !== -1) &&
        Array.prototype.every.call(filters, function (f) { return !f.value || row.dataset[f.dataset.filter] === f.value; });
      row.hidden = !ok;
      if (ok) { shown++; sum += parseFloat(row.dataset.total); }
    });
    count.textContent = shown;
    total.textContent = nf.format(sum);
    none.hidden = shown > 0;
  }
  filters.forEach(function (f) { f.addEventListener("change", apply); });
  search.addEventListener("input", apply);

  table.querySelectorAll("[data-sort]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var th = btn.parentElement, key = btn.dataset.sort;
      var dir = th.getAttribute("aria-sort") === "descending" ? "ascending" : "descending";
      table.querySelectorAll("th[aria-sort]").forEach(function (h) { h.setAttribute("aria-sort", "none"); });
      th.setAttribute("aria-sort", dir);
      var numeric = key === "total" || key === "code";
      rows.sort(function (a, b) {
        var x = a.dataset[key], y = b.dataset[key];
        var cmp = numeric ? parseFloat(x) - parseFloat(y) : x.localeCompare(y);
        return dir === "ascending" ? cmp : -cmp;
      });
      rows.forEach(function (row) { body.appendChild(row); });
    });
  });

  // Approved-claims menu: close on outside click, Escape, or after picking a format.
  var menu = document.querySelector("[data-menu]");
  document.addEventListener("click", function (e) { if (menu.open && !menu.contains(e.target)) menu.open = false; });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
  });
  menu.querySelectorAll("a").forEach(function (a) { a.addEventListener("click", function () { menu.open = false; }); });

  // Download a branded Excel file of exactly what the filters show, in the current sort order.
  var exportBtn = document.querySelector("[data-export]");
  exportBtn.addEventListener("click", function () {
    var params = new URLSearchParams();
    var narrowed = search.value.trim() || Array.prototype.some.call(filters, function (f) { return f.value; });
    // a capped ledger without filters means "everything": let the server export every claim, not just the rows shown
    if (narrowed || !exportBtn.hasAttribute("data-capped")) {
      params.set("ids", rows.filter(function (row) { return !row.hidden; }).map(function (row) { return row.dataset.code; }).join(","));
    }
    filters.forEach(function (f) { if (f.value) params.set(f.dataset.filter, f.value); });
    if (search.value.trim()) params.set("q", search.value.trim());
    window.location.href = exportBtn.dataset.export + "?" + params.toString();
  });
})();
