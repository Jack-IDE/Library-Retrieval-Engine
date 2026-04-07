/**
 * sticky_nav.js — Hide-on-scroll sticky header helper.
 *
 * Adds and removes classes on a header element based on scroll direction
 * and threshold. Uses requestAnimationFrame scheduling to avoid janky
 * scroll work.
 *
 * CSS contract example:
 * .site-header { position: sticky; top: 0; transition: transform 180ms ease-out; }
 * .site-header.is-hidden { transform: translateY(-100%); }
 * .site-header.is-elevated { box-shadow: var(--shadow-md); }
 */

export function initStickyNav(header, options = {}) {
  if (!header) throw new TypeError('initStickyNav requires a header element');

  const threshold = options.threshold ?? 24;
  const hideAfter = options.hideAfter ?? 80;
  let lastY = window.scrollY;
  let ticking = false;

  function update() {
    const y = window.scrollY;
    const goingDown = y > lastY;
    const delta = Math.abs(y - lastY);

    header.classList.toggle('is-elevated', y > threshold);

    if (y <= threshold) {
      header.classList.remove('is-hidden');
    } else if (goingDown && y > hideAfter && delta > 4) {
      header.classList.add('is-hidden');
    } else if (!goingDown && delta > 4) {
      header.classList.remove('is-hidden');
    }

    lastY = y;
    ticking = false;
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(update);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  update();

  return () => window.removeEventListener('scroll', onScroll);
}
