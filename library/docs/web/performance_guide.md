# Performance Guide

## Core Web Vitals

Google measures page performance with Core Web Vitals. These scores directly affect search ranking and user experience:

- **LCP (Largest Contentful Paint)** — how long until the largest visible element renders. Target: under 2.5 seconds. Usually a hero image or heading. Optimize by preloading the LCP image and serving it in WebP or AVIF format.
- **FID (First Input Delay) / INP (Interaction to Next Paint)** — how long the browser takes to respond to the first user interaction. Target: INP under 200ms. Optimize by breaking long tasks and avoiding heavy main-thread JavaScript.
- **CLS (Cumulative Layout Shift)** — how much content shifts around unexpectedly during load. Target: under 0.1. Optimize by setting explicit `width` and `height` on images and reserving space for ads and embeds.

## Image Optimization

Images are usually the largest portion of page weight. Serve the right format, right size, and load lazily.

Use WebP for photographs and complex images. Use AVIF where supported (better compression, less browser support). Use SVG for icons, logos, and illustrations. Use PNG only when you need lossless quality and AVIF/WebP are not suitable.

```html
<!-- Responsive image with format fallback and lazy loading -->
<picture>
  <source srcset="hero.avif" type="image/avif">
  <source srcset="hero.webp" type="image/webp">
  <img
    src="hero.jpg"
    alt="Hero image description"
    width="1200"
    height="600"
    loading="lazy"
    decoding="async"
  >
</picture>
```

Always set `width` and `height` attributes on `<img>`. The browser uses these to reserve layout space before the image downloads, preventing CLS. The values do not need to match the displayed size — the CSS controls display size, the attributes inform the aspect ratio.

Use `loading="lazy"` on all images below the fold. Do NOT add it to the LCP image or any image visible in the initial viewport — it delays their load.

Use `srcset` and `sizes` to serve appropriately sized images to different screen widths:

```html
<img
  src="card.jpg"
  srcset="card-400.jpg 400w, card-800.jpg 800w, card-1200.jpg 1200w"
  sizes="(max-width: 600px) 100vw, (max-width: 1200px) 50vw, 400px"
  alt="Card image"
  width="400"
  height="300"
>
```

## CSS Performance

Avoid overly complex selectors. The browser matches selectors right-to-left. `div p span a` is slower than `.nav-link`.

Do not use `@import` in CSS files — it creates a serial request waterfall. Use `<link>` elements in HTML or bundle CSS at build time.

Minimize render-blocking CSS. Only the CSS in the initial `<link>` tags blocks rendering. Defer non-critical CSS by loading it asynchronously:

```html
<link rel="preload" href="print.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="print.css"></noscript>
```

Use `will-change` sparingly. It promotes elements to their own compositing layer, which can improve animation performance but increases memory usage:

```css
/* Only before an animation starts, remove afterward */
.animating { will-change: transform, opacity; }
```

## JavaScript Performance

JavaScript blocks the main thread. Large scripts prevent user interaction and delay rendering. Keep JavaScript payloads small and load non-critical scripts asynchronously.

Defer non-critical scripts:

```html
<script src="analytics.js" async></script>     <!-- no DOM dependency, order doesn't matter -->
<script src="app.js" defer></script>            <!-- needs DOM, runs after parse in order -->
```

Debounce event handlers on high-frequency events (scroll, resize, input):

```javascript
function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

window.addEventListener('scroll', debounce(handleScroll, 100));
```

Use `requestAnimationFrame` for visual updates tied to scroll or resize — do not read and write the DOM in the same frame:

```javascript
let ticking = false;
window.addEventListener('scroll', () => {
  if (!ticking) {
    requestAnimationFrame(() => {
      updateStickyHeader();
      ticking = false;
    });
    ticking = true;
  }
});
```

Split large computations across frames using `setTimeout(fn, 0)` or `scheduler.postTask()` to avoid blocking the main thread.

## Caching and Resource Hints

Use resource hints to start connections and downloads early:

```html
<!-- Start DNS lookup for third-party domain -->
<link rel="dns-prefetch" href="https://fonts.googleapis.com">

<!-- Start TCP connection (includes DNS + TLS) -->
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<!-- Download resource now, use later -->
<link rel="preload" href="fonts/inter.woff2" as="font" type="font/woff2" crossorigin>

<!-- Download next page's resources during idle time -->
<link rel="prefetch" href="product-detail.js">
```

Set aggressive cache headers for hashed assets. When filenames include a content hash (e.g., `app.a3f9b2.js`), they can be cached indefinitely:

```
Cache-Control: public, max-age=31536000, immutable
```

HTML and non-hashed assets should use short cache times or must-revalidate:

```
Cache-Control: no-cache
```

## Critical Rendering Path

The browser renders a page by: parsing HTML to build the DOM, parsing CSS to build the CSSOM, combining them into the render tree, laying out elements, and painting. Any resource that blocks this process delays First Contentful Paint.

Inline critical CSS (the styles needed to render above-the-fold content) directly in a `<style>` block in the `<head>`. Load the full stylesheet non-critically. This technique eliminates the render-blocking stylesheet request for the initial view and is effective for perceived performance.

```html
<head>
  <style>
    /* Inlined critical CSS — only what is needed for the first screenful */
    body { margin: 0; font-family: system-ui; }
    .header { background: #1a1a2e; color: white; padding: 1rem; }
    .hero { min-height: 60vh; display: flex; align-items: center; }
  </style>
  <link rel="preload" href="styles.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
</head>
```
