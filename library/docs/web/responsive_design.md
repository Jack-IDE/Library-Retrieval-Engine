# Responsive Design

## Mobile-First Philosophy

Mobile-first means writing your base CSS for the smallest screen and using `min-width` media queries to progressively enhance the layout for larger screens. This is the correct approach.

The alternative — desktop-first with `max-width` queries — forces you to undo complex layouts rather than build up from simple ones. It also tends to produce heavier CSS payloads for mobile users.

```css
/* Mobile-first: base styles apply to all screen sizes */
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

/* Tablet and up */
@media (min-width: 640px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}

/* Desktop and up */
@media (min-width: 1024px) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
```

## Standard Breakpoints

Common breakpoint values used in the industry. These are guidelines, not rules — break where the design breaks, not at arbitrary numbers.

```css
/* Common breakpoints */
/* sm  */ @media (min-width: 640px)  { ... }   /* Large phones landscape */
/* md  */ @media (min-width: 768px)  { ... }   /* Tablets portrait */
/* lg  */ @media (min-width: 1024px) { ... }   /* Tablets landscape / small laptops */
/* xl  */ @media (min-width: 1280px) { ... }   /* Desktop */
/* 2xl */ @media (min-width: 1536px) { ... }   /* Large desktop / wide monitors */
```

Define breakpoints as custom properties for consistent use (they cannot be used in media query conditions directly, but you can maintain a reference):

```css
:root {
  --bp-sm:  640px;
  --bp-md:  768px;
  --bp-lg:  1024px;
  --bp-xl:  1280px;
}
```

## Viewport Units

`vw` and `vh` are 1% of the viewport width and height respectively.

`svh` (small viewport height) accounts for mobile browser UI chrome (address bar, nav bar) being shown. `lvh` (large viewport height) assumes the chrome is hidden. `dvh` (dynamic viewport height) updates as the chrome shows/hides. Use `svh` for hero sections and full-screen layouts to prevent the bottom of the content being hidden behind the browser chrome.

`vmin` is 1% of the smaller viewport dimension. `vmax` is 1% of the larger. Useful for sizing elements that should respond to both orientations.

## Fluid Typography with clamp()

`clamp(min, preferred, max)` sets a value that scales between a minimum and maximum based on the viewport:

```css
:root {
  /* Base font size scales from 16px to 20px as viewport grows */
  --text-body: clamp(1rem, 0.95rem + 0.25vw, 1.25rem);

  /* Heading scales from 2rem to 4rem */
  --text-hero: clamp(2rem, 5vw, 4rem);

  /* Section heading */
  --text-h2: clamp(1.5rem, 3vw, 2.5rem);
}
```

The preferred value `5vw` is calculated so the scaling happens smoothly. The formula for a value that is exactly `minSize` at `minWidth` and `maxSize` at `maxWidth`:

```
preferred = minSize + (maxSize - minSize) * (100vw - minWidth) / (maxWidth - minWidth)
```

## Fluid Spacing

Apply the same clamp technique to padding and margins for layouts that scale smoothly without breakpoints:

```css
.section {
  padding-block: clamp(3rem, 8vw, 8rem);
  padding-inline: clamp(1rem, 5vw, 4rem);
}

.card-grid {
  gap: clamp(1rem, 3vw, 2rem);
}
```

## Responsive Images

Always prevent images from overflowing their containers:

```css
img, video {
  max-width: 100%;
  height: auto;       /* maintains aspect ratio */
  display: block;     /* removes inline baseline gap */
}
```

Use `srcset` and `sizes` to serve the right resolution:

```html
<img
  src="photo-800.jpg"
  srcset="
    photo-400.jpg   400w,
    photo-800.jpg   800w,
    photo-1200.jpg 1200w,
    photo-1600.jpg 1600w
  "
  sizes="
    (max-width: 640px) 100vw,
    (max-width: 1024px) 50vw,
    33vw
  "
  alt="Description"
  width="800"
  height="600"
  loading="lazy"
>
```

The `sizes` attribute tells the browser how wide the image will actually be rendered at each breakpoint, so it can select the optimal source from `srcset`. Use actual CSS breakpoints that match your layout.

## Responsive Navigation

The standard mobile navigation pattern: hamburger button on small screens, full horizontal nav on large screens.

```css
/* Mobile: hide the nav links, show hamburger */
.navbar__links {
  display: none;
  flex-direction: column;
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-4);
  gap: var(--space-2);
}

.navbar__links.is-open {
  display: flex;
}

.navbar__menu-btn { display: flex; }

/* Desktop: show links, hide hamburger */
@media (min-width: 768px) {
  .navbar__links {
    display: flex;
    flex-direction: row;
    position: static;
    border: none;
    padding: 0;
  }
  .navbar__menu-btn { display: none; }
}
```

## Container Queries

Container queries are like media queries, but they respond to the size of the element's container rather than the viewport. Essential for truly reusable components.

```css
/* Define a containment context */
.card-wrapper {
  container-type: inline-size;
  container-name: card;
}

/* Style the card based on its container width, not viewport */
.card { flex-direction: column; }

@container card (min-width: 400px) {
  .card {
    flex-direction: row;
  }
  .card__image {
    width: 40%;
    flex-shrink: 0;
  }
}
```

This means the same `.card` component can be used in a narrow sidebar (column layout) and a wide main area (row layout) without needing extra modifier classes.

## Print Styles

```css
@media print {
  /* Hide non-essential elements */
  .navbar, .sidebar, .footer, .cookie-banner, button {
    display: none !important;
  }

  /* Show link URLs after anchor text */
  a[href]::after {
    content: ' (' attr(href) ')';
    font-size: 0.8em;
    color: #666;
  }

  /* Avoid page breaks inside elements */
  article, .card, blockquote {
    break-inside: avoid;
  }

  /* Force page break before each section */
  h2 { break-before: page; }

  /* Use black text on white background */
  body {
    color: black;
    background: white;
    font-size: 12pt;
  }

  /* Expand all accordions */
  details { display: block; }
  summary + * { display: block; }
}
```

## Reduced Motion

Users who have requested reduced motion in their OS settings may have vestibular disorders or motion sensitivities. Respect their preference:

```css
/* Wrap all animations in a prefers-reduced-motion check */
@media (prefers-reduced-motion: no-preference) {
  .hero__image {
    animation: float 4s ease-in-out infinite;
  }

  .card {
    transition: transform var(--duration-normal) var(--ease-out);
  }

  .card:hover {
    transform: translateY(-4px);
  }
}

/* Provide instant transitions as fallback */
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Do not simply remove transitions for reduced-motion users — state changes should still be visible, just instantaneous instead of animated.
