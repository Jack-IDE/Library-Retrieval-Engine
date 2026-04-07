# CSS Architecture Specification

## CSS Custom Properties (Variables)

Custom properties (CSS variables) are the foundation of a maintainable CSS system. They cascade, inherit, can be set per-scope, and are readable and writable with JavaScript.

Define a design token system on the root element:

```css
:root {
  /* Color palette */
  --color-primary-50:  #eff6ff;
  --color-primary-500: #3b82f6;
  --color-primary-900: #1e3a5f;
  --color-neutral-0:   #ffffff;
  --color-neutral-100: #f3f4f6;
  --color-neutral-900: #111827;

  /* Semantic tokens — reference palette tokens */
  --color-bg:           var(--color-neutral-0);
  --color-bg-subtle:    var(--color-neutral-100);
  --color-text:         var(--color-neutral-900);
  --color-text-muted:   #6b7280;
  --color-accent:       var(--color-primary-500);
  --color-border:       #e5e7eb;

  /* Typography */
  --font-sans:  'Inter', system-ui, sans-serif;
  --font-mono:  'JetBrains Mono', 'Fira Code', monospace;
  --text-xs:    0.75rem;
  --text-sm:    0.875rem;
  --text-base:  1rem;
  --text-lg:    1.125rem;
  --text-xl:    1.25rem;
  --text-2xl:   1.5rem;
  --text-3xl:   1.875rem;
  --text-4xl:   2.25rem;
  --leading-tight:  1.25;
  --leading-normal: 1.5;
  --leading-loose:  1.75;

  /* Spacing scale */
  --space-1:  0.25rem;
  --space-2:  0.5rem;
  --space-3:  0.75rem;
  --space-4:  1rem;
  --space-6:  1.5rem;
  --space-8:  2rem;
  --space-12: 3rem;
  --space-16: 4rem;

  /* Radii */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 1rem;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);

  /* Transitions */
  --duration-fast:   100ms;
  --duration-normal: 200ms;
  --duration-slow:   300ms;
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in:  cubic-bezier(0.4, 0, 1, 1);
}
```

## Dark Mode with Custom Properties

Implementing dark mode by swapping semantic token values:

```css
:root {
  --color-bg:   #ffffff;
  --color-text: #111827;
  --color-border: #e5e7eb;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg:   #111827;
    --color-text: #f9fafb;
    --color-border: #374151;
  }
}

/* JavaScript-controlled dark mode */
[data-theme="dark"] {
  --color-bg:   #111827;
  --color-text: #f9fafb;
}
```

Reading and writing custom properties with JavaScript:

```javascript
// Read
const bg = getComputedStyle(document.documentElement).getPropertyValue('--color-bg');

// Write
document.documentElement.style.setProperty('--color-accent', '#10b981');

// Toggle theme
document.documentElement.dataset.theme =
  document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
```

## BEM Naming Convention

BEM (Block, Element, Modifier) is a class naming convention that makes CSS scope and intent clear without nesting:

- **Block** — standalone component: `.card`, `.button`, `.nav`
- **Element** — child of block, separated by double underscore: `.card__title`, `.card__body`, `.nav__link`
- **Modifier** — variant of block or element, separated by double hyphen: `.button--primary`, `.button--large`, `.card--featured`

```html
<div class="card card--featured">
  <img class="card__image" src="..." alt="...">
  <div class="card__body">
    <h2 class="card__title">Title</h2>
    <p class="card__excerpt">Text</p>
  </div>
  <a class="card__cta button button--primary" href="...">Read more</a>
</div>
```

```css
.card { background: var(--color-bg); border-radius: var(--radius-md); }
.card--featured { border: 2px solid var(--color-accent); }
.card__title { font-size: var(--text-xl); font-weight: 700; }
.card__body { padding: var(--space-4); }
```

BEM avoids specificity wars because all selectors are single classes. It avoids deeply nested CSS that becomes unreadable.

## Utility Classes

Utility classes are single-purpose classes that apply one CSS declaration each. Useful for spacing adjustments and one-off overrides without creating new component classes:

```css
/* Display */
.flex    { display: flex; }
.grid    { display: grid; }
.hidden  { display: none; }

/* Spacing */
.mt-4    { margin-top: var(--space-4); }
.px-6    { padding-left: var(--space-6); padding-right: var(--space-6); }
.gap-4   { gap: var(--space-4); }

/* Typography */
.text-sm     { font-size: var(--text-sm); }
.font-bold   { font-weight: 700; }
.text-muted  { color: var(--color-text-muted); }
.truncate    { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Visual */
.rounded     { border-radius: var(--radius-md); }
.shadow-md   { box-shadow: var(--shadow-md); }
.sr-only {   /* screen reader only, visually hidden but accessible */
  position: absolute; width: 1px; height: 1px; padding: 0;
  margin: -1px; overflow: hidden; clip: rect(0,0,0,0);
  white-space: nowrap; border-width: 0;
}
```

## CSS Reset

A minimal reset that normalizes cross-browser differences without removing all browser defaults:

```css
*, *::before, *::after {
  box-sizing: border-box;
}

* {
  margin: 0;
  padding: 0;
}

html {
  -webkit-text-size-adjust: 100%;
  tab-size: 4;
}

body {
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

img, picture, video, canvas, svg {
  display: block;
  max-width: 100%;
}

input, button, textarea, select {
  font: inherit;
}

p, h1, h2, h3, h4, h5, h6 {
  overflow-wrap: break-word;
}

a {
  color: inherit;
}
```

## CSS Layers

`@layer` (CSS Cascade Layers) allows explicit control over cascade order, solving specificity conflicts between third-party styles and your own:

```css
@layer reset, base, components, utilities;

@layer reset {
  *, *::before, *::after { box-sizing: border-box; }
}

@layer base {
  body { font-family: var(--font-sans); color: var(--color-text); }
}

@layer components {
  .button { padding: 0.5rem 1rem; border-radius: var(--radius-md); }
}

@layer utilities {
  .mt-4 { margin-top: 1rem; }
}
```

Later-declared layers win over earlier layers regardless of specificity. Unlayered styles win over all layers. This allows you to import a third-party library in a low-priority layer without its styles overriding yours.
