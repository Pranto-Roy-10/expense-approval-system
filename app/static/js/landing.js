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

  // ---------- Header shadow ----------
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

  var mm = gsap.matchMedia();

  mm.add("(prefers-reduced-motion: reduce)", function () {
    gsap.set(heroPieces, { autoAlpha: 1 });
  });

  mm.add("(prefers-reduced-motion: no-preference)", function () {
    gsap.set(heroPieces, { autoAlpha: 1 });

    // Hero intro
    var title = document.querySelector("[data-hero-title]");
    var split = window.SplitText ? SplitText.create(title, { type: "words", mask: "words", wordsClass: "word" }) : null;
    var total = document.querySelector("[data-count]");
    var target = parseFloat(total.dataset.count);
    var counter = { v: 0 };

    var tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    tl.from(".pill", { y: 16, autoAlpha: 0, duration: 0.6 })
      .from(split ? split.words : title, {
        yPercent: 110, duration: 0.9, ease: "expo.out", stagger: 0.05,
        onComplete: function () { if (split) split.revert(); }
      }, "-=0.3")
      .from(".hero .lead, .hero-actions", { y: 20, autoAlpha: 0, duration: 0.7, stagger: 0.12 }, "-=0.55")
      .from("[data-hero-point]", { x: -14, autoAlpha: 0, duration: 0.5, stagger: 0.08 }, "-=0.4")
      .from("[data-claim-card]", {
        y: 60, rotateX: 14, transformPerspective: 1200, transformOrigin: "50% 100%",
        autoAlpha: 0, duration: 1.1, ease: "expo.out"
      }, 0.35)
      .from("[data-claim-row]", { x: 18, autoAlpha: 0, duration: 0.5, stagger: 0.12 }, 0.75)
      .to(counter, {
        v: target, duration: 1.3, ease: "power2.out",
        onUpdate: function () {
          total.textContent = counter.v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
      }, 0.9)
      .from("[data-step-dot]", { scale: 0, duration: 0.45, stagger: 0.15, ease: "back.out(2.4)" }, 1.2)
      .from("[data-steps-fill]", { scaleX: 0, duration: 0.8, ease: "power2.inOut" }, 1.35)
      .from("[data-float]", { y: 24, scale: 0.85, autoAlpha: 0, duration: 0.7, stagger: 0.25, ease: "back.out(1.7)" }, 1.6)
      .add(function () {
        gsap.to("[data-float]", { y: -8, duration: 2.6, ease: "sine.inOut", yoyo: true, repeat: -1, stagger: 0.9 });
      });

    // Ambient background drift
    gsap.to(".glow-a", { xPercent: -18, yPercent: 12, duration: 9, ease: "sine.inOut", yoyo: true, repeat: -1 });
    gsap.to(".glow-b", { xPercent: 22, yPercent: -10, duration: 11, ease: "sine.inOut", yoyo: true, repeat: -1 });
    gsap.to(".grid-lines", { yPercent: 18, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });

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

    // Ticker: endless loop of the two identical lists; slows on hover
    var ticker = gsap.to("[data-ticker-track]", { xPercent: -50, duration: 40, ease: "none", repeat: -1 });
    var tickerEl = document.querySelector("[data-ticker]");
    var slowTicker = function () { gsap.to(ticker, { timeScale: 0.15, duration: 0.6 }); };
    var resumeTicker = function () { gsap.to(ticker, { timeScale: 1, duration: 0.6 }); };
    tickerEl.addEventListener("pointerenter", slowTicker);
    tickerEl.addEventListener("pointerleave", resumeTicker);

    // Drop inline transform props after reveal so CSS hover lift (translate) works.
    var CLEAR = "transform,translate,rotate,scale";

    // Section reveals
    gsap.utils.toArray("[data-reveal]").forEach(function (el) {
      gsap.from(el, { y: 28, autoAlpha: 0, duration: 0.8, ease: "power2.out", scrollTrigger: { trigger: el, start: "top 85%" } });
    });
    gsap.utils.toArray("[data-stagger]").forEach(function (el) {
      gsap.from(el.children, { y: 40, autoAlpha: 0, duration: 0.7, stagger: 0.1, ease: "power2.out", clearProps: CLEAR, scrollTrigger: { trigger: el, start: "top 82%" } });
    });

    // Lifecycle: cards rise in, connecting line fills with scroll
    gsap.from("[data-stage]", { y: 40, autoAlpha: 0, duration: 0.7, stagger: 0.12, ease: "power2.out", clearProps: CLEAR, scrollTrigger: { trigger: ".lifecycle", start: "top 82%" } });
    gsap.fromTo("[data-lifecycle-fill]", { scaleX: 0 }, { scaleX: 1, ease: "none", scrollTrigger: { trigger: ".lifecycle", start: "top 75%", end: "bottom 55%", scrub: 0.6 } });
    gsap.from(".stage-num", { scale: 0.4, rotate: -20, duration: 0.6, stagger: 0.12, ease: "back.out(2)", scrollTrigger: { trigger: ".lifecycle", start: "top 82%" } });

    // Audit timeline: entries slide in, dots pop
    var tlAudit = gsap.timeline({ scrollTrigger: { trigger: "[data-timeline]", start: "top 80%" } });
    tlAudit.from("[data-timeline]", { y: 40, autoAlpha: 0, duration: 0.7, ease: "power2.out" })
      .from("[data-tl-item]", { x: 24, autoAlpha: 0, duration: 0.5, stagger: 0.15, ease: "power2.out" }, "-=0.3")
      .from("[data-timeline] .dot", { scale: 0, duration: 0.4, stagger: 0.15, ease: "back.out(2.5)" }, "<");

    // CTA
    gsap.from("[data-cta]", { y: 50, scale: 0.95, autoAlpha: 0, duration: 0.9, ease: "power3.out", scrollTrigger: { trigger: "[data-cta]", start: "top 88%" } });
    gsap.from("[data-cta] > *", { y: 20, autoAlpha: 0, duration: 0.6, stagger: 0.1, delay: 0.2, ease: "power2.out", scrollTrigger: { trigger: "[data-cta]", start: "top 88%" } });

    if (document.fonts) document.fonts.ready.then(function () { ScrollTrigger.refresh(); });

    return function () {
      if (onMove) {
        card.removeEventListener("pointermove", onMove);
        card.removeEventListener("pointerleave", onLeave);
      }
      if (split) split.revert();
      tickerEl.removeEventListener("pointerenter", slowTicker);
      tickerEl.removeEventListener("pointerleave", resumeTicker);
    };
  });
})();
