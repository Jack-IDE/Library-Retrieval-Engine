/**
 * dom_utils.js — Lightweight DOM manipulation helpers.
 *
 * Zero-dependency utilities for querying, creating, modifying, and
 * observing DOM elements without a framework.
 */

// ─── Querying ──────────────────────────────────────────────────────────────

/**
 * Query one element. Returns null if not found.
 * @param {string} selector
 * @param {Element|Document} [root=document]
 * @returns {Element|null}
 */
export function qs(selector, root = document) {
  return root.querySelector(selector);
}

/**
 * Query all matching elements as an Array.
 * @param {string} selector
 * @param {Element|Document} [root=document]
 * @returns {Element[]}
 */
export function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

/**
 * Find the closest ancestor matching selector, including the element itself.
 * Returns null if no match found.
 */
export function closest(el, selector) {
  return el ? el.closest(selector) : null;
}

// ─── Element Creation ──────────────────────────────────────────────────────

/**
 * Create an element with optional attributes and children.
 *
 * @param {string} tag - Tag name.
 * @param {Object} [attrs] - Attribute map. Use 'class' for className, 'text' for textContent.
 * @param {...(Element|string)} [children] - Child elements or text strings.
 * @returns {Element}
 *
 * @example
 * const btn = el('button', { class: 'button button--primary', type: 'button' }, 'Save');
 * const div = el('div', { class: 'card' }, el('h2', {}, 'Title'), el('p', {}, 'Body'));
 */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs)) {
    if (key === 'text') {
      node.textContent = val;
    } else if (key === 'html') {
      node.innerHTML = val;
    } else if (key.startsWith('data-')) {
      node.dataset[key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = val;
    } else if (key === 'class') {
      node.className = val;
    } else {
      node.setAttribute(key, val);
    }
  }
  for (const child of children) {
    if (child == null) continue;
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

/**
 * Parse an HTML string and return the first child element.
 * Useful for creating elements from template strings.
 */
export function fromHTML(html) {
  const tpl = document.createElement('template');
  tpl.innerHTML = html.trim();
  return tpl.content.firstElementChild;
}

// ─── DOM Manipulation ──────────────────────────────────────────────────────

/**
 * Replace element's children with new content.
 * Accepts a single element, a string, a DocumentFragment, or an array.
 */
export function setContent(el, content) {
  el.textContent = '';
  if (Array.isArray(content)) {
    const frag = document.createDocumentFragment();
    content.forEach(c => frag.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
    el.appendChild(frag);
  } else if (typeof content === 'string') {
    el.textContent = content;
  } else if (content) {
    el.appendChild(content);
  }
}

/**
 * Toggle a CSS class. Optionally force it on or off.
 * @param {Element} el
 * @param {string} cls
 * @param {boolean} [force]
 */
export function toggleClass(el, cls, force) {
  el.classList.toggle(cls, force);
}

/**
 * Show an element (removes 'hidden' attribute and display:none style).
 */
export function show(el) {
  el.removeAttribute('hidden');
  el.style.display = '';
}

/**
 * Hide an element using the 'hidden' attribute (preferred for accessibility).
 */
export function hide(el) {
  el.setAttribute('hidden', '');
}

/**
 * Insert newNode before referenceNode inside parent.
 * Or append to parent if referenceNode is null.
 */
export function insertBefore(parent, newNode, referenceNode = null) {
  parent.insertBefore(newNode, referenceNode);
}

// ─── Events ───────────────────────────────────────────────────────────────

/**
 * Add an event listener and return a cleanup function.
 *
 * @param {EventTarget} target
 * @param {string} type
 * @param {Function} handler
 * @param {Object|boolean} [options]
 * @returns {() => void} - Call to remove the listener.
 *
 * @example
 * const cleanup = on(button, 'click', handleClick);
 * // later:
 * cleanup();
 */
export function on(target, type, handler, options) {
  target.addEventListener(type, handler, options);
  return () => target.removeEventListener(type, handler, options);
}

/**
 * Event delegation — listen for events on children matching selector,
 * fired on a parent element.
 *
 * @param {Element} parent
 * @param {string} eventType
 * @param {string} selector
 * @param {Function} handler - Called with (event, matchedElement).
 * @returns {() => void} - Cleanup.
 *
 * @example
 * delegate(list, 'click', '.list-item__delete', (e, item) => removeItem(item));
 */
export function delegate(parent, eventType, selector, handler) {
  function listener(e) {
    const matched = e.target.closest(selector);
    if (matched && parent.contains(matched)) {
      handler(e, matched);
    }
  }
  parent.addEventListener(eventType, listener);
  return () => parent.removeEventListener(eventType, listener);
}

/**
 * Fire handler once, then remove the listener.
 */
export function once(target, type, handler, options) {
  const opts = typeof options === 'object'
    ? { ...options, once: true }
    : { once: true };
  target.addEventListener(type, handler, opts);
}

// ─── Timing ───────────────────────────────────────────────────────────────

/**
 * Debounce a function. Returns a new function that delays invocation
 * until after `delay` ms of inactivity.
 */
export function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Throttle a function. Ensures fn is called at most once per `limit` ms.
 */
export function throttle(fn, limit) {
  let last = 0;
  return function (...args) {
    const now = Date.now();
    if (now - last >= limit) {
      last = now;
      return fn.apply(this, args);
    }
  };
}

// ─── Viewport / Scroll ────────────────────────────────────────────────────

/**
 * Returns true if the element is in the viewport.
 * @param {Element} el
 * @param {number} [threshold=0] - 0–1, portion of element that must be visible.
 */
export function isInViewport(el, threshold = 0) {
  const rect = el.getBoundingClientRect();
  const windowH = window.innerHeight || document.documentElement.clientHeight;
  const windowW = window.innerWidth  || document.documentElement.clientWidth;
  const visibleH = Math.min(rect.bottom, windowH) - Math.max(rect.top, 0);
  const visibleW = Math.min(rect.right,  windowW) - Math.max(rect.left, 0);
  return (
    visibleH / rect.height > threshold &&
    visibleW / rect.width  > threshold
  );
}

/**
 * Smooth scroll to an element, respecting reduced motion preference.
 */
export function scrollTo(el, { offset = 0, behavior } = {}) {
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const y = el.getBoundingClientRect().top + window.scrollY - offset;
  window.scrollTo({ top: y, behavior: behavior ?? (reducedMotion ? 'instant' : 'smooth') });
}

// ─── Attributes / Data ────────────────────────────────────────────────────

/**
 * Get the value of a data attribute. Returns undefined if missing.
 */
export function data(el, key) {
  return el.dataset[key];
}

/**
 * Set ARIA attribute. Converts boolean values to 'true'/'false' strings.
 */
export function aria(el, attr, value) {
  el.setAttribute(`aria-${attr}`, typeof value === 'boolean' ? String(value) : value);
}
