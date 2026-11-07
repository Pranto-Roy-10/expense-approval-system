(function () {
  "use strict";

  var root = document.documentElement;

  // ---------- Theme toggle ----------
  var toggle = document.querySelector("[data-theme-toggle]");
  function syncToggle() {
    var dark = root.dataset.theme === "dark";
    toggle.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    toggle.setAttribute("aria-pressed", String(dark));
  }
  syncToggle();
  toggle.addEventListener("click", function () {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
    syncToggle();
  });

  // ---------- Header border ----------
  var header = document.querySelector(".site-header");
  function onScroll() { header.classList.toggle("is-scrolled", window.scrollY > 8); }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // ---------- Animations ----------
  var heroPieces = "[data-hero], [data-hero-title], [data-hero-point], [data-claim-card], [data-float]";
  if (!window.gsap || !window.ScrollTrigger) {
    root.classList.remove("js"); // CDN failed: show everything statically
    return;
  }
  gsap.registerPlugin(ScrollTrigger);
  if (window.SplitText) gsap.registerPlugin(SplitText);

  // Reading progress line under the header follows scroll position (runs in every mode)
  gsap.to(header, { "--progress": 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: 0.3 } });

  var mm = gsap.matchMedia();

  mm.add("(prefers-reduced-motion: reduce)", function () {
    gsap.set(heroPieces, { autoAlpha: 1 });
  });

  mm.add("(prefers-reduced-motion: no-preference)", function () {
    gsap.set(heroPieces, { autoAlpha: 1 });
    var splits = [];
    var CLEAR = "transform,translate,rotate,scale"; // so CSS hover lift (translate) works afterwards
    var popMark = { "--mark": 1, duration: 0.35, ease: "back.out(3)" };

    // ---- Header: slides down, then brand and links settle in ----
    gsap.timeline({ defaults: { ease: "power3.out" } })
      .from(header, { yPercent: -100, duration: 0.6 })
      .from(".nav .brand, .nav-links li, .theme-toggle, .nav .btn", { autoAlpha: 0, y: -8, duration: 0.4, stagger: 0.05 }, "-=0.25");

    // ---- Hero ----
    var title = document.querySelector("[data-hero-title]");
    var split = window.SplitText ? SplitText.create(title, { type: "words", mask: "words" }) : null;
    var total = document.querySelector("[data-count]");
    var target = parseFloat(total.dataset.count);
    var counter = { v: 0 };

    var tl = gsap.timeline({ defaults: { ease: "power3.out" }, delay: 0.2 });
    tl.from(".hero .eyebrow", { autoAlpha: 0, x: -12, duration: 0.6 })
      .fromTo(".hero .eyebrow", { "--draw": 0 }, { "--draw": 1, duration: 0.6, ease: "power2.inOut" }, "<")
      .from(split ? split.words : title, { yPercent: 110, autoAlpha: split ? 1 : 0, duration: 0.9, ease: "expo.out", stagger: 0.045 }, "-=0.3")
      .fromTo(".mark", { "--hl": 0 }, { "--hl": 1, duration: 0.7, ease: "power2.inOut" }, "-=0.35")
      .from(".hero .lead, .hero-actions", { y: 18, autoAlpha: 0, duration: 0.7, stagger: 0.12 }, "-=0.6")
      .from("[data-hero-point]", { x: -14, autoAlpha: 0, duration: 0.5, stagger: 0.08 }, "-=0.4")
      .fromTo("[data-hero-point] path", { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.45, stagger: 0.08, ease: "power2.out" }, "<0.15")
      .from("[data-claim-card]", {
        y: 60, rotateX: 14, transformPerspective: 1200, transformOrigin: "50% 100%",
        autoAlpha: 0, duration: 1.1, ease: "expo.out"
      }, 0.35)
      .fromTo(".claim-head .badge", { "--mark": 0 }, popMark, 0.9)
      .from("[data-claim-row]", { x: 18, autoAlpha: 0, duration: 0.5, stagger: 0.12 }, 0.75)
      .from(".cat", { scale: 0.7, autoAlpha: 0, duration: 0.35, stagger: 0.12, ease: "back.out(2.5)" }, 0.95)
      .to(counter, {
        v: target, duration: 1.3, ease: "power2.out",
        onUpdate: function () {
          // Taka uses South Asian digit grouping (e.g. 1,23,650.00)
          total.textContent = counter.v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
      }, 0.9)
      .from("[data-step-dot]", { scale: 0, duration: 0.45, stagger: 0.15, ease: "back.out(2.4)" }, 1.2)
      .from("[data-steps-fill]", { scaleX: 0, duration: 0.8, ease: "power2.inOut" }, 1.35)
      .from("[data-float]", { y: 24, scale: 0.85, autoAlpha: 0, duration: 0.7, stagger: 0.25, ease: "back.out(1.7)" }, 1.6)
      .from(".float-icon", { scale: 0, rotate: -30, duration: 0.45, stagger: 0.25, ease: "back.out(2.5)" }, 1.8)
      .add(function () {
        if (split) split.revert(); // restore plain headline text once the underline has finished
        gsap.to("[data-float]", { y: -8, duration: 2.6, ease: "sine.inOut", yoyo: true, repeat: -1, stagger: 0.9 });
      });

    // Pointer tilt on the claim card: desktop layout + mouse only, after the intro,
    // measured over the card itself and eased back to flat when the pointer leaves.
    var card = document.querySelector("[data-claim-card]");
    var onMove = null, onLeave = null;
    if (window.matchMedia("(min-width: 1024px) and (hover: hover) and (pointer: fine)").matches) {
      var rx = gsap.quickTo(card, "rotationX", { duration: 0.6, ease: "power3.out" });
      var ry = gsap.quickTo(card, "rotationY", { duration: 0.6, ease: "power3.out" });
      onMove = function (e) {
        var r = card.getBoundingClientRect();
        ry(gsap.utils.clamp(-4, 4, ((e.clientX - r.left) / r.width - 0.5) * 8));
        rx(gsap.utils.clamp(-3, 3, -((e.clientY - r.top) / r.height - 0.5) * 6));
      };
      onLeave = function () { rx(0); ry(0); };
      tl.add(function () {
        card.addEventListener("pointermove", onMove);
        card.addEventListener("pointerleave", onLeave);
      });
    }

    // ---- Ticker: fades in, then loops; slows on hover ----
    var tickerEl = document.querySelector("[data-ticker]");
    gsap.from(tickerEl, { autoAlpha: 0, duration: 0.8, delay: 1.2 });
    var ticker = gsap.to("[data-ticker-track]", { xPercent: -50, duration: 40, ease: "none", repeat: -1 });
    var slowTicker = function () { gsap.to(ticker, { timeScale: 0.15, duration: 0.6 }); };
    var resumeTicker = function () { gsap.to(ticker, { timeScale: 1, duration: 0.6 }); };
    tickerEl.addEventListener("pointerenter", slowTicker);
    tickerEl.addEventListener("pointerleave", resumeTicker);

    // ---- Section headers: rule draws, heading rises line by line, copy follows ----
    gsap.utils.toArray("[data-reveal]").forEach(function (el) {
      var h2 = el.querySelector("h2");
      var st = { trigger: el, start: "top 85%" };
      if (!h2) { // the Rejected callout
        gsap.timeline({ scrollTrigger: st })
          .from(el, { y: 24, autoAlpha: 0, duration: 0.7, ease: "power2.out" })
          .fromTo(el.querySelector(".badge"), { "--mark": 0 }, popMark, "-=0.3");
        return;
      }
      var hs = window.SplitText ? SplitText.create(h2, { type: "lines", mask: "lines" }) : null;
      if (hs) splits.push(hs);
      gsap.timeline({ scrollTrigger: st, defaults: { ease: "power3.out" } })
        .from(el.querySelector(".eyebrow"), { autoAlpha: 0, x: -12, duration: 0.5 })
        .fromTo(el.querySelector(".eyebrow"), { "--draw": 0 }, { "--draw": 1, duration: 0.5, ease: "power2.inOut" }, "<")
        .from(hs ? hs.lines : h2, { yPercent: 105, autoAlpha: hs ? 1 : 0, duration: 0.8, ease: "expo.out", stagger: 0.08 }, "-=0.25")
        .from(el.querySelectorAll("h2 ~ p"), { autoAlpha: 0, y: 12, duration: 0.6 }, "-=0.5");
    });

    // ---- Lifecycle: cards rise, numbers spin in, badges pop, line fills with scroll ----
    var life = gsap.timeline({ scrollTrigger: { trigger: ".lifecycle", start: "top 82%" } });
    life.from("[data-stage]", { y: 40, autoAlpha: 0, duration: 0.7, stagger: 0.12, ease: "power2.out", clearProps: CLEAR })
      .from(".stage-num", { scale: 0.4, rotate: -20, duration: 0.6, stagger: 0.12, ease: "back.out(2)" }, 0)
      .fromTo(".lifecycle .badge", { "--mark": 0 }, Object.assign({ stagger: 0.12 }, popMark), 0.3)
      .from(".lifecycle h3, .lifecycle p", { autoAlpha: 0, y: 8, duration: 0.45, stagger: 0.05, ease: "power2.out" }, 0.25);
    gsap.fromTo("[data-lifecycle-fill]", { scaleX: 0 }, { scaleX: 1, ease: "none", scrollTrigger: { trigger: ".lifecycle", start: "top 75%", end: "bottom 55%", scrub: 0.6 } });

    // ---- Role cards: rise, icons pop, duties tick in ----
    var roles = document.querySelector(".roles");
    gsap.timeline({ scrollTrigger: { trigger: roles, start: "top 82%" } })
      .from(roles.children, { y: 40, autoAlpha: 0, duration: 0.7, stagger: 0.12, ease: "power2.out", clearProps: CLEAR })
      .from(".role-icon", { scale: 0.5, rotate: -15, duration: 0.55, stagger: 0.12, ease: "back.out(2.2)" }, 0.2)
      .from(".role-card h3, .role-card > p", { autoAlpha: 0, y: 8, duration: 0.45, stagger: 0.06, ease: "power2.out" }, 0.3)
      .from(".role-card li", { autoAlpha: 0, x: -10, duration: 0.4, stagger: 0.05, ease: "power2.out" }, 0.5);

    // Role card hover: icon gives a small nudge
    gsap.utils.toArray(".role-card").forEach(function (c) {
      var icon = c.querySelector(".role-icon");
      c.addEventListener("pointerenter", function () {
        gsap.fromTo(icon, { rotate: 0 }, { keyframes: [{ rotate: -8, duration: 0.12 }, { rotate: 6, duration: 0.12 }, { rotate: 0, duration: 0.2 }], ease: "power1.inOut" });
      });
    });

    // ---- Policy cards: rise, approval flow steps through, categories pop ----
    var rules = document.querySelector(".rules");
    gsap.timeline({ scrollTrigger: { trigger: rules, start: "top 82%" } })
      .from(rules.children, { y: 40, autoAlpha: 0, duration: 0.7, stagger: 0.1, ease: "power2.out", clearProps: CLEAR })
      .from(".rule dt, .rule dd", { autoAlpha: 0, y: 8, duration: 0.4, stagger: 0.04, ease: "power2.out" }, 0.25);
    var flow = gsap.timeline({ scrollTrigger: { trigger: ".rule-flow", start: "top 88%" }, delay: 0.4 });
    gsap.utils.toArray(".rule-flow > *").forEach(function (part) {
      flow.from(part, part.tagName === "I"
        ? { scaleX: 0, duration: 0.35, ease: "power2.inOut" }
        : { scale: 0.7, autoAlpha: 0, duration: 0.35, ease: "back.out(2.2)" });
    });
    gsap.from(".chips li", { scale: 0.6, autoAlpha: 0, duration: 0.4, stagger: 0.07, ease: "back.out(2.4)", scrollTrigger: { trigger: ".chips", start: "top 90%" }, delay: 0.3 });

    // ---- Audit timeline: card rises, entries slide in, connector lines draw, dots pop ----
    var items = gsap.utils.toArray("[data-tl-item]");
    var tlAudit = gsap.timeline({ scrollTrigger: { trigger: "[data-timeline]", start: "top 80%" } });
    tlAudit.from("[data-timeline]", { y: 40, autoAlpha: 0, duration: 0.7, ease: "power2.out" });
    items.forEach(function (li, i) {
      var at = 0.4 + i * 0.22;
      tlAudit.from(li, { x: 24, autoAlpha: 0, duration: 0.45, ease: "power2.out" }, at)
        .from(li.querySelector(".dot"), { scale: 0, duration: 0.4, ease: "back.out(2.5)" }, at)
        .fromTo(li, { "--draw": 0 }, { "--draw": 1, duration: 0.35, ease: "power1.inOut" }, at + 0.2);
    });
    tlAudit.from("[data-timeline] blockquote", { autoAlpha: 0, x: -8, duration: 0.4, ease: "power2.out" });

    // ---- CTA: card scales up, heading lines rise, button slides in ----
    var ctaTitle = document.querySelector("[data-cta] h2");
    var cs = window.SplitText ? SplitText.create(ctaTitle, { type: "lines", mask: "lines" }) : null;
    if (cs) splits.push(cs);
    gsap.timeline({ scrollTrigger: { trigger: "[data-cta]", start: "top 88%" }, defaults: { ease: "power3.out" } })
      .from("[data-cta]", { y: 40, scale: 0.97, autoAlpha: 0, duration: 0.8 })
      .from(cs ? cs.lines : ctaTitle, { yPercent: 105, autoAlpha: cs ? 1 : 0, duration: 0.8, ease: "expo.out", stagger: 0.08 }, "-=0.45")
      .from("[data-cta] p", { autoAlpha: 0, y: 10, duration: 0.5 }, "-=0.5")
      .from("[data-cta] .btn", { autoAlpha: 0, x: 16, duration: 0.5 }, "-=0.4");

    // ---- Footer ----
    gsap.from("[data-footer] > *", { autoAlpha: 0, y: 12, duration: 0.5, stagger: 0.08, ease: "power2.out", scrollTrigger: { trigger: "[data-footer]", start: "top 98%" } });

    if (document.fonts) document.fonts.ready.then(function () { ScrollTrigger.refresh(); });

    return function () {
      if (onMove) {
        card.removeEventListener("pointermove", onMove);
        card.removeEventListener("pointerleave", onLeave);
      }
      splits.forEach(function (s) { s.revert(); });
      tickerEl.removeEventListener("pointerenter", slowTicker);
      tickerEl.removeEventListener("pointerleave", resumeTicker);
    };
  });
})();
