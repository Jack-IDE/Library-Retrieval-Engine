# Layout Patterns

## Hero Section

A hero section occupies the top of a page and typically contains a headline, subtext, and a call-to-action button. Common approaches:

**Full-viewport hero with centered content:**
```html
<section class="hero">
  <div class="hero__inner">
    <h1 class="hero__heading">Build something great.</h1>
    <p class="hero__subtext">A short description that supports the headline.</p>
    <a href="/start" class="button button--primary button--lg">Get started</a>
  </div>
</section>
```

```css
.hero {
  min-height: 100svh;        /* svh: small viewport height — accounts for mobile browser chrome */
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
  color: white;
  padding: var(--space-8);
}

.hero__inner {
  max-width: 720px;
}

.hero__heading {
  font-size: clamp(2rem, 5vw, 4rem); /* fluid type: min, preferred, max */
  font-weight: 800;
  line-height: 1.1;
  margin-bottom: var(--space-4);
}
```

**Split hero: text left, image right:**
```css
.hero {
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: center;
  gap: var(--space-12);
  padding: var(--space-16) var(--space-8);
  max-width: 1280px;
  margin: 0 auto;
}

@media (max-width: 768px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .hero__image { order: -1; } /* Image above text on mobile */
}
```

## Navigation Bar

**Sticky top navbar that hides on scroll down, reveals on scroll up:**
```html
<header class="navbar" id="navbar">
  <a class="navbar__logo" href="/">Brand</a>
  <nav class="navbar__nav" aria-label="Main">
    <ul class="navbar__links">
      <li><a class="navbar__link" href="/about">About</a></li>
      <li><a class="navbar__link" href="/work">Work</a></li>
      <li><a class="navbar__link" href="/contact">Contact</a></li>
    </ul>
  </nav>
  <button class="navbar__menu-btn" aria-expanded="false" aria-controls="mobile-menu"
          aria-label="Open menu">
    <span class="navbar__hamburger"></span>
  </button>
</header>
```

```css
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-6);
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  transition: transform var(--duration-normal) var(--ease-out);
}

.navbar--hidden {
  transform: translateY(-100%);
}
```

```javascript
let lastY = 0;
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  const y = window.scrollY;
  navbar.classList.toggle('navbar--hidden', y > lastY && y > 80);
  lastY = y;
}, { passive: true });
```

## Card Grid

Cards are the most common pattern for displaying a collection of items.

```html
<div class="card-grid">
  <article class="card">
    <img class="card__image" src="..." alt="..." width="400" height="250" loading="lazy">
    <div class="card__body">
      <p class="card__tag">Design</p>
      <h2 class="card__title"><a href="/post/1">Article Title</a></h2>
      <p class="card__excerpt">A short excerpt from the article content.</p>
    </div>
    <footer class="card__footer">
      <time datetime="2024-06-15">June 15, 2024</time>
    </footer>
  </article>
  <!-- more cards -->
</div>
```

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-6);
  padding: var(--space-8);
}

.card {
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

.card__image {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
}

.card__body {
  flex: 1;           /* pushes footer to bottom */
  padding: var(--space-4);
}

.card__footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.card__title a {
  text-decoration: none;
  color: inherit;
}
.card__title a::after {
  content: '';
  position: absolute;
  inset: 0; /* makes entire card clickable for the link */
}
.card { position: relative; }
```

## Sidebar Layout

Two-column layout with a fixed sidebar and scrollable main content:

```css
.page-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  grid-template-rows: auto 1fr;
  min-height: 100vh;
}

.sidebar {
  grid-row: 1 / -1;         /* spans all rows */
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: var(--space-6);
  border-right: 1px solid var(--color-border);
}

@media (max-width: 900px) {
  .page-layout {
    grid-template-columns: 1fr;
  }
  .sidebar {
    position: static;
    height: auto;
    border-right: none;
    border-bottom: 1px solid var(--color-border);
  }
}
```

## Footer

A multi-column site footer:

```html
<footer class="site-footer">
  <div class="site-footer__inner">
    <div class="site-footer__brand">
      <a href="/">Brand</a>
      <p>Short brand description or tagline.</p>
    </div>
    <nav class="site-footer__col" aria-label="Product links">
      <h3 class="site-footer__heading">Product</h3>
      <ul>
        <li><a href="/features">Features</a></li>
        <li><a href="/pricing">Pricing</a></li>
        <li><a href="/changelog">Changelog</a></li>
      </ul>
    </nav>
    <nav class="site-footer__col" aria-label="Company links">
      <h3 class="site-footer__heading">Company</h3>
      <ul>
        <li><a href="/about">About</a></li>
        <li><a href="/blog">Blog</a></li>
        <li><a href="/careers">Careers</a></li>
      </ul>
    </nav>
  </div>
  <div class="site-footer__bar">
    <p>&copy; 2024 Brand. All rights reserved.</p>
  </div>
</footer>
```

```css
.site-footer__inner {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: var(--space-8);
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-12) var(--space-8);
}

@media (max-width: 768px) {
  .site-footer__inner {
    grid-template-columns: 1fr 1fr;
  }
  .site-footer__brand {
    grid-column: 1 / -1;
  }
}
```

## Modal Overlay

```html
<dialog class="modal" id="confirm-modal" aria-labelledby="modal-title">
  <div class="modal__content">
    <header class="modal__header">
      <h2 class="modal__title" id="modal-title">Confirm Action</h2>
      <button class="modal__close" aria-label="Close dialog">×</button>
    </header>
    <div class="modal__body">
      <p>Are you sure you want to delete this item? This cannot be undone.</p>
    </div>
    <footer class="modal__footer">
      <button type="button" class="button button--ghost" data-close-modal>Cancel</button>
      <button type="button" class="button button--danger">Delete</button>
    </footer>
  </div>
</dialog>
```

```css
.modal {
  border: none;
  border-radius: var(--radius-lg);
  padding: 0;
  max-width: min(560px, 90vw);
  width: 100%;
  box-shadow: var(--shadow-lg);
}

.modal::backdrop {
  background: rgb(0 0 0 / 0.5);
  backdrop-filter: blur(2px);
}

/* Entrance animation */
.modal[open] {
  animation: modal-in var(--duration-slow) var(--ease-out);
}

@keyframes modal-in {
  from { opacity: 0; transform: translateY(-12px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.modal__content { display: flex; flex-direction: column; }
.modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--color-border);
}
.modal__body { padding: var(--space-6); }
.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--color-border);
}
```

```javascript
const modal = document.getElementById('confirm-modal');
const opener = document.getElementById('open-modal-btn');

opener.addEventListener('click', () => {
  modal.showModal();
});

modal.addEventListener('click', (e) => {
  if (e.target === modal) modal.close(); // close on backdrop click
});

modal.querySelectorAll('[data-close-modal], .modal__close').forEach(btn => {
  btn.addEventListener('click', () => modal.close());
});
```

## Skip Link

A skip navigation link that lets keyboard users jump past the navigation to the main content. Must be the first focusable element on the page.

```html
<a class="skip-link" href="#main-content">Skip to main content</a>
<header>...</header>
<main id="main-content">...</main>
```

```css
.skip-link {
  position: absolute;
  top: -100%;
  left: var(--space-4);
  padding: var(--space-2) var(--space-4);
  background: var(--color-accent);
  color: white;
  font-weight: 600;
  text-decoration: none;
  border-radius: var(--radius-md);
  z-index: 9999;
  transition: top var(--duration-fast);
}

.skip-link:focus {
  top: var(--space-4);
}
```
