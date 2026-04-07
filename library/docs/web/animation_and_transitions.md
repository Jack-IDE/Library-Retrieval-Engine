# Animation and Transitions

## CSS Transitions

Transitions animate a CSS property change from one value to another. They trigger on state changes: hover, focus, active, class toggling.

```css
/* Syntax: property duration easing delay */
.button {
  transition: background 200ms ease-out, transform 150ms ease-out;
}

/* Avoid transitioning all: it creates invisible transitions on unexpected properties */
/* Use this only for prototyping: */
.prototype { transition: all 200ms; }
```

Common easing functions:

```css
/* Built-in keywords */
transition-timing-function: linear;        /* constant speed */
transition-timing-function: ease;          /* fast start, slow end (default) */
transition-timing-function: ease-in;       /* slow start, fast end */
transition-timing-function: ease-out;      /* fast start, slow end (most natural) */
transition-timing-function: ease-in-out;   /* slow start and end */

/* Custom cubic bezier */
transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1); /* spring-like overshoot */

/* Step functions (no interpolation — jump to steps) */
transition-timing-function: steps(4, end);  /* 4-frame animation */
```

Only animate properties that the browser can composite without layout recalculation. The safe properties for smooth 60fps animation:

- `transform` (translate, scale, rotate, skew) — composited, very fast
- `opacity` — composited, very fast
- `filter` — composited (blurs can be expensive)
- `clip-path` — composited in modern browsers

Avoid animating: `width`, `height`, `top`, `left`, `margin`, `padding` — these trigger layout and are slow.

## CSS Keyframe Animations

Keyframes define a multi-step animation sequence:

```css
@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%       { transform: translateX(-8px); }
  40%       { transform: translateX(8px); }
  60%       { transform: translateX(-6px); }
  80%       { transform: translateX(6px); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.5; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-10px); }
}
```

Apply animations:

```css
.hero-text {
  animation: slide-up 400ms ease-out both;
  /* 'both' fills both forwards and backwards */
}

/* Staggered animations using delay */
.hero-text { animation-delay: 0ms; }
.hero-subtext { animation-delay: 100ms; }
.hero-cta { animation-delay: 200ms; }

/* Infinite loop */
.spinner { animation: spin 0.8s linear infinite; }

/* Shake on error */
.input--error { animation: shake 400ms ease-out; }
```

## Entrance Animations for Scroll

Animate elements into view as they enter the viewport using the Intersection Observer API:

```css
.animate-on-scroll {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 500ms ease-out, transform 500ms ease-out;
}

.animate-on-scroll.is-visible {
  opacity: 1;
  transform: translateY(0);
}
```

```javascript
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target); // animate once only
      }
    });
  },
  { threshold: 0.15 }  // trigger when 15% visible
);

document.querySelectorAll('.animate-on-scroll').forEach(el => {
  observer.observe(el);
});
```

Always respect `prefers-reduced-motion`. Check the preference before applying scroll animations:

```javascript
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
if (!reducedMotion) {
  document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));
}
```

## Page Transition with the View Transitions API

The View Transitions API creates smooth animated transitions between page states without a JavaScript framework:

```css
/* Default cross-fade (built in — nothing extra needed in same-document transitions) */

/* Custom transition: slide from right */
@keyframes slide-from-right {
  from { transform: translateX(100%); }
}

@keyframes slide-to-left {
  to { transform: translateX(-100%); }
}

::view-transition-old(root) {
  animation: 300ms ease-out slide-to-left;
}

::view-transition-new(root) {
  animation: 300ms ease-out slide-from-right;
}

/* Shared element transition — element morphs between states */
.hero-image {
  view-transition-name: hero-image;
}
```

```javascript
// Trigger a same-document view transition
document.startViewTransition(() => {
  // Update the DOM here
  mainContent.innerHTML = newContent;
});
```

## CSS-Only Hover Effects

```css
/* Underline grows from left */
.nav-link {
  position: relative;
  text-decoration: none;
}

.nav-link::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 0;
  height: 2px;
  background: var(--color-accent);
  transition: width var(--duration-normal) var(--ease-out);
}

.nav-link:hover::after { width: 100%; }

/* Card lift with shadow */
.card {
  transition: transform var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

/* Image zoom on card hover */
.card__image {
  overflow: hidden;
}

.card__image img {
  transition: transform 400ms var(--ease-out);
}

.card:hover .card__image img {
  transform: scale(1.05);
}
```

## Loading Skeletons

Skeleton screens are placeholder animations shown while content loads. They reduce perceived wait time by showing the shape of content before it arrives.

```html
<div class="skeleton-card">
  <div class="skeleton skeleton--image"></div>
  <div class="skeleton-card__body">
    <div class="skeleton skeleton--line" style="width: 60%"></div>
    <div class="skeleton skeleton--line" style="width: 90%"></div>
    <div class="skeleton skeleton--line" style="width: 40%"></div>
  </div>
</div>
```

```css
.skeleton {
  background: var(--color-bg-subtle);
  border-radius: var(--radius-sm);
  position: relative;
  overflow: hidden;
}

/* Shimmer effect */
.skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgb(255 255 255 / 0.4) 50%,
    transparent 100%
  );
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  from { transform: translateX(-100%); }
  to   { transform: translateX(100%); }
}

.skeleton--image { aspect-ratio: 16/9; width: 100%; }
.skeleton--line  { height: 1em; margin-bottom: 0.5em; }

@media (prefers-reduced-motion: reduce) {
  .skeleton::after { animation: none; }
}
```

## JavaScript Spring Animation

A physics-based spring that produces natural-feeling motion:

```javascript
class Spring {
  constructor({ stiffness = 170, damping = 26, mass = 1 } = {}) {
    this.stiffness = stiffness;
    this.damping = damping;
    this.mass = mass;
    this.value = 0;
    this.velocity = 0;
    this.target = 0;
  }

  setTarget(target) { this.target = target; }

  step(dt) {
    const spring = -this.stiffness * (this.value - this.target);
    const damper = -this.damping * this.velocity;
    const acceleration = (spring + damper) / this.mass;
    this.velocity += acceleration * dt;
    this.value += this.velocity * dt;
  }

  isSettled(threshold = 0.001) {
    return Math.abs(this.velocity) < threshold && Math.abs(this.value - this.target) < threshold;
  }
}

// Usage: smooth follow cursor
const springX = new Spring({ stiffness: 200, damping = 30 });
const springY = new Spring({ stiffness: 200, damping = 30 });
let lastTime = performance.now();

function tick() {
  const now = performance.now();
  const dt = Math.min((now - lastTime) / 1000, 0.05); // max 50ms step
  lastTime = now;

  springX.step(dt);
  springY.step(dt);

  cursor.style.transform = `translate(${springX.value}px, ${springY.value}px)`;

  if (!springX.isSettled() || !springY.isSettled()) {
    requestAnimationFrame(tick);
  }
}

document.addEventListener('mousemove', (e) => {
  springX.setTarget(e.clientX);
  springY.setTarget(e.clientY);
  requestAnimationFrame(tick);
});
```
