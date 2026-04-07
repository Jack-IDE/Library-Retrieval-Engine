# HTML Document Structure Specification

## Semantic Landmark Elements

HTML5 landmark elements define the structure of a page. Each has an implicit ARIA role that assistive technologies use to let users jump between page regions.

| Element      | ARIA Role      | Usage                                                               |
|--------------|----------------|---------------------------------------------------------------------|
| `<header>`   | `banner`       | Site-wide header with logo, primary nav. One per page at top level. |
| `<nav>`      | `navigation`   | Navigation links. Label with aria-label when multiple nav elements. |
| `<main>`     | `main`         | Primary page content. Exactly one per page.                         |
| `<article>`  | `article`      | Self-contained, independently redistributable content.              |
| `<section>`  | `region`       | Thematic grouping with a heading. Needs aria-label or heading.      |
| `<aside>`    | `complementary`| Tangentially related content — sidebars, callouts, ads.             |
| `<footer>`   | `contentinfo`  | Site-wide footer at top level. Subordinate footer inside article.   |

A `<header>` or `<footer>` nested inside `<article>` or `<section>` does not carry the `banner` or `contentinfo` role — it is scoped to its parent element.

## Heading Hierarchy

Headings form an outline of the page content. The `<h1>` is the page title. Subheadings of the `<h1>` are `<h2>`. Subheadings of an `<h2>` are `<h3>`. Never skip levels — do not go from `<h2>` to `<h4>`. Never use heading elements for visual styling; use CSS classes instead.

Each page should have exactly one `<h1>`. Multiple `<h1>` elements are permitted in the HTML5 spec via sectioning elements but cause screen reader outline confusion in practice.

## Interactive Elements

`<a href="">` — Anchor. For navigation. If it has no destination, use `<button>` instead. The `href` value may be an absolute URL, relative URL, fragment (#section-id), or `mailto:`/`tel:` URI. An `<a>` without `href` is focusable but not activatable by keyboard.

`<button>` — Button. For actions. Default `type` is `submit` inside a form; set `type="button"` explicitly for non-submit buttons. Can contain inline elements including images and SVG.

`<input>` — Form control. Type attribute changes behavior completely: `text`, `email`, `password`, `number`, `checkbox`, `radio`, `file`, `range`, `date`, `hidden`, `submit`.

`<select>` and `<option>` — Dropdown selection. Use `<optgroup label="">` to group options. For multi-select, add the `multiple` attribute.

`<textarea>` — Multi-line text input. Size is set via `rows` and `cols` attributes or CSS. The `resize` CSS property controls user resizability: `none`, `vertical`, `horizontal`, `both`.

`<details>` and `<summary>` — Native disclosure widget (accordion). No JavaScript required. The `open` attribute controls initial state. Style `details[open]` to target expanded state.

`<dialog>` — Native modal dialog. Open with `.showModal()` for modal behavior (traps focus, backdrop) or `.show()` for non-modal. Close with `.close()` or Escape key. Style the backdrop with `::backdrop`.

## Form Structure

```html
<form method="post" action="/submit" novalidate>
  <fieldset>
    <legend>Personal Information</legend>
    
    <div class="field">
      <label for="name">Full name <span aria-hidden="true">*</span></label>
      <input type="text" id="name" name="name"
             autocomplete="name" required
             aria-required="true">
    </div>
    
    <div class="field">
      <label for="email">Email</label>
      <input type="email" id="email" name="email"
             autocomplete="email"
             aria-describedby="email-hint">
      <span id="email-hint" class="hint">We will not share your email.</span>
    </div>
  </fieldset>
  
  <button type="submit">Submit</button>
</form>
```

Use `novalidate` on the form to disable native browser validation UI (which is not styleable) and implement custom validation with JavaScript and ARIA.

## Metadata Elements

Elements that belong in `<head>`:

`<title>` — Required. Page title shown in browser tabs and search results. Should be unique per page and descriptive. Recommended format: "Page Topic — Site Name".

`<meta charset="UTF-8">` — Required. Always UTF-8.

`<meta name="viewport">` — Required for responsive layouts. Standard value: `width=device-width, initial-scale=1.0`. Do not add `user-scalable=no` — it prevents zooming and violates WCAG.

`<meta name="description">` — Shown in search result snippets. Keep under 160 characters.

`<link rel="canonical" href="...">` — Declares the preferred URL for a page when content is accessible at multiple URLs.

`<link rel="icon" href="favicon.ico">` — Browser tab icon. Also support PNG and SVG:
```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.png" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
```

`<meta name="theme-color" content="#1a1a2e">` — Sets the browser chrome color on mobile. Can be updated dynamically with JavaScript.

## Data Attributes

The `data-*` attribute family stores custom data on elements without requiring non-standard attributes. The JavaScript API reads them via `element.dataset`:

```html
<button data-modal-target="confirm-dialog" data-action="open">Open</button>
```

```javascript
button.addEventListener('click', () => {
  const targetId = button.dataset.modalTarget; // 'confirm-dialog'
  const action = button.dataset.action;        // 'open'
});
```

Data attributes are useful for JavaScript hooks that do not pollute CSS classes with behavioral semantics.
