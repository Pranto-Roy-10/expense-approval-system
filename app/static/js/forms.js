// Form behaviour, clickable rows and the receipt viewer. Works without GSAP.
(function () {
  "use strict";

  var animate = function (el) {
    if (window.gsap && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      gsap.from(el, { y: 16, autoAlpha: 0, duration: 0.4, ease: "power2.out", clearProps: "all" });
    }
  };

  // ---------- Sign-up: the manager field only applies to employees ----------
  var signup = document.querySelector("[data-signup]");
  if (signup) {
    var managerField = signup.querySelector("[data-manager-field]");
    var syncRole = function () {
      var role = signup.querySelector("input[name=role]:checked");
      managerField.hidden = !role || role.value !== "employee";
    };
    signup.addEventListener("change", syncRole);
    syncRole();
  }

  // ---------- Claim form: add/remove lines, live total, meal note hint ----------
  var form = document.querySelector("[data-claim-form]");
  if (form) {
    var lines = form.querySelector("[data-lines]");
    var template = form.querySelector("[data-line-template]");
    var rates = JSON.parse(form.dataset.rates);
    var totalEl = form.querySelector("[data-total]");
    var nextKey = 0;

    var base = function (line) {
      var amount = parseFloat(line.querySelector("[data-amount]").value);
      var rate = parseFloat(rates[line.querySelector("[data-currency]").value]);
      return isFinite(amount) && amount > 0 ? amount * rate : 0;
    };
    var set = function (sel, text) { var el = form.querySelector(sel); if (el) el.textContent = text; };
    var check = function (key, ok) { var el = form.querySelector('[data-check="' + key + '"]'); if (el) el.classList.toggle("is-ok", ok); };
    var refresh = function () {
      var total = 0, receipts = 0, complete = true, notesOk = true, mealsNeedingNote = 0;
      var all = lines.querySelectorAll("[data-line]");
      all.forEach(function (line, i) {
        line.querySelector("[data-line-number]").textContent = i + 1;
        var value = base(line);
        total += value;
        var needsNote = line.querySelector("[data-category]").value === "Meals" && value > 50;
        var flag = line.querySelector("[data-note-flag]");
        flag.textContent = needsNote ? "Required for meals over ৳50" : "Optional";
        flag.classList.toggle("is-required", needsNote);
        var note = line.querySelector("[data-note]");
        note.required = needsNote;
        if (needsNote) mealsNeedingNote++;
        if (needsNote && !note.value.trim()) notesOk = false;
        // a receipt counts if one is kept on file or a new file is chosen
        var kept = line.querySelector("[data-receipt-current]") && !line.querySelector("[data-remove-receipt]").checked;
        if (kept || line.querySelector("[data-file]").files.length) receipts++;
        ["input[type=date]", "[data-category]", "[data-amount]", "input[name$='-description']"].forEach(function (sel) {
          if (!line.querySelector(sel).value.trim()) complete = false;
        });
        if (!value) complete = false;
      });
      totalEl.textContent = total.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      set("[data-sum-items]", all.length);
      set("[data-items-plural]", all.length === 1 ? "" : "s");
      set("[data-sum-lines]", all.length);
      set("[data-sum-receipts]", receipts);
      set("[data-finance]", total > 1000 ? "Required, over ৳1,000" : "Not needed");
      check("title", !!form.querySelector("#title").value.trim());
      check("lines", complete);
      check("receipts", receipts === all.length);
      // only a pass when there is something to pass; with no meals over ৳50 the rule simply doesn't apply
      check("notes", mealsNeedingNote > 0 && notesOk);
      var notes = form.querySelector('[data-check="notes"]');
      if (notes) notes.classList.toggle("is-na", mealsNeedingNote === 0);
    };
    form.querySelector("#title").addEventListener("input", refresh);
    // Show that a save is under way; stop double submits.
    form.addEventListener("submit", function (e) {
      var used = e.submitter;
      form.querySelectorAll("button[type=submit]").forEach(function (b) {
        if (b === used && b.dataset.busy) {
          // keep the clicked button's name/value in the request after disabling it
          var keep = document.createElement("input");
          keep.type = "hidden"; keep.name = b.name; keep.value = b.value;
          form.appendChild(keep);
          b.dataset.label = b.textContent;
          b.textContent = b.dataset.busy;
        }
        b.disabled = true;
      });
    });
    window.addEventListener("pageshow", function (e) {
      if (!e.persisted) return; // back button restored the page: undo the busy state
      form.querySelectorAll("button[type=submit]").forEach(function (b) { b.disabled = false; if (b.dataset.label) b.textContent = b.dataset.label; });
      form.querySelectorAll("input[type=hidden][name=action]").forEach(function (i) { i.remove(); });
    });
    var formError = document.querySelector("[data-form-error]");
    if (formError) formError.focus();

    form.querySelector("[data-add-line]").addEventListener("click", function () {
      var html = template.innerHTML.replace(/__KEY__/g, "n" + Date.now() + "_" + nextKey++);
      lines.insertAdjacentHTML("beforeend", html);
      var line = lines.lastElementChild;
      line.querySelector("input[type=date]").valueAsDate = new Date();
      refresh();
      animate(line);
      line.querySelector("[data-category]").focus();
    });
    lines.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-remove-line]");
      if (!btn || lines.children.length < 2) return;
      btn.closest("[data-line]").remove();
      refresh();
    });
    lines.addEventListener("input", refresh);
    lines.addEventListener("change", function (e) {
      if (e.target.matches("[data-file]")) {
        var label = e.target.parentNode.querySelector("[data-file-label]");
        label.textContent = e.target.files.length ? e.target.files[0].name : "Upload receipt";
      }
      refresh();
    });
    refresh();
  }

  // ---------- Table rows open their claim ----------
  document.querySelectorAll("tr.is-link").forEach(function (row) {
    var link = row.querySelector("a");
    row.addEventListener("click", function (e) {
      if (!e.target.closest("a, button") && !window.getSelection().toString()) link.click();
    });
  });

  // ---------- Confirmations and required comments ----------
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!confirm(f.dataset.confirm)) e.preventDefault();
    });
  });
  document.querySelectorAll("[data-needs-comment]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      var comment = btn.form.querySelector("textarea[name=comment]");
      if (!comment.value.trim()) {
        e.preventDefault();
        comment.setAttribute("aria-invalid", "true");
        comment.placeholder = "Add a comment so the employee knows what to fix";
        comment.focus();
      }
    });
  });

  // ---------- Receipt viewer ----------
  var viewer = document.querySelector("[data-viewer]");
  if (viewer) {
    var body = viewer.querySelector("[data-viewer-body]");
    var close = function () { viewer.close(); };
    document.querySelectorAll("[data-receipt]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var src = btn.dataset.src;
        viewer.querySelector("[data-viewer-name]").textContent = btn.dataset.name;
        viewer.querySelector("[data-viewer-open]").href = src;
        body.textContent = "";
        var el;
        if (btn.dataset.kind === "pdf") {
          el = document.createElement("iframe");
          el.title = btn.dataset.name;
        } else {
          el = document.createElement("img");
          el.alt = "Receipt " + btn.dataset.name;
        }
        el.src = src;
        body.appendChild(el);
        viewer.showModal();
        if (window.gsap && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
          gsap.fromTo(viewer, { y: 24, scale: 0.97, autoAlpha: 0 }, { y: 0, scale: 1, autoAlpha: 1, duration: 0.35, ease: "power3.out", clearProps: "transform" });
        }
      });
    });
    viewer.querySelector("[data-viewer-close]").addEventListener("click", close);
    viewer.addEventListener("click", function (e) { if (e.target === viewer) close(); }); // backdrop click
    viewer.addEventListener("close", function () { body.textContent = ""; });
  }

  // ---- Status tabs over a claims table: each tab lists the statuses it shows ----
  var tabs = document.querySelector("[data-tabs]");
  if (tabs) {
    var tabRows = document.querySelectorAll("[data-tab-table] tbody tr");
    var tabNone = document.querySelector("[data-tab-none]");
    tabs.addEventListener("click", function (e) {
      var tab = e.target.closest("[data-tab]");
      if (!tab) return;
      var wanted = tab.dataset.tab ? tab.dataset.tab.split(" ") : null, shown = 0;
      tabs.querySelectorAll("[data-tab]").forEach(function (t) { t.setAttribute("aria-pressed", String(t === tab)); });
      tabRows.forEach(function (row) {
        row.hidden = wanted !== null && wanted.indexOf(row.dataset.status) === -1;
        if (!row.hidden) shown++;
      });
      tabNone.hidden = shown > 0;
    });
  }
})();
