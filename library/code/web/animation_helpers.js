/**
 * animation_helpers.js — Reusable animation utilities.
 *
 * Covers: scroll-triggered entrance animations via IntersectionObserver,
 * staggered list animations, a physics-based spring, a typed text effect,
 * smooth counter animation, and scroll progress tracking.
 * No dependencies. Respects prefers-reduced-motion throughout.
 */

// ─── Motion Preference ────────────────────────────────────────────────────

const mq = window.matchMedia('(prefers-reduced-motion: reduce)');

/** Returns true if the user has requested reduced motion. */
export function prefersReducedMotion() {
  return mq.matches;
}

// ─── Scroll-triggered Entrance ────────────────────────────────────────────

/**
 * Animate elements into view as they enter the viewport.
 * Adds an 'is-visible' class when the element crosses the threshold.
 *
 * CSS contract:
 *   .animate         { opacity: 0; transform: translateY(20px); transition: ... }
 *   .animate.is-visible { opacity: 1; transform: translateY(0); }
 *
 * @param {string|NodeList|Element[]} target - CSS selector or element list.
 * @param {Object} [options]
 * @param {number} [options.threshold=0.15] - Portion of element visible before triggering.
 * @param {string} [options.rootMargin='0px'] - Margin around the root.
 * @param {boolean} [options.once=true] - Remove observer after first trigger.
 * @param {string} [options.visibleClass='is-visible']
 * @param {number} [options.staggerDelay=0] - ms between each element's entrance (index × delay).
 * @returns {IntersectionObserver|null} - null if reduced motion.
 */
export function animateOnScroll(target, options = {}) {
  if (prefersReducedMotion()) {
    // Make all elements immediately visible
    const els = resolveTargets(target);
    els.forEach(el => el.classList.add(options.visibleClass ?? 'is-visible'));
    return null;
  }

  const {
    threshold    = 0.15,
    rootMargin   = '0px',
    once         = true,
    visibleClass = 'is-visible',
    staggerDelay = 0,
  } = options;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el  = entry.target;
        const idx = Number(el.dataset.animateIndex ?? 0);
        const delay = staggerDelay * idx;

        if (delay > 0) {
          setTimeout(() => el.classList.add(visibleClass), delay);
        } else {
          el.classList.add(visibleClass);
        }

        if (once) observer.unobserve(el);
      });
    },
    { threshold, rootMargin }
  );

  resolveTargets(target).forEach((el, i) => {
    if (staggerDelay) el.dataset.animateIndex = String(i);
    observer.observe(el);
  });

  return observer;
}

// ─── Stagger Children ─────────────────────────────────────────────────────

/**
 * Apply staggered entrance animation to children of a container.
 * Adds CSS animation-delay to each child, then triggers by adding a class to the container.
 *
 * @param {Element} container
 * @param {Object} [options]
 * @param {string} [options.childSelector='> *'] - Children to stagger.
 * @param {number} [options.delayMs=60] - Delay increment per child in ms.
 * @param {string} [options.activeClass='is-staggering'] - Class added to container.
 * @param {number} [options.initialDelay=0] - Base delay for first child.
 */
export function staggerChildren(container, options = {}) {
  const {
    childSelector = '> *',
    delayMs       = 60,
    activeClass   = 'is-staggering',
    initialDelay  = 0,
  } = options;

  const children = Array.from(container.querySelectorAll(childSelector));

  if (prefersReducedMotion()) {
    container.classList.add(activeClass);
    return;
  }

  children.forEach((child, i) => {
    child.style.animationDelay = `${initialDelay + i * delayMs}ms`;
  });

  // Force reflow so animations start from scratch if class was already present
  container.classList.remove(activeClass);
  void container.offsetWidth;
  container.classList.add(activeClass);
}

// ─── Spring ───────────────────────────────────────────────────────────────

/**
 * A simple physics-based spring for smooth, natural animations.
 * Integrate with requestAnimationFrame.
 *
 * @example
 * const s = new Spring({ stiffness: 180, damping: 22 });
 * s.setTarget(100);
 *
 * function tick() {
 *   s.step(1 / 60);
 *   el.style.transform = `translateX(${s.value}px)`;
 *   if (!s.isSettled()) requestAnimationFrame(tick);
 * }
 * requestAnimationFrame(tick);
 */
export class Spring {
  /**
   * @param {Object} [options]
   * @param {number} [options.stiffness=170] - Spring stiffness (higher = snappier).
   * @param {number} [options.damping=26] - Damping (higher = less bouncy).
   * @param {number} [options.mass=1] - Mass of the simulated object.
   * @param {number} [options.initial=0] - Initial value and target.
   */
  constructor({ stiffness = 170, damping = 26, mass = 1, initial = 0 } = {}) {
    this.stiffness = stiffness;
    this.damping   = damping;
    this.mass      = mass;
    this.value     = initial;
    this.velocity  = 0;
    this.target    = initial;
  }

  setTarget(target) {
    this.target = target;
  }

  /**
   * Advance the simulation by dt seconds.
   * @param {number} dt - Delta time in seconds. Clamp to ~0.05 to prevent blowup.
   */
  step(dt = 1 / 60) {
    const clampedDt = Math.min(dt, 0.05);
    const spring     = -this.stiffness * (this.value - this.target);
    const damper     = -this.damping   * this.velocity;
    const accel      = (spring + damper) / this.mass;
    this.velocity   += accel      * clampedDt;
    this.value      += this.velocity * clampedDt;
  }

  /**
   * Returns true when the spring has effectively stopped moving.
   * @param {number} [threshold=0.001]
   */
  isSettled(threshold = 0.001) {
    return (
      Math.abs(this.velocity)         < threshold &&
      Math.abs(this.value - this.target) < threshold
    );
  }

  /** Snap to target immediately without animation. */
  snap(target) {
    this.target   = target;
    this.value    = target;
    this.velocity = 0;
  }
}

// ─── Smooth Number Counter ────────────────────────────────────────────────

/**
 * Animate a number from start to end over a duration, updating a DOM element.
 *
 * @param {Element} el - Element whose textContent is updated.
 * @param {number} end - Target number.
 * @param {Object} [options]
 * @param {number} [options.start=0]
 * @param {number} [options.duration=1200] - ms
 * @param {Function} [options.easing] - Easing function (t: 0–1) => 0–1.
 * @param {Function} [options.format] - Format the number for display. Default: toLocaleString.
 * @returns {() => void} - Cancel function.
 *
 * @example
 * animateCounter(document.getElementById('stat'), 12500, {
 *   duration: 1500,
 *   format: (n) => `${Math.round(n).toLocaleString()}+`,
 * });
 */
export function animateCounter(el, end, options = {}) {
  const {
    start    = 0,
    duration = 1200,
    easing   = easeOutCubic,
    format   = (n) => Math.round(n).toLocaleString(),
  } = options;

  if (prefersReducedMotion()) {
    el.textContent = format(end);
    return () => {};
  }

  let startTime = null;
  let raf = null;

  function tick(timestamp) {
    if (!startTime) startTime = timestamp;
    const elapsed = timestamp - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const value = start + (end - start) * easing(progress);
    el.textContent = format(value);
    if (progress < 1) {
      raf = requestAnimationFrame(tick);
    }
  }

  raf = requestAnimationFrame(tick);
  return () => { if (raf) cancelAnimationFrame(raf); };
}

// ─── Typed Text Effect ────────────────────────────────────────────────────

/**
 * Animate typing text into an element, cycling through multiple strings.
 *
 * @param {Element} el - Element to type into.
 * @param {string[]} strings - Strings to cycle through.
 * @param {Object} [options]
 * @param {number} [options.typeSpeed=80] - ms per character when typing.
 * @param {number} [options.deleteSpeed=40] - ms per character when deleting.
 * @param {number} [options.pauseEnd=2000] - ms pause after fully typed.
 * @param {number} [options.pauseStart=500] - ms pause after fully deleted.
 * @param {boolean} [options.loop=true]
 * @param {string} [options.cursor='|'] - Cursor character.
 * @returns {{ stop: () => void }}
 */
export function typeText(el, strings, options = {}) {
  const {
    typeSpeed   = 80,
    deleteSpeed = 40,
    pauseEnd    = 2000,
    pauseStart  = 500,
    loop        = true,
    cursor      = '|',
  } = options;

  if (prefersReducedMotion()) {
    el.textContent = strings[0] ?? '';
    return { stop: () => {} };
  }

  let strIndex  = 0;
  let charIndex = 0;
  let deleting  = false;
  let stopped   = false;
  let timer     = null;

  // Inject cursor span
  const cursorEl = document.createElement('span');
  cursorEl.className = 'typed-cursor';
  cursorEl.textContent = cursor;
  cursorEl.setAttribute('aria-hidden', 'true');
  el.after(cursorEl);

  function tick() {
    if (stopped) return;

    const current = strings[strIndex] ?? '';

    if (!deleting) {
      el.textContent = current.slice(0, charIndex + 1);
      charIndex++;
      if (charIndex >= current.length) {
        deleting = true;
        timer = setTimeout(tick, pauseEnd);
        return;
      }
      timer = setTimeout(tick, typeSpeed);
    } else {
      el.textContent = current.slice(0, charIndex - 1);
      charIndex--;
      if (charIndex <= 0) {
        deleting = false;
        strIndex = (strIndex + 1) % strings.length;
        if (!loop && strIndex === 0) { stopped = true; return; }
        timer = setTimeout(tick, pauseStart);
        return;
      }
      timer = setTimeout(tick, deleteSpeed);
    }
  }

  timer = setTimeout(tick, pauseStart);

  return {
    stop() {
      stopped = true;
      clearTimeout(timer);
      cursorEl.remove();
    },
  };
}

// ─── Scroll Progress ─────────────────────────────────────────────────────

/**
 * Track page scroll progress (0–1) and call a callback on each update.
 * Uses requestAnimationFrame for performance.
 *
 * @param {Function} callback - Called with progress (0–1) and scrollY.
 * @param {Object} [options]
 * @param {Element} [options.container=document.documentElement] - Scrollable container.
 * @returns {() => void} - Cleanup.
 *
 * @example
 * const cleanup = trackScrollProgress((progress) => {
 *   progressBar.style.width = `${progress * 100}%`;
 * });
 */
export function trackScrollProgress(callback, options = {}) {
  const container = options.container ?? document.documentElement;
  let ticking = false;

  function update() {
    const scrollY  = window.scrollY;
    const maxScroll = container.scrollHeight - window.innerHeight;
    const progress = maxScroll > 0 ? Math.min(scrollY / maxScroll, 1) : 0;
    callback(progress, scrollY);
    ticking = false;
  }

  function onScroll() {
    if (!ticking) {
      requestAnimationFrame(update);
      ticking = true;
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  update(); // initial call
  return () => window.removeEventListener('scroll', onScroll);
}

// ─── Easing Functions ─────────────────────────────────────────────────────

export function linear(t)       { return t; }
export function easeInQuad(t)   { return t * t; }
export function easeOutQuad(t)  { return t * (2 - t); }
export function easeInOutQuad(t){ return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }
export function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
export function easeInOutCubic(t){ return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
export function easeOutExpo(t)  { return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); }
export function easeOutBack(t)  {
  const c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}
export function easeOutBounce(t) {
  const n1 = 7.5625, d1 = 2.75;
  if      (t < 1 / d1)       return n1 * t * t;
  else if (t < 2 / d1)       return n1 * (t -= 1.5 / d1) * t + 0.75;
  else if (t < 2.5 / d1)     return n1 * (t -= 2.25 / d1) * t + 0.9375;
  else                        return n1 * (t -= 2.625 / d1) * t + 0.984375;
}

// ─── Internal Helpers ─────────────────────────────────────────────────────

function resolveTargets(target) {
  if (typeof target === 'string') return Array.from(document.querySelectorAll(target));
  if (target instanceof Element)  return [target];
  return Array.from(target);
}
