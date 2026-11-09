// Animations for the get-started page and the role workspaces.
(function () {
  "use strict";

  var root = document.documentElement;
  var pieces = "[data-intro], [data-cards], [data-intro-tail]";
  if (!window.gsap || !window.ScrollTrigger) {
    root.classList.remove("js"); // CDN failed: show everything statically
    return;
  }
  gsap.registerPlugin(ScrollTrigger);
  if (window.SplitText) gsap.registerPlugin(SplitText);

  var mm = gsap.matchMedia();

  // ---- Sign-in side panel: one claim walks through approval, state by state ----
  var aside = document.querySelector("[data-auth-aside]");
  var AUTH_STATES = [
    // badge text, badge tone, steps done, current step, fill, toast
    ["Submitted", "submitted", 0, -1, 0, null],
    ["In review", "submitted", 0, 0, 0, null],
    ["Awaiting Finance", "submitted", 1, 1, 0.5, ["Approved by manager", "Sent to Finance"]],
    ["Approved", "approved", 2, 2, 1, ["Finance approved", "Over ৳" + (aside ? aside.dataset.limit : "") + ", signed off"]],
    ["Paid", "paid", 3, -1, 1, ["Paid out", (aside ? aside.querySelector("tfoot .num").textContent.replace(/\.00$/, "") : "") + " reimbursed"]],
  ];
  function authState(n) {
    var st = AUTH_STATES[n], badge = aside.querySelector("[data-auth-badge]");
    badge.textContent = st[0];
    badge.className = "badge badge-" + st[1];
    aside.querySelectorAll("[data-auth-step]").forEach(function (li, i) {
      li.className = i < st[2] ? "done" : i === st[3] ? "current" : "";
    });
    if (st[5]) {
      aside.querySelector("[data-auth-toast-title]").textContent = st[5][0];
      aside.querySelector("[data-auth-toast-sub]").textContent = st[5][1];
    }
    return st;
  }

  mm.add("(prefers-reduced-motion: reduce)", function () {
    gsap.set(pieces, { autoAlpha: 1 });
    if (aside) { authState(4); gsap.set("[data-auth-fill]", { scaleX: 1 }); }
  });

  mm.add("(prefers-reduced-motion: no-preference)", function () {
    gsap.set(pieces, { autoAlpha: 1 });
    var CLEAR = "transform,translate,rotate,scale"; // so CSS hover lift (translate) works afterwards
    var cleanups = [];

    // ---- Header: slides down, then its contents settle in ----
    if (document.querySelector(".site-header")) {
      gsap.timeline({ defaults: { ease: "power3.out" } })
        .from(".site-header", { yPercent: -100, duration: 0.6 })
        .from(".nav > *", { autoAlpha: 0, duration: 0.4, stagger: 0.05 }, "-=0.25");
    } else {
      // ---- Sidebar: links slide in one after another ----
      gsap.from("[data-side-item]", { autoAlpha: 0, x: -12, duration: 0.45, stagger: 0.05, ease: "power3.out", clearProps: CLEAR });
    }

    // ---- Page intro: rule draws, heading words rise, underline sweeps, copy follows ----
    var intro = document.querySelector("[data-intro]");
    var split = null;
    if (intro.matches(".ws-head")) {
      // working pages: a quiet fade, no headline theatrics
      gsap.from(intro.children, { autoAlpha: 0, y: 8, duration: 0.4, stagger: 0.06, ease: "power2.out", clearProps: CLEAR });
    } else {
    var h1 = intro.querySelector("h1");
    split = window.SplitText ? SplitText.create(h1, { type: "words", mask: "words" }) : null;
    var eyebrow = intro.querySelector(".eyebrow");
    gsap.timeline({ defaults: { ease: "power3.out" } })
      .from(eyebrow, { autoAlpha: 0, x: -12, duration: 0.35 })
      .fromTo(eyebrow, { "--draw": 0 }, { "--draw": 1, duration: 0.5, ease: "power2.inOut" }, "<")
      .from(split ? split.words : h1, { yPercent: 110, autoAlpha: split ? 1 : 0, duration: 0.6, ease: "expo.out", stagger: 0.03 }, "-=0.2")
      .from(intro.querySelectorAll(".lead, .page-head > .btn"), { y: 12, autoAlpha: 0, duration: 0.45, stagger: 0.06 }, "-=0.45")
      .add(function () { if (split) split.revert(); });
    }

    // ---- Card groups: rise in order (public pages add icon and avatar pops) ----
    gsap.utils.toArray("[data-cards]").forEach(function (group, i) {
      var q = function (sel) { return group.querySelectorAll(sel); };
      var cards = group.matches(".panel") ? [group] : group.children;
      if (document.body.classList.contains("has-shell")) {
        // working pages: one short, quiet reveal; no counters, pops or bounces
        gsap.from(cards, { y: 8, autoAlpha: 0, duration: 0.35, stagger: 0.04, ease: "power1.out",
          delay: Math.min(i, 4) * 0.05, clearProps: CLEAR });
        return;
      }
      var tl = gsap.timeline({
        defaults: { ease: "power2.out" },
        delay: 0.1 + Math.min(i, 3) * 0.06,
        scrollTrigger: { trigger: group, start: "top 92%" }
      });
      tl.from(cards, { y: 24, autoAlpha: 0, duration: 0.5, stagger: 0.07, clearProps: CLEAR });

      if (q(".role-icon").length) tl.from(q(".role-icon"), { scale: 0.5, rotate: -15, duration: 0.55, stagger: 0.1, ease: "back.out(2.2)" }, 0.2);
      if (q(".avatar").length) tl.from(q(".avatar"), { scale: 0, duration: 0.45, stagger: 0.08, ease: "back.out(2.4)" }, 0.3);
      if (q(".role-pick li").length) tl.from(q(".role-pick li"), { autoAlpha: 0, x: -10, duration: 0.4, stagger: 0.04 }, 0.45);
    });

    gsap.from("[data-intro-tail]", { autoAlpha: 0, y: 10, duration: 0.4, delay: 0.45 });

    // Get started: role cards float gently once they've arrived (yPercent, so the pick animation's y is untouched)
    gsap.utils.toArray(".gs-card").forEach(function (card, i) {
      gsap.to(card, { yPercent: -1.6, duration: 1.8 + i * 0.3, delay: 0.9 + i * 0.2, ease: "sine.inOut",
        yoyo: true, repeat: -1, force3D: true, autoRound: false });
    });

    // ---- Role cards: icon nudge on hover; chosen card lifts while the others step back ----
    var picks = gsap.utils.toArray(".role-pick");
    picks.forEach(function (card) {
      var icon = card.querySelector(".role-icon");
      var nudge = function () {
        gsap.fromTo(icon, { rotate: 0 }, { keyframes: [{ rotate: -8, duration: 0.12 }, { rotate: 6, duration: 0.12 }, { rotate: 0, duration: 0.2 }], ease: "power1.inOut" });
      };
      card.addEventListener("pointerenter", nudge);
      cleanups.push(function () { card.removeEventListener("pointerenter", nudge); });
    });
    // Picking a role submits straight away; the button just shows it's working (no held-back exit animation).
    gsap.utils.toArray("[data-role-form]").forEach(function (form) {
      var onSubmit = function () {
        var btn = form.querySelector("button");
        form.closest(".role-pick").classList.add("is-picked");
        btn.dataset.label = btn.innerHTML;
        btn.textContent = "Opening workspace…";
        setTimeout(function () { btn.disabled = true; }, 0); // after the submit has been sent
      };
      form.addEventListener("submit", onSubmit);
      cleanups.push(function () { form.removeEventListener("submit", onSubmit); });
    });
    // returning with the back button restores the page from cache: undo the busy state
    var onShow = function (e) {
      if (!e.persisted) return;
      document.querySelectorAll(".role-pick.is-picked").forEach(function (card) {
        card.classList.remove("is-picked");
        var btn = card.querySelector("button");
        btn.disabled = false;
        if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
      });
    };
    window.addEventListener("pageshow", onShow);
    cleanups.push(function () { window.removeEventListener("pageshow", onShow); });

    if (aside) {
      var fill = aside.querySelector("[data-auth-fill]");
      var toast = aside.querySelector("[data-auth-toast]");
      var rows = aside.querySelectorAll("[data-auth-row]");
      var step = function (n) {
        return function () {
          var st = authState(n);
          gsap.to(fill, { scaleX: st[4], duration: 0.6, ease: "power2.inOut" });
          gsap.fromTo(aside.querySelector("[data-auth-badge]"), { scale: 0.85 }, { scale: 1, duration: 0.35, ease: "back.out(3)" });
          if (st[5]) gsap.fromTo(toast, { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.45, ease: "back.out(1.8)" });
        };
      };
      var loop = gsap.timeline({ repeat: -1, repeatDelay: 0.4, delay: 0.6 });
      loop.call(step(0))
        .set(toast, { autoAlpha: 0 })
        .fromTo(rows, { autoAlpha: 0, x: 16 }, { autoAlpha: 1, x: 0, duration: 0.45, stagger: 0.15, ease: "power2.out" })
        .call(step(1), null, "+=0.5")
        .call(step(2), null, "+=1.3")
        .to(toast, { autoAlpha: 0, y: -8, duration: 0.3 }, "+=1.6")
        .call(step(3))
        .to(toast, { autoAlpha: 0, y: -8, duration: 0.3 }, "+=1.8")
        .call(step(4))
        .to([rows, toast], { autoAlpha: 0, duration: 0.4 }, "+=2.2");
      cleanups.push(function () { loop.kill(); });
    }

    if (document.fonts) document.fonts.ready.then(function () { ScrollTrigger.refresh(); });

    return function () {
      if (split) split.revert();
      cleanups.forEach(function (fn) { fn(); });
    };
  });
})();
