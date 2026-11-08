// Landing page motion: a short hero entrance, sections fade up as they scroll in,
// and the device mockups drift gently. Everything is visible without JS or with reduced motion.
(function () {
  "use strict";

  var root = document.documentElement;
  var hidden = "[data-hero], [data-float]"; // hidden by landing.css until revealed here
  if (!window.gsap || !window.ScrollTrigger) {
    root.classList.remove("js");
    return;
  }
  gsap.registerPlugin(ScrollTrigger);

  var mm = gsap.matchMedia();
  mm.add("(prefers-reduced-motion: reduce)", function () {
    gsap.set(hidden, { autoAlpha: 1 });
  });

  mm.add("(prefers-reduced-motion: no-preference)", function () {
    gsap.set(hidden, { autoAlpha: 1 });

    gsap.timeline({ defaults: { ease: "power2.out" }, delay: 0.1 })
      .from("[data-hero]", { y: 18, autoAlpha: 0, duration: 0.6, stagger: 0.1 })
      .from(".dec-hero .dec-solid", { scale: 0.8, rotate: -8, duration: 1.1, ease: "power3.out" }, 0)
      .from(".dec-hero .dec-ring", { scale: 0.9, rotate: 8, autoAlpha: 0, duration: 1.3, ease: "power3.out" }, 0.1)
      .from("[data-phone]", { y: 40, autoAlpha: 0, duration: 0.8 }, 0.2)
      .from("[data-float]", { x: 40, autoAlpha: 0, duration: 0.8 }, 0.35)
      .from(".donut .seg", { strokeDasharray: "0 100", duration: 0.9, stagger: 0.12, ease: "power2.inOut" }, 0.6)
      .from(".mock-bars span", { scaleY: 0, duration: 0.5, stagger: 0.05 }, 0.7);

    // Endless loops only run while their section is on screen, so scrolling stays smooth.
    var whileVisible = function (trigger, tween) {
      tween.pause();
      ScrollTrigger.create({ trigger: trigger, start: "top bottom", end: "bottom top",
        onToggle: function (self) { if (self.isActive) tween.resume(); else tween.pause(); } });
      return tween;
    };

    // Floating: an even sine wave, sub-pixel positions (no whole-pixel snapping), GPU transforms
    var FLOAT = { ease: "sine.inOut", yoyo: true, repeat: -1, force3D: true, autoRound: false };

    // gentle drift, out of step with each other
    var hero = document.querySelector(".lp-hero");
    whileVisible(hero, gsap.to("[data-phone]", Object.assign({ y: 14, duration: 1.4, delay: 1 }, FLOAT)));
    whileVisible(hero, gsap.to("[data-float]", Object.assign({ y: 8, duration: 2.5, delay: 1 }, FLOAT)));

    // Highlights ticker: loops forever, slows down while hovered
    var tickerEl = document.querySelector("[data-ticker]");
    var ticker = whileVisible(tickerEl, gsap.to("[data-ticker-track]", { xPercent: -50, duration: 40, ease: "none", repeat: -1 }));
    var slow = function () { gsap.to(ticker, { timeScale: 0.15, duration: 0.6 }); };
    var resume = function () { gsap.to(ticker, { timeScale: 1, duration: 0.6 }); };
    tickerEl.addEventListener("pointerenter", slow);
    tickerEl.addEventListener("pointerleave", resume);

    gsap.utils.toArray("[data-reveal]").forEach(function (el) {
      var cards = el.querySelectorAll(".s-card, .feature, .role-tile");
      var tl = gsap.timeline({ scrollTrigger: { trigger: el, start: "top 85%" }, defaults: { ease: "power2.out" } });
      tl.from(el, { y: 24, autoAlpha: 0, duration: 0.6 });
      if (cards.length) tl.from(cards, { y: 20, autoAlpha: 0, duration: 0.5, stagger: 0.08 }, 0.15);
      // each step card floats on its own rhythm while on screen; yPercent so it never fights the reveal's y
      el.querySelectorAll(".s-card").forEach(function (card, i) {
        whileVisible(card, gsap.to(card, Object.assign({ yPercent: -8, duration: 1.8 + i * 0.3, delay: i * 0.25 }, FLOAT)));
      });
    });

    return function () {
      tickerEl.removeEventListener("pointerenter", slow);
      tickerEl.removeEventListener("pointerleave", resume);
    };
  });
})();
