# Navigation Patterns

## Breadcrumbs

Breadcrumbs show the user's location in a site hierarchy and allow navigation to parent sections.

```html
<nav aria-label="Breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb__item">
      <a class="breadcrumb__link" href="/">Home</a>
    </li>
    <li class="breadcrumb__item">
      <a class="breadcrumb__link" href="/docs">Documentation</a>
    </li>
    <li class="breadcrumb__item" aria-current="page">
      Getting Started
    </li>
  </ol>
</nav>
```

```css
.breadcrumb {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  list-style: none;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.breadcrumb__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* Separator using CSS */
.breadcrumb__item:not(:first-child)::before {
  content: '/';
  color: var(--color-border);
}

.breadcrumb__link {
  color: var(--color-text-muted);
  text-decoration: none;
}
.breadcrumb__link:hover { color: var(--color-text); text-decoration: underline; }

/* Current page item — not a link */
.breadcrumb__item[aria-current="page"] {
  color: var(--color-text);
  font-weight: 500;
}
```

Use a `<ol>` (ordered list) for breadcrumbs, not `<ul>`, because the order is meaningful. Use `aria-current="page"` on the last item (the current page), not `aria-current="true"`.

## Pagination

```html
<nav class="pagination" aria-label="Search results pagination">
  <a class="pagination__btn" href="?page=2" rel="prev" aria-label="Previous page">
    &lsaquo; Prev
  </a>

  <ol class="pagination__pages">
    <li><a class="pagination__page" href="?page=1">1</a></li>
    <li><a class="pagination__page" href="?page=2">2</a></li>
    <li><span class="pagination__page pagination__page--current" aria-current="page">3</span></li>
    <li><a class="pagination__page" href="?page=4">4</a></li>
    <li><span class="pagination__ellipsis" aria-hidden="true">…</span></li>
    <li><a class="pagination__page" href="?page=12">12</a></li>
  </ol>

  <a class="pagination__btn" href="?page=4" rel="next" aria-label="Next page">
    Next &rsaquo;
  </a>
</nav>
```

```css
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.pagination__pages {
  display: flex;
  list-style: none;
  gap: var(--space-1);
}

.pagination__page {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  text-decoration: none;
  color: var(--color-text);
  transition: background var(--duration-fast);
}

.pagination__page:hover {
  background: var(--color-bg-subtle);
}

.pagination__page--current {
  background: var(--color-accent);
  color: white;
}

.pagination__btn {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  text-decoration: none;
  color: var(--color-text);
  transition: background var(--duration-fast);
}
.pagination__btn:hover { background: var(--color-bg-subtle); }

/* Disable previous on first page */
a.pagination__btn[href="?page=0"] {
  pointer-events: none;
  opacity: 0.4;
}
```

## Dropdown Menu

```html
<div class="dropdown">
  <button class="button button--secondary" aria-haspopup="menu" aria-expanded="false" id="menu-btn">
    Options
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24">
      <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" fill="none"/>
    </svg>
  </button>

  <ul class="dropdown__menu" role="menu" aria-labelledby="menu-btn">
    <li role="none">
      <a class="dropdown__item" role="menuitem" href="/edit">Edit</a>
    </li>
    <li role="none">
      <a class="dropdown__item" role="menuitem" href="/duplicate">Duplicate</a>
    </li>
    <li class="dropdown__divider" role="separator"></li>
    <li role="none">
      <button class="dropdown__item dropdown__item--danger" role="menuitem">Delete</button>
    </li>
  </ul>
</div>
```

```css
.dropdown { position: relative; display: inline-block; }

.dropdown__menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 180px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  list-style: none;
  padding: var(--space-1);
  z-index: 50;
  opacity: 0;
  transform: translateY(-4px);
  pointer-events: none;
  transition: opacity var(--duration-fast), transform var(--duration-fast);
}

.dropdown--open .dropdown__menu {
  opacity: 1;
  transform: translateY(0);
  pointer-events: all;
}

.dropdown__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--color-text);
  text-decoration: none;
  cursor: pointer;
  transition: background var(--duration-fast);
}

.dropdown__item:hover { background: var(--color-bg-subtle); }
.dropdown__item--danger { color: #dc2626; }
.dropdown__item--danger:hover { background: #fee2e2; }

.dropdown__divider {
  height: 1px;
  background: var(--color-border);
  margin: var(--space-1) 0;
}
```

```javascript
const dropdown = document.querySelector('.dropdown');
const btn = dropdown.querySelector('[aria-haspopup]');
const menu = dropdown.querySelector('[role="menu"]');
const items = menu.querySelectorAll('[role="menuitem"]');

btn.addEventListener('click', () => {
  const open = dropdown.classList.toggle('dropdown--open');
  btn.setAttribute('aria-expanded', String(open));
  if (open) items[0].focus();
});

// Close on outside click
document.addEventListener('click', (e) => {
  if (!dropdown.contains(e.target)) {
    dropdown.classList.remove('dropdown--open');
    btn.setAttribute('aria-expanded', 'false');
  }
});

// Arrow key navigation within menu (ARIA menuitem pattern)
menu.addEventListener('keydown', (e) => {
  const idx = Array.from(items).indexOf(document.activeElement);
  if (e.key === 'ArrowDown') { e.preventDefault(); items[(idx + 1) % items.length].focus(); }
  if (e.key === 'ArrowUp')   { e.preventDefault(); items[(idx - 1 + items.length) % items.length].focus(); }
  if (e.key === 'Escape')    { dropdown.classList.remove('dropdown--open'); btn.focus(); }
  if (e.key === 'Home')      { items[0].focus(); }
  if (e.key === 'End')       { items[items.length - 1].focus(); }
});
```

## Table of Contents

A document-level table of contents that highlights the active section as the user scrolls:

```html
<nav class="toc" aria-label="Table of contents">
  <ol class="toc__list">
    <li><a class="toc__link" href="#installation">Installation</a></li>
    <li><a class="toc__link" href="#configuration">Configuration</a></li>
    <li>
      <a class="toc__link" href="#api">API Reference</a>
      <ol class="toc__sublist">
        <li><a class="toc__link" href="#api-get">GET /items</a></li>
        <li><a class="toc__link" href="#api-post">POST /items</a></li>
      </ol>
    </li>
  </ol>
</nav>
```

```css
.toc { font-size: var(--text-sm); }
.toc__list, .toc__sublist { list-style: none; }
.toc__sublist { padding-left: var(--space-4); margin-top: var(--space-1); }

.toc__link {
  display: block;
  padding: var(--space-1) 0;
  color: var(--color-text-muted);
  text-decoration: none;
  border-left: 2px solid transparent;
  padding-left: var(--space-3);
  transition: color var(--duration-fast), border-color var(--duration-fast);
}

.toc__link:hover { color: var(--color-text); }
.toc__link--active {
  color: var(--color-accent);
  border-left-color: var(--color-accent);
}
```

```javascript
const headings = document.querySelectorAll('h2[id], h3[id]');
const tocLinks = document.querySelectorAll('.toc__link');

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        tocLinks.forEach(l => l.classList.remove('toc__link--active'));
        const active = document.querySelector(`.toc__link[href="#${entry.target.id}"]`);
        active?.classList.add('toc__link--active');
      }
    });
  },
  { rootMargin: '-20% 0px -75% 0px' }
);

headings.forEach(h => observer.observe(h));
```
