# Common Components

## Buttons

Buttons are the most frequently used interactive component. Define a complete button system with variants and sizes.

```css
/* Base button */
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-base);
  font-weight: 600;
  line-height: 1;
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  text-decoration: none;
  transition: background var(--duration-fast), color var(--duration-fast),
              border-color var(--duration-fast), box-shadow var(--duration-fast),
              transform var(--duration-fast);
  user-select: none;
  white-space: nowrap;
}

.button:active { transform: translateY(1px); }

.button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}

/* Variants */
.button--primary {
  background: var(--color-accent);
  color: white;
}
.button--primary:hover {
  background: color-mix(in srgb, var(--color-accent) 85%, black);
}

.button--secondary {
  background: var(--color-bg-subtle);
  color: var(--color-text);
  border-color: var(--color-border);
}
.button--secondary:hover {
  background: var(--color-border);
}

.button--ghost {
  background: transparent;
  color: var(--color-text);
}
.button--ghost:hover {
  background: var(--color-bg-subtle);
}

.button--danger {
  background: #dc2626;
  color: white;
}
.button--danger:hover { background: #b91c1c; }

.button--outline {
  background: transparent;
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.button--outline:hover {
  background: var(--color-accent);
  color: white;
}

/* Sizes */
.button--sm { padding: var(--space-1) var(--space-3); font-size: var(--text-sm); }
.button--lg { padding: var(--space-3) var(--space-6); font-size: var(--text-lg); }
.button--xl { padding: var(--space-4) var(--space-8); font-size: var(--text-xl); }

/* Icon button */
.button--icon {
  padding: var(--space-2);
  aspect-ratio: 1;
}

/* Loading state */
.button--loading {
  position: relative;
  color: transparent;
  pointer-events: none;
}
.button--loading::after {
  content: '';
  position: absolute;
  width: 1em;
  height: 1em;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
```

## Badges and Tags

```html
<span class="badge badge--success">Active</span>
<span class="badge badge--warning">Pending</span>
<span class="badge badge--error">Failed</span>
<span class="badge badge--neutral">Draft</span>

<div class="tag-list">
  <span class="tag">HTML</span>
  <span class="tag">CSS</span>
  <button class="tag tag--removable">
    JavaScript
    <span aria-hidden="true">×</span>
  </button>
</div>
```

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.125rem 0.5rem;
  font-size: var(--text-xs);
  font-weight: 600;
  border-radius: var(--radius-full);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.badge--success { background: #dcfce7; color: #166534; }
.badge--warning { background: #fef9c3; color: #854d0e; }
.badge--error   { background: #fee2e2; color: #991b1b; }
.badge--neutral { background: var(--color-bg-subtle); color: var(--color-text-muted); }

.tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  background: var(--color-bg-subtle);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
}
```

## Alert / Toast Notifications

```html
<div class="alert alert--info" role="alert">
  <svg class="alert__icon" aria-hidden="true"><!-- info icon --></svg>
  <div class="alert__content">
    <strong class="alert__title">Heads up</strong>
    <p>Your changes have been saved automatically.</p>
  </div>
  <button class="alert__dismiss" aria-label="Dismiss">×</button>
</div>
```

```css
.alert {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  border-left: 4px solid currentColor;
}

.alert--info    { background: #eff6ff; color: #1d4ed8; }
.alert--success { background: #f0fdf4; color: #15803d; }
.alert--warning { background: #fffbeb; color: #b45309; }
.alert--error   { background: #fef2f2; color: #dc2626; }

.alert__content { flex: 1; color: var(--color-text); }
.alert__title   { display: block; font-weight: 600; margin-bottom: var(--space-1); }

/* Toast — floating notification */
.toast-container {
  position: fixed;
  bottom: var(--space-4);
  right: var(--space-4);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  pointer-events: none;
}

.toast {
  pointer-events: all;
  background: var(--color-neutral-900);
  color: white;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  animation: toast-in var(--duration-slow) var(--ease-out);
  min-width: 260px;
  max-width: 400px;
}

@keyframes toast-in {
  from { opacity: 0; transform: translateX(100%); }
  to   { opacity: 1; transform: translateX(0); }
}
```

## Tabs

```html
<div class="tabs" role="tablist" aria-label="Documentation sections">
  <button class="tabs__tab" role="tab" aria-selected="true" aria-controls="panel-overview" id="tab-overview">
    Overview
  </button>
  <button class="tabs__tab" role="tab" aria-selected="false" aria-controls="panel-api" id="tab-api" tabindex="-1">
    API Reference
  </button>
  <button class="tabs__tab" role="tab" aria-selected="false" aria-controls="panel-examples" id="tab-examples" tabindex="-1">
    Examples
  </button>
</div>

<div class="tabs__panel" role="tabpanel" id="panel-overview" aria-labelledby="tab-overview">
  <!-- overview content -->
</div>
<div class="tabs__panel" role="tabpanel" id="panel-api" aria-labelledby="tab-api" hidden>
  <!-- api content -->
</div>
```

```css
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--color-border);
}

.tabs__tab {
  padding: var(--space-3) var(--space-4);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;    /* overlaps container border */
  color: var(--color-text-muted);
  font-weight: 500;
  cursor: pointer;
  transition: color var(--duration-fast), border-color var(--duration-fast);
}

.tabs__tab[aria-selected="true"] {
  color: var(--color-accent);
  border-bottom-color: var(--color-accent);
}

.tabs__tab:hover { color: var(--color-text); }
```

```javascript
const tabs = document.querySelectorAll('[role="tab"]');

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    // Deactivate all tabs
    tabs.forEach(t => {
      t.setAttribute('aria-selected', 'false');
      t.setAttribute('tabindex', '-1');
    });
    // Activate clicked tab
    tab.setAttribute('aria-selected', 'true');
    tab.removeAttribute('tabindex');

    // Show correct panel
    document.querySelectorAll('[role="tabpanel"]').forEach(p => p.hidden = true);
    document.getElementById(tab.getAttribute('aria-controls')).hidden = false;
  });

  // Arrow key navigation between tabs (ARIA keyboard pattern)
  tab.addEventListener('keydown', (e) => {
    const idx = Array.from(tabs).indexOf(tab);
    if (e.key === 'ArrowRight') tabs[(idx + 1) % tabs.length].click();
    if (e.key === 'ArrowLeft')  tabs[(idx - 1 + tabs.length) % tabs.length].click();
    if (e.key === 'Home') tabs[0].click();
    if (e.key === 'End')  tabs[tabs.length - 1].click();
  });
});
```

## Accordion

```html
<div class="accordion">
  <details class="accordion__item">
    <summary class="accordion__summary">
      <span>What is included in the free plan?</span>
      <svg class="accordion__chevron" aria-hidden="true" viewBox="0 0 24 24">
        <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" fill="none"/>
      </svg>
    </summary>
    <div class="accordion__body">
      <p>The free plan includes up to 3 projects, 1GB storage, and community support.</p>
    </div>
  </details>
</div>
```

```css
.accordion__item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.accordion__item + .accordion__item { margin-top: var(--space-2); }

.accordion__summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  cursor: pointer;
  font-weight: 500;
  list-style: none;           /* remove default marker */
}

/* Remove default marker in webkit */
.accordion__summary::-webkit-details-marker { display: none; }

.accordion__chevron {
  width: 1.25em;
  height: 1.25em;
  transition: transform var(--duration-normal) var(--ease-out);
  flex-shrink: 0;
}

details[open] .accordion__chevron { transform: rotate(180deg); }

.accordion__body {
  padding: 0 var(--space-4) var(--space-4);
  color: var(--color-text-muted);
}
```

## Tooltip

```html
<span class="tooltip-wrapper">
  <button class="button button--icon" aria-describedby="tooltip-copy">
    Copy
  </button>
  <span class="tooltip" id="tooltip-copy" role="tooltip">Copy to clipboard</span>
</span>
```

```css
.tooltip-wrapper {
  position: relative;
  display: inline-block;
}

.tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-1) var(--space-3);
  background: var(--color-neutral-900);
  color: white;
  font-size: var(--text-sm);
  white-space: nowrap;
  border-radius: var(--radius-sm);
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--duration-fast);
  z-index: 50;
}

/* Arrow */
.tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: var(--color-neutral-900);
}

.tooltip-wrapper:hover .tooltip,
.tooltip-wrapper:focus-within .tooltip {
  opacity: 1;
}
```

## Progress Bar

```html
<div class="progress" role="progressbar" aria-valuenow="65" aria-valuemin="0" aria-valuemax="100"
     aria-label="Upload progress">
  <div class="progress__bar" style="width: 65%"></div>
</div>
```

```css
.progress {
  height: 8px;
  background: var(--color-bg-subtle);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress__bar {
  height: 100%;
  background: var(--color-accent);
  border-radius: var(--radius-full);
  transition: width var(--duration-slow) var(--ease-out);
}

/* Indeterminate / loading state */
.progress--indeterminate .progress__bar {
  width: 40%;
  animation: progress-slide 1.5s ease-in-out infinite;
}

@keyframes progress-slide {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(300%); }
}
```

## Avatar

```html
<!-- Image avatar -->
<img class="avatar" src="user.jpg" alt="Jane Doe" width="40" height="40">

<!-- Initials fallback -->
<span class="avatar avatar--initials" aria-label="Jane Doe">JD</span>

<!-- Avatar group -->
<div class="avatar-group" aria-label="3 team members">
  <img class="avatar" src="a.jpg" alt="Alice" title="Alice">
  <img class="avatar" src="b.jpg" alt="Bob"   title="Bob">
  <span class="avatar avatar--count" aria-hidden="true">+5</span>
</div>
```

```css
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--color-bg);
}

.avatar--initials {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent);
  color: white;
  font-size: var(--text-sm);
  font-weight: 700;
}

.avatar-group {
  display: flex;
}
.avatar-group .avatar { margin-left: -10px; }
.avatar-group .avatar:first-child { margin-left: 0; }
```
