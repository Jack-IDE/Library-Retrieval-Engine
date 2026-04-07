# CSS Layout Guide

## The Box Model

Every HTML element is a rectangular box. The box has four layers: content, padding, border, and margin. Understanding which layer affects which dimension is fundamental.

With the default `box-sizing: content-box`, `width` and `height` set the content area only. Padding and border are added on top, making the rendered element wider and taller than the declared width. This is counterintuitive.

With `box-sizing: border-box`, `width` and `height` include padding and border. The content area shrinks to fit. This is almost always what you want. Apply it globally:

```css
*, *::before, *::after {
  box-sizing: border-box;
}
```

Margin is always outside the border and is never included in `width` or `height` calculations regardless of `box-sizing`.

## Flexbox

Flexbox is a one-dimensional layout system. It arranges items along a single axis — either a row or a column. Use it for components: navigation bars, button groups, card layouts within a row, centering a single element.

```css
.container {
  display: flex;
  flex-direction: row;        /* row | column | row-reverse | column-reverse */
  justify-content: flex-start; /* main axis alignment */
  align-items: stretch;       /* cross axis alignment */
  flex-wrap: nowrap;          /* wrap | nowrap */
  gap: 1rem;                  /* space between items */
}
```

Centering an element both horizontally and vertically:

```css
.parent {
  display: flex;
  justify-content: center;
  align-items: center;
}
```

Flexbox item properties control how individual children behave:

```css
.item {
  flex-grow: 0;    /* how much extra space item takes */
  flex-shrink: 1;  /* how much item shrinks when space is tight */
  flex-basis: auto; /* initial size before growing/shrinking */
}

/* Shorthand: grow shrink basis */
.item { flex: 1 1 0; }    /* grows and shrinks equally, starts at 0 width */
.item { flex: 0 0 200px; } /* fixed 200px, never grows or shrinks */
.item { flex: 1; }         /* shorthand for flex: 1 1 0 */
```

`align-self` overrides `align-items` for a single item. `order` changes visual order without changing DOM order — use with caution because it breaks keyboard navigation order.

## CSS Grid

Grid is a two-dimensional layout system. It places items in rows and columns simultaneously. Use it for page-level layouts: the overall page structure, complex card grids, dashboard layouts, image galleries.

```css
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr); /* three equal columns */
  grid-template-rows: auto;
  gap: 1.5rem;
}
```

Common column patterns:

```css
/* Two columns: sidebar + main */
grid-template-columns: 250px 1fr;

/* Three equal columns */
grid-template-columns: repeat(3, 1fr);

/* Responsive: as many columns as fit, minimum 200px wide */
grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));

/* Holy grail layout: header, sidebar, main, aside, footer */
grid-template-areas:
  "header header  header"
  "sidebar main   aside"
  "footer footer  footer";
```

Place items into named grid areas:

```css
.header  { grid-area: header; }
.sidebar { grid-area: sidebar; }
.main    { grid-area: main; }
```

Span items across multiple tracks:

```css
.featured-card {
  grid-column: span 2;  /* spans two columns */
  grid-row: span 2;     /* spans two rows */
}
```

## When to Use Flexbox vs Grid

Use flexbox when the layout is driven by the content size — you have a list of items and want them to fill available space naturally. Navigation bars, button rows, tag lists.

Use grid when the layout is driven by a defined structure — you have a specific column and row structure the content must conform to. Page layouts, card grids, form layouts with label+input pairs in alignment.

They compose well. Use grid for the page shell, flexbox inside each card or navigation component.

## Positioning

`position: static` is the default. Elements flow in document order.

`position: relative` does not remove the element from flow. It offsets the element from its natural position using `top`, `right`, `bottom`, `left`. The original space is preserved. Mostly used to create a positioning context for absolutely positioned children.

`position: absolute` removes the element from flow. It is placed relative to its nearest ancestor with `position` set to anything other than `static`. If no such ancestor exists, it is placed relative to the initial containing block (the viewport).

`position: fixed` removes the element from flow. It is placed relative to the viewport and stays there during scroll. Used for sticky headers, floating action buttons, cookie banners.

`position: sticky` is a hybrid. The element stays in flow and scrolls normally until it reaches a threshold (set with `top`, `bottom`, etc.), then it sticks in place like `fixed` within its parent's bounds. Excellent for table headers and section headings that should remain visible while scrolling through their section.

```css
/* Sticky table header */
thead th {
  position: sticky;
  top: 0;
  background: white;
  z-index: 1;
}
```

## The Stacking Context

When elements overlap, the browser uses the stacking context to decide which is drawn on top. A new stacking context is created by: `position` with a `z-index` other than `auto`, `opacity` less than 1, `transform`, `filter`, `will-change`, `isolation: isolate`.

Within a stacking context, child elements are painted in this order: background and borders of the stacking context element, negative z-index children, block elements in flow, float elements, inline elements, positioned children with z-index 0, positioned children with positive z-index.

`z-index` only works between siblings in the same stacking context. A child with `z-index: 9999` inside a parent stacking context with `z-index: 1` cannot appear above a sibling stacking context with `z-index: 2`. This is the most common source of z-index confusion.

## Overflow and Scroll

`overflow: hidden` clips content that exceeds the element's box. Also establishes a new block formatting context, which prevents margin collapse and contains floats.

`overflow: auto` shows a scrollbar only when content overflows. `overflow: scroll` always shows scrollbars even when not needed.

`overflow-x` and `overflow-y` control axes independently. Setting `overflow-x: hidden` on a parent while intending to use `overflow-y: scroll` can cause the scrollbar to be hidden — set both explicitly.

`overscroll-behavior: contain` prevents scroll from propagating to the parent when a scrollable child reaches its end. Essential for modal dialogs and sidebars with their own scroll.

```css
.modal-body {
  overflow-y: auto;
  overscroll-behavior: contain;
  max-height: 70vh;
}
```
