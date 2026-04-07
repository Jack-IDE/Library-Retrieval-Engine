# Typography and Color

## Type Scale

A type scale is a set of harmonically related font sizes. Use a modular scale — each size is the previous size multiplied by a fixed ratio. Common ratios: 1.125 (Major Second), 1.25 (Major Third), 1.333 (Perfect Fourth), 1.5 (Perfect Fifth).

A practical scale using 1rem (16px) as the base and a 1.25 ratio:

```css
:root {
  --text-xs:   0.640rem;  /* 10.2px */
  --text-sm:   0.800rem;  /* 12.8px */
  --text-base: 1.000rem;  /* 16px   */
  --text-lg:   1.250rem;  /* 20px   */
  --text-xl:   1.563rem;  /* 25px   */
  --text-2xl:  1.953rem;  /* 31.2px */
  --text-3xl:  2.441rem;  /* 39px   */
  --text-4xl:  3.052rem;  /* 48.8px */
}
```

Apply the scale consistently. Use `--text-base` for body text, `--text-sm` for captions and meta info, `--text-lg` for lead paragraphs, `--text-xl` through `--text-4xl` for headings.

## Line Height

Line height (leading) controls readability. Too tight and lines feel cramped. Too loose and they feel disconnected.

Rules of thumb:
- Body text: 1.5–1.7 for comfortable reading in paragraph form.
- Headings: 1.1–1.25. Large text needs tighter line height to look intentional.
- Short single lines (buttons, labels): 1.0–1.2.
- Long-form text (articles, documentation): up to 1.75.

```css
:root {
  --leading-none:   1.0;
  --leading-tight:  1.25;
  --leading-snug:   1.375;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
  --leading-loose:  2.0;
}

body           { line-height: var(--leading-normal); }
h1, h2, h3     { line-height: var(--leading-tight); }
.lead          { line-height: var(--leading-relaxed); }
.article-body  { line-height: var(--leading-loose); }
```

## Measure (Line Length)

The optimal line length for readable text is 45–75 characters (roughly 600–800px at 16px). Use `max-width` on text containers to enforce this.

```css
.prose {
  max-width: 65ch;   /* ch unit = width of "0" character in current font */
  margin-inline: auto;
}
```

## Font Weight

Only load the font weights you actually use. Loading all weights adds unnecessary bytes.

```css
/* System font stack — no download required, great performance */
font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

/* Monospace stack */
font-family: ui-monospace, 'Cascadia Code', 'Fira Code', Consolas, monospace;
```

Common weights and their uses:
- 400 (regular) — body text
- 500 (medium) — labels, navigation links
- 600 (semibold) — subheadings, button text, form labels
- 700 (bold) — headings
- 800–900 (extrabold/black) — hero headings, large display text

## Color Theory Basics

**Hue** is the color itself (red, blue, green). **Saturation** is how vivid or gray the color is. **Lightness** is how light or dark it is. The HSL color model maps directly to these three properties, making it easier to reason about color relationships than hex:

```css
/* Same hue, decreasing saturation */
--color-blue-vivid: hsl(220, 90%, 55%);
--color-blue-mid:   hsl(220, 40%, 55%);
--color-blue-muted: hsl(220, 10%, 55%);

/* Same hue, decreasing lightness */
--color-blue-light:  hsl(220, 70%, 90%);
--color-blue-mid:    hsl(220, 70%, 55%);
--color-blue-dark:   hsl(220, 70%, 20%);
```

## Color Palette Strategy

Start with a single primary hue. Generate a scale of 10 tints and shades from near-white to near-black. Add a neutral gray scale, a semantic error red, a success green, and a warning yellow.

```css
/* Primary blue palette */
--color-blue-50:  hsl(214, 100%, 97%);
--color-blue-100: hsl(214, 95%,  93%);
--color-blue-200: hsl(213, 97%,  87%);
--color-blue-300: hsl(212, 96%,  78%);
--color-blue-400: hsl(213, 94%,  68%);
--color-blue-500: hsl(217, 91%,  60%);  /* brand color */
--color-blue-600: hsl(221, 83%,  53%);
--color-blue-700: hsl(224, 76%,  48%);
--color-blue-800: hsl(226, 71%,  40%);
--color-blue-900: hsl(224, 64%,  33%);
--color-blue-950: hsl(226, 57%,  21%);

/* Neutral gray palette */
--color-gray-50:  hsl(210, 40%, 98%);
--color-gray-100: hsl(210, 40%, 96%);
--color-gray-200: hsl(214, 32%, 91%);
--color-gray-300: hsl(213, 27%, 84%);
--color-gray-400: hsl(215, 20%, 65%);
--color-gray-500: hsl(215, 16%, 47%);
--color-gray-600: hsl(215, 19%, 35%);
--color-gray-700: hsl(215, 25%, 27%);
--color-gray-800: hsl(217, 33%, 17%);
--color-gray-900: hsl(222, 47%, 11%);
```

## Semantic Color Tokens

Never reference palette values directly in component styles. Map palette values to semantic tokens that describe their intent:

```css
:root {
  /* Backgrounds */
  --color-bg:          var(--color-gray-50);
  --color-bg-subtle:   var(--color-gray-100);
  --color-bg-inverse:  var(--color-gray-900);

  /* Text */
  --color-text:        var(--color-gray-900);
  --color-text-muted:  var(--color-gray-500);
  --color-text-inverse: var(--color-gray-50);

  /* Borders */
  --color-border:       var(--color-gray-200);
  --color-border-strong: var(--color-gray-400);

  /* Brand / Accent */
  --color-accent:       var(--color-blue-600);
  --color-accent-hover: var(--color-blue-700);
  --color-accent-light: var(--color-blue-50);

  /* Feedback */
  --color-success: hsl(142, 71%, 45%);
  --color-warning: hsl(38,  92%, 50%);
  --color-error:   hsl(0,   84%, 60%);
  --color-info:    hsl(199, 89%, 48%);
}
```

When you swap a theme, you only change the semantic tokens. The component styles remain unchanged.

## CSS Color Functions

Modern CSS color functions for accessible color manipulation:

```css
/* Lighten / darken relative to the variable — works in dark mode too */
.button:hover {
  background: color-mix(in srgb, var(--color-accent) 85%, black);
}

.button:active {
  background: color-mix(in srgb, var(--color-accent) 70%, black);
}

/* Transparent version of a token */
.focus-ring {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 30%, transparent);
}
```

## Text Rendering

```css
body {
  -webkit-font-smoothing: antialiased;    /* macOS Chrome/Safari */
  -moz-osx-font-smoothing: grayscale;    /* macOS Firefox */
  text-rendering: optimizeLegibility;    /* enables kerning and ligatures */
}
```

`text-wrap: balance` distributes text evenly across lines for headings. Prevents orphaned single words on the last line:

```css
h1, h2, h3, h4, blockquote {
  text-wrap: balance;
}
```

`text-wrap: pretty` does the same for body paragraphs, optimizing for the last few lines. Available in Chrome 117+ and Firefox 130+.

## OpenType Features

Advanced typography via `font-feature-settings` or the higher-level `font-variant-*` properties:

```css
/* Numeric styles */
.stats { font-variant-numeric: tabular-nums; }      /* fixed-width numbers for alignment */
.price { font-variant-numeric: oldstyle-nums; }     /* text figures */

/* Ligatures */
body { font-variant-ligatures: common-ligatures; }  /* fi, fl, etc. */

/* Small caps */
.label { font-variant-caps: small-caps; }

/* Direct OpenType feature access */
.mono-nums { font-feature-settings: 'tnum' 1; }
.ligatures  { font-feature-settings: 'liga' 1, 'calt' 1; }
```
