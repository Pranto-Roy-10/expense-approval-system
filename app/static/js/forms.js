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
    // the policy limits come from the server (rules.py), so the live hints always match what is enforced
    var threshold = parseFloat(form.dataset.threshold), mealLimit = parseFloat(form.dataset.mealLimit.replace(/,/g, ""));
    var taka = function (v) { return v.toLocaleString("en-IN"); };
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
        var needsNote = line.querySelector("[data-category]").value === "Meals" && value > mealLimit;
        var flag = line.querySelector("[data-note-flag]");
        flag.textContent = needsNote ? "Required for meals over ৳" + taka(mealLimit) : "Optional";
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
      set("[data-finance]", total > threshold ? "Required, over ৳" + taka(threshold) : "Not needed");
      check("title", !!form.querySelector("#title").value.trim());
      check("lines", complete);
      check("receipts", receipts === all.length);
      // only a pass when there is something to pass; with no meals over the limit the rule simply doesn't apply
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
  // A form with data-confirm opens the themed dialog in base.html first; it is sent only after "Confirm".
  var ask = document.querySelector("[data-confirm-dialog]");
  if (ask) {
    var pending = null;
    var okBtn = ask.querySelector("[data-confirm-ok]");
    var field = function (name) { return ask.querySelector("[data-confirm-" + name + "]"); };
    var finish = function (value) { // play the exit animation, then close
      if (!ask.open || ask.classList.contains("is-closing")) return;
      ask.classList.add("is-closing");
      var closed = false;
      var done = function () { if (closed) return; closed = true; ask.classList.remove("is-closing"); ask.close(value); };
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return done();
      ask.addEventListener("animationend", done, { once: true });
      setTimeout(done, 300); // backup for browsers that skip the animation (hidden tab, power saving)
    };
    document.querySelectorAll("form[data-confirm]").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        if (f.dataset.confirmed) return;
        e.preventDefault();
        pending = f;
        var d = f.dataset;
        field("title").textContent = d.confirmTitle || "Are you sure?";
        field("text").textContent = d.confirm;
        okBtn.textContent = d.confirmOk || "Confirm";
        ask.classList.toggle("is-danger", d.confirmTone === "danger");
        field("details").hidden = !d.confirmEmployee;
        ["employee", "claim", "amount"].forEach(function (k) {
          field(k).textContent = d["confirm" + k.charAt(0).toUpperCase() + k.slice(1)] || "";
        });
        ask.returnValue = "";
        ask.showModal();
      });
    });
    ask.addEventListener("click", function (e) {
      var btn = e.target.closest("button[value]");
      if (btn) { e.preventDefault(); finish(btn.value); }
      else if (e.target === ask) finish("cancel"); // backdrop
    });
    ask.addEventListener("cancel", function (e) { e.preventDefault(); finish("cancel"); }); // Escape key
    ask.addEventListener("close", function () {
      var f = pending; pending = null;
      if (f && ask.returnValue === "ok") { f.dataset.confirmed = "1"; f.requestSubmit(); }
    });
    window.addEventListener("pageshow", function (e) { // back button: ask again next time
      if (e.persisted) document.querySelectorAll("form[data-confirmed]").forEach(function (f) { delete f.dataset.confirmed; });
    });
  }
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

  // One click per action: approve, reject, pay, submit and delete buttons lock once their form is sent.
  // The claim form and the role picker have their own busy states.
  document.querySelectorAll('form[method="post"]:not([data-claim-form]):not([data-role-form])').forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (e.defaultPrevented) return; // a confirm or required comment stopped it
      setTimeout(function () { f.querySelectorAll("button[type=submit], button:not([type])").forEach(function (b) { b.disabled = true; }); }, 0);
    });
  });
  window.addEventListener("pageshow", function (e) {
    if (e.persisted) document.querySelectorAll('form[method="post"] button:disabled').forEach(function (b) { b.disabled = false; });
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
