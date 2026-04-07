# Debugging and Troubleshooting

## Fixed Header Covers Anchor Targets

A fixed or sticky header often hides the top of the section you just navigated to with a fragment link like `#pricing`.

Use `scroll-margin-top` on the target elements rather than adding random spacer divs.

```css
:root {
  --header-offset: 72px;
}

section[id],
h2[id],
h3[id] {
  scroll-margin-top: calc(var(--header-offset) + var(--space-4));
}
```

If you use `scrollIntoView()`, make sure the same offset logic is honored or the browser will align the target flush to the top.

## SPA Works Locally but 404s on Refresh

A client-side router using the History API needs the server to return `index.html` for unknown application routes.

Symptoms:
- clicking links inside the app works
- directly refreshing `/dashboard/settings` returns 404

Cause:
- the browser asks the server for `/dashboard/settings`
- the server looks for a real file instead of handing the request back to the SPA entry document

Fix:
- configure the server or host to rewrite unknown routes to `index.html`
- keep actual asset requests (`.js`, `.css`, images) excluded from the catch-all rewrite

## Submit Button Reloads the Page Unexpectedly

Inside a form, `<button>` defaults to `type="submit"`.

That means buttons meant for UI actions like “open picker”, “add row”, or “toggle password visibility” will submit the form unless you explicitly set `type="button"`.

```html
<button type="button" class="field__toggle-password">Show</button>
<button type="submit">Save</button>
```

For JavaScript form handling:

```js
form.addEventListener('submit', (event) => {
  event.preventDefault();
  // validate, serialize, send request
});
```

## Modal Focus Trap Feels Broken

Common causes:
- no focusable element exists inside the modal
- focus is not moved into the dialog on open
- focus is not restored to the opener on close
- the trap list includes disabled or hidden elements
- multiple keydown handlers are attached every time the modal opens

When possible, prefer the native `<dialog>` element with `showModal()` because it handles much of this for you.

If you build a custom trap, cache the opener before opening and restore focus after close.

## Dark Theme Flashes Light Mode First

This is a startup ordering problem. The theme attribute is being set after the page has already painted.

Fix it by applying the saved theme in an inline script inside `<head>` before the CSS-visible UI renders.

```html
<script>
(() => {
  const pref = localStorage.getItem('theme-preference') || 'system';
  const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const resolved = pref === 'system' ? (dark ? 'dark' : 'light') : pref;
  document.documentElement.setAttribute('data-theme', resolved);
})();
</script>
```

The full theme manager can still initialize later. The early script exists only to prevent the flash.

## Scroll Listeners Cause Jank

Scroll handlers fire frequently. The usual problems:
- doing layout reads and writes on every scroll event
- toggling too many classes
- reading `getBoundingClientRect()` repeatedly without batching
- attaching multiple listeners during re-renders

Use a passive listener and debounce or `requestAnimationFrame` based scheduling.

```js
let ticking = false;

window.addEventListener('scroll', () => {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => {
    const y = window.scrollY;
    document.body.classList.toggle('scrolled', y > 24);
    ticking = false;
  });
}, { passive: true });
```

## Event Listener Duplication

A common SPA bug is re-binding handlers every time a view mounts without removing the old ones.

Symptoms:
- click handlers fire twice, then three times, then four times
- one modal close button suddenly closes and reopens
- analytics events duplicate

Use one of these patterns:
- event delegation from a stable parent
- teardown functions returned from setup code
- idempotent initialization guards

```js
if (!window.__navBound) {
  document.addEventListener('click', handleGlobalNavClick);
  window.__navBound = true;
}
```

That kind of guard is blunt but better than accidental listener explosions in a simple site.

## Images Overflow Their Cards

Usually one of these is missing:

```css
img {
  max-width: 100%;
  height: auto;
  display: block;
}
```

If the image must fill a fixed-height card:

```css
.card__media {
  width: 100%;
  height: 220px;
  object-fit: cover;
}
```

`object-fit: cover` crops. `contain` preserves the whole image but may letterbox.
