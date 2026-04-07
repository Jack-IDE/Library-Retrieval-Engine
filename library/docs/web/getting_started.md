# Getting Started with HTML Websites

## The Minimal Valid HTML Document

Every HTML page starts with the same skeleton. Omitting any of these pieces causes browsers to invoke quirks mode, which changes layout behavior in ways that are hard to debug.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Page Title</title>
</head>
<body>
  <!-- content here -->
</body>
</html>
```

The `<!DOCTYPE html>` declaration is not an HTML tag — it is a processing instruction that tells the browser to render in standards mode. Always put it on the very first line with no whitespace before it.

The `lang` attribute on `<html>` is required for screen readers and translation tools to work correctly. Use an IETF language tag: `en`, `fr`, `ja`, `zh-Hans`.

The `charset` meta must appear within the first 1024 bytes of the file. UTF-8 is the only correct choice for modern sites.

The `viewport` meta prevents mobile browsers from rendering the page at desktop width and then scaling it down. Without it, responsive CSS breakpoints do not work as intended on phones.

## Linking CSS and JavaScript

Place stylesheet links in the `<head>`. Place script tags at the end of `<body>`, or use `defer` in the head. Never put `<script>` tags at the top of `<head>` without `defer` or `async` — they block HTML parsing.

```html
<head>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <!-- content -->
  <script src="app.js" defer></script>
</body>
```

The `defer` attribute causes the script to download in parallel with HTML parsing and execute after the document is fully parsed, in order. Use `defer` for scripts that need the DOM. Use `async` only for fully independent scripts like analytics that do not depend on DOM order.

## Project File Structure

A practical starting structure for a small site:

```
project/
  index.html
  about.html
  contact.html
  css/
    reset.css
    layout.css
    components.css
    utilities.css
  js/
    main.js
    form.js
  img/
    logo.svg
    hero.webp
  fonts/
    inter-variable.woff2
```

Split CSS into layers. The reset file removes browser default margins, paddings, and box-sizing. The layout file defines the page grid and major containers. The components file styles individual UI elements like cards and buttons. The utilities file contains single-purpose helper classes.

## Common Beginner Mistakes

Using `<div>` for everything instead of semantic elements. Screen readers and search engines cannot infer meaning from divs. Use `<header>`, `<nav>`, `<main>`, `<article>`, `<section>`, `<aside>`, and `<footer>` where they apply.

Forgetting `box-sizing: border-box`. By default, `width` and `height` do not include padding or border, which makes layout math confusing. Add this to every project:

```css
*, *::before, *::after {
  box-sizing: border-box;
}
```

Inline styles for everything. Inline styles cannot be reused, cannot be overridden in a stylesheet without `!important`, and make the HTML harder to read. Move styles to CSS classes.

Using `px` for font sizes. Defining font sizes in `px` overrides the user's browser default font size preference, which breaks accessibility. Use `rem` for font sizes, which is relative to the root font size and respects user preferences.

Missing `alt` attributes on images. Every `<img>` must have an `alt` attribute. If the image is decorative, set `alt=""`. If it conveys information, describe it.

## Meta Tags for SEO and Social Sharing

Beyond the required charset and viewport metas, add these for better SEO and social sharing previews:

```html
<meta name="description" content="A short description of the page content, 150 characters max.">

<!-- Open Graph for Facebook, LinkedIn -->
<meta property="og:title" content="Page Title">
<meta property="og:description" content="Page description">
<meta property="og:image" content="https://example.com/share-image.jpg">
<meta property="og:url" content="https://example.com/page">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Page Title">
<meta name="twitter:description" content="Page description">
<meta name="twitter:image" content="https://example.com/share-image.jpg">
```

The `og:image` should be at least 1200×630 pixels. If omitted, social platforms will choose an image from the page at random, usually with bad results.

## Loading Fonts

Self-hosted variable fonts are faster than Google Fonts CDN for most users in 2024. Load them with `@font-face` and the `font-display: swap` descriptor so text stays visible while the font downloads:

```css
@font-face {
  font-family: 'Inter';
  src: url('../fonts/inter-variable.woff2') format('woff2');
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}
```

Preload critical fonts with a `<link rel="preload">` in the head to start the download before CSS is parsed:

```html
<link rel="preload" href="fonts/inter-variable.woff2" as="font" type="font/woff2" crossorigin>
```

The `crossorigin` attribute is required even for same-origin font files. Without it, the preloaded font is not reused by the `@font-face` declaration and downloads twice.
