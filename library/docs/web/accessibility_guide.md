# Accessibility Guide

## Why Accessibility Matters

Accessibility (a11y) is the practice of making websites usable by people with disabilities. In many countries, including the US (ADA), EU, and UK, web accessibility is a legal requirement for public-facing sites. Beyond compliance, accessible sites work better for everyone: keyboard users, people on slow connections, search engines, and screen reader users.

The Web Content Accessibility Guidelines (WCAG) define three conformance levels: A (minimum), AA (standard requirement), and AAA (enhanced). Aim for WCAG 2.1 AA as your baseline.

## Semantic HTML

Using the right HTML element is the single highest-leverage accessibility improvement. Semantic elements have built-in ARIA roles, keyboard behavior, and browser focus management that you would have to recreate manually with divs.

```html
<!-- Wrong: requires manual ARIA and keyboard handling -->
<div class="button" onclick="submit()">Submit</div>

<!-- Correct: built-in keyboard support, ARIA role, focus styles -->
<button type="submit">Submit</button>
```

Use these elements correctly:
- `<button>` for actions that do not navigate. Always specify `type="button"` unless submitting a form, to prevent unintended form submission.
- `<a href="...">` for navigation. Never use `<a>` without an `href` as a button.
- `<label>` paired with `<input>` using `for`/`id`. Every input must have a label.
- `<nav>` for site navigation. Use `aria-label` when there are multiple nav elements per page.
- `<main>` for the primary page content. There should be exactly one per page.
- `<h1>`–`<h6>` for headings in hierarchical order. Do not skip heading levels.

## ARIA — When and How

ARIA (Accessible Rich Internet Applications) attributes add accessibility semantics to elements that do not have them natively. The first rule of ARIA: do not use ARIA if a native HTML element already provides the semantics.

Common ARIA attributes:
- `aria-label` — gives an accessible name to an element that has no text content. Example: an icon-only button.
- `aria-labelledby` — links an element's accessible name to another element's text. More robust than `aria-label` for complex cases.
- `aria-describedby` — links additional descriptive text to an element. Used for input hint text and error messages.
- `aria-hidden="true"` — hides an element from screen readers. Use for decorative icons and visual-only content.
- `aria-expanded` — indicates whether a disclosure widget (accordion, dropdown) is open or closed.
- `aria-live` — marks a region as updated dynamically. Screen readers announce changes to `aria-live` regions. Use `aria-live="polite"` for non-urgent updates (search results, status messages) and `aria-live="assertive"` only for critical errors.
- `role` — overrides or adds a semantic role. Use only when native elements are not available.

## Focus Management

Keyboard users navigate with Tab (forward), Shift+Tab (backward), Enter (activate), Space (activate buttons, toggle checkboxes), Escape (dismiss), and arrow keys (within components).

Every interactive element must be reachable with keyboard and have a visible focus indicator. Never do this:

```css
/* DO NOT — removes focus indicator for keyboard users */
:focus { outline: none; }
```

Instead, customize focus styles while keeping them visible:

```css
:focus-visible {
  outline: 2px solid #005fcc;
  outline-offset: 2px;
}
/* :focus-visible only applies to keyboard navigation, not mouse clicks */
```

## Modal Dialog Accessibility

A modal dialog requires these accessibility behaviors to be correct:
1. When the modal opens, focus must move to the first focusable element inside it (or the dialog itself).
2. Focus must be trapped inside the modal — Tab and Shift+Tab must cycle through elements inside the dialog only.
3. Pressing Escape must close the modal.
4. When the modal closes, focus must return to the element that opened it.
5. The background content must be inert while the dialog is open.

```html
<dialog id="modal" aria-labelledby="modal-title" aria-modal="true">
  <h2 id="modal-title">Confirm Delete</h2>
  <p>This action cannot be undone.</p>
  <button type="button" id="modal-cancel">Cancel</button>
  <button type="button" id="modal-confirm">Delete</button>
</dialog>
```

The native `<dialog>` element handles focus trapping and Escape key dismissal when opened with `showModal()`. It also applies the `inert` attribute to the rest of the document automatically in supporting browsers. Prefer native `<dialog>` over custom modal implementations.

For focus trapping in custom components, collect all focusable elements and intercept Tab keydown:

```javascript
const focusable = modal.querySelectorAll(
  'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'
);
const first = focusable[0];
const last = focusable[focusable.length - 1];

modal.addEventListener('keydown', (e) => {
  if (e.key !== 'Tab') return;
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});
```

## Images and Alt Text

The `alt` attribute must describe the purpose of the image, not its appearance. Screen readers read the alt text aloud in place of the image.

```html
<!-- Informational image: describe what it conveys -->
<img src="chart.png" alt="Bar chart showing Q3 revenue up 23% year-over-year">

<!-- Decorative image: empty alt hides it from screen readers -->
<img src="decorative-wave.svg" alt="">

<!-- Functional image (logo that links home): describe the function -->
<a href="/"><img src="logo.svg" alt="Acme Corp — home"></a>

<!-- Never use the filename or "image of" in alt text -->
<img src="dog.jpg" alt="image of dog.jpg"> <!-- WRONG -->
<img src="dog.jpg" alt="A golden retriever puppy sitting in tall grass"> <!-- Correct -->
```

## Color and Contrast

WCAG AA requires a contrast ratio of at least 4.5:1 for normal text and 3:1 for large text (18pt or 14pt bold). UI components and graphical objects need 3:1. AAA requires 7:1 for normal text.

Never use color as the only means of conveying information. A red error message is invisible to colorblind users. Add an icon or text label as a second indicator.

## Form Accessibility

```html
<!-- Every input needs a visible label linked by for/id -->
<label for="email">Email address</label>
<input type="email" id="email" name="email" autocomplete="email" required>

<!-- Hint text linked with aria-describedby -->
<label for="password">Password</label>
<input type="password" id="password" aria-describedby="password-hint" required>
<span id="password-hint">Must be at least 8 characters.</span>

<!-- Error state: link error message and add aria-invalid -->
<input type="email" id="email" aria-invalid="true" aria-describedby="email-error">
<span id="email-error" role="alert">Please enter a valid email address.</span>
```

Group related inputs with `<fieldset>` and `<legend>`:

```html
<fieldset>
  <legend>Shipping address</legend>
  <label for="street">Street</label>
  <input type="text" id="street" name="street">
  <!-- more inputs -->
</fieldset>
```
