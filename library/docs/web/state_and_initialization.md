# State and Initialization

## Startup Order Matters

A front-end site or SPA usually has several systems that want to run at startup:
- theme resolution
- router boot
- event listener registration
- hydration or page render
- analytics
- persisted state restore

If these initialize in the wrong order, you get race conditions, layout flashes, double listeners, or route mismatches.

A good baseline order is:

1. Apply theme as early as possible
2. Read persisted state needed for first paint
3. Bind global listeners once
4. Initialize router
5. Render current route
6. Start non-critical observers and analytics

## Module Scripts vs DOMContentLoaded

If you use `<script type="module">` at the end of `<body>`, many apps do not need `DOMContentLoaded` at all.

```html
<body>
  <!-- content -->
  <script type="module" src="/code/app.js"></script>
</body>
```

If the script is in `<head>`, then wait for the DOM before querying page elements.

```js
document.addEventListener('DOMContentLoaded', () => {
  initThemeControls();
  initRouter();
  initForms();
});
```

Do not mix both patterns carelessly. That often leads to setup running twice.

## One-Time Initialization Guard

For simple apps without a framework, a one-time guard is enough.

```js
let booted = false;

export function bootApp() {
  if (booted) return;
  booted = true;

  initTheme();
  initRouter();
  initUIEvents();
}
```

This is especially useful when hot reload, PJAX-style swaps, or repeated imports make initialization easy to duplicate.

## Restoring Persisted UI State

State restored from `localStorage` should be scoped and validated.

Examples of safe persisted UI state:
- selected theme
- dismissed announcement banners
- active tab id
- whether a nav section is expanded

Examples that need validation before use:
- route paths
- search filters
- user-generated HTML
- anything fed back into the DOM as markup

```js
const allowedTabs = new Set(['overview', 'pricing', 'faq']);
const savedTab = localStorage.getItem('active-tab');
const activeTab = allowedTabs.has(savedTab) ? savedTab : 'overview';
```

## Event Delegation for Stable UI Setup

Instead of binding a click handler to every button on boot, delegate from a stable ancestor.

```js
document.addEventListener('click', (event) => {
  const toggle = event.target.closest('[data-theme-toggle]');
  if (toggle) {
    document.documentElement.toggleAttribute('data-theme', 'dark');
  }
});
```

Delegation reduces rebinding work and survives dynamically inserted elements.

## Router First vs Render First

If the router controls what content is visible, initialize the router before first render so the initial page state matches the URL.

If most of the page is static and the router only enhances certain panels, render the shell first and let the router progressively enhance.

The important part is consistency: do not render one state, then immediately swap to another because the router read the URL too late.
