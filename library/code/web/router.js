/**
 * router.js — Lightweight client-side router using the History API.
 *
 * Handles pushState navigation, popstate (browser back/forward), link
 * interception, route parameters, query strings, and scroll restoration.
 * No dependencies. Works with any server that serves index.html for all routes.
 */

// ─── Route Matching ────────────────────────────────────────────────────────

/**
 * Compile a route pattern string into a regex and a list of param names.
 *
 * Supports:
 *   :param      — named segment, matches non-slash characters
 *   :param?     — optional named segment
 *   *           — wildcard, matches everything (greedy)
 *
 * @param {string} pattern - e.g. '/users/:id', '/posts/:slug?', '/files/*'
 * @returns {{ regex: RegExp, paramNames: string[] }}
 */
function compilePattern(pattern) {
  const paramNames = [];
  const regexStr = pattern
    .replace(/\//g, '\\/')
    .replace(/:([a-zA-Z_][a-zA-Z0-9_]*)\?/g, (_, name) => {
      paramNames.push(name);
      return '([^/]*)';
    })
    .replace(/:([a-zA-Z_][a-zA-Z0-9_]*)/g, (_, name) => {
      paramNames.push(name);
      return '([^/]+)';
    })
    .replace(/\*/g, '(.*)');
  return { regex: new RegExp(`^${regexStr}$`), paramNames };
}

/**
 * Match a pathname against a compiled route.
 * Returns a params object if matched, or null.
 */
function matchRoute(route, pathname) {
  const m = pathname.match(route.regex);
  if (!m) return null;
  const params = {};
  route.paramNames.forEach((name, i) => {
    params[name] = decodeURIComponent(m[i + 1] || '');
  });
  return params;
}

// ─── Query String ─────────────────────────────────────────────────────────

/**
 * Parse a query string into a plain object.
 * @param {string} [search=window.location.search]
 * @returns {Object}
 */
export function parseQuery(search = window.location.search) {
  const params = {};
  new URLSearchParams(search).forEach((val, key) => {
    if (key in params) {
      params[key] = Array.isArray(params[key]) ? [...params[key], val] : [params[key], val];
    } else {
      params[key] = val;
    }
  });
  return params;
}

/**
 * Serialize an object to a query string (with leading '?').
 * Returns '' if object is empty.
 */
export function buildQuery(obj) {
  const str = new URLSearchParams(
    Object.entries(obj).flatMap(([k, v]) =>
      Array.isArray(v) ? v.map(val => [k, val]) : [[k, v]]
    )
  ).toString();
  return str ? `?${str}` : '';
}

// ─── Router ───────────────────────────────────────────────────────────────

export class Router {
  /**
   * @param {Object} [options]
   * @param {string} [options.base=''] - Base path prefix for all routes (e.g. '/app').
   * @param {boolean} [options.restoreScroll=true] - Restore scroll position on popstate.
   * @param {Function} [options.onNotFound] - Called when no route matches.
   *
   * @example
   * const router = new Router();
   *
   * router.on('/', () => renderHome());
   * router.on('/about', () => renderAbout());
   * router.on('/users/:id', ({ params }) => renderUser(params.id));
   * router.on('/search', ({ query }) => renderSearch(query.q));
   * router.on('*', () => render404());
   *
   * router.start();
   */
  constructor(options = {}) {
    this.base = (options.base || '').replace(/\/$/, '');
    this.restoreScroll = options.restoreScroll !== false;
    this.onNotFound = options.onNotFound || null;
    this._routes = [];
    this._beforeEach = [];
    this._afterEach = [];
    this._scrollPositions = new Map();
    this._current = null;
    this._started = false;
  }

  /**
   * Register a route handler.
   * @param {string} pattern - Route pattern.
   * @param {Function} handler - Called with { params, query, path, href }.
   * @returns {this}
   */
  on(pattern, handler) {
    const compiled = compilePattern(this.base + pattern);
    this._routes.push({ pattern, ...compiled, handler });
    return this;
  }

  /**
   * Register a guard that runs before every navigation.
   * Return false or a string (redirect path) to cancel navigation.
   * @param {Function} fn - async (to) => false | string | undefined
   */
  beforeEach(fn) {
    this._beforeEach.push(fn);
    return this;
  }

  /** Register a hook that runs after every successful navigation. */
  afterEach(fn) {
    this._afterEach.push(fn);
    return this;
  }

  /**
   * Navigate to a path programmatically.
   * @param {string} path - Absolute path with optional query string.
   * @param {Object} [options]
   * @param {boolean} [options.replace=false] - Use replaceState instead of pushState.
   * @param {Object} [options.state] - State object to pass to pushState.
   */
  async navigate(path, { replace = false, state = {} } = {}) {
    const url = new URL(path, window.location.origin);
    await this._dispatch(url.pathname, url.search, { replace, state });
  }

  /** Replace the current history entry without adding a new one. */
  async replace(path) {
    await this.navigate(path, { replace: true });
  }

  /** Go back in history. */
  back() { history.back(); }

  /** Go forward in history. */
  forward() { history.forward(); }

  /** Start the router. Call once after registering all routes. */
  start() {
    if (this._started) return this;
    this._started = true;

    // Intercept clicks on <a> links
    document.addEventListener('click', this._handleLinkClick.bind(this));

    // Handle popstate (back/forward)
    window.addEventListener('popstate', (e) => {
      this._dispatch(
        window.location.pathname,
        window.location.search,
        { replace: true, state: e.state || {} }
      );
    });

    // Dispatch initial route
    this._dispatch(window.location.pathname, window.location.search, {
      replace: true,
      state: {},
    });

    return this;
  }

  // ─── Private ─────────────────────────────────────────────────────────────

  _handleLinkClick(e) {
    const link = e.target.closest('a[href]');
    if (!link) return;

    const href = link.getAttribute('href');

    // Skip: external, hash-only, special protocols, modifier keys, target="_blank"
    if (
      !href ||
      href.startsWith('http') ||
      href.startsWith('//') ||
      href.startsWith('mailto:') ||
      href.startsWith('tel:') ||
      href.startsWith('#') ||
      link.hasAttribute('download') ||
      link.getAttribute('target') === '_blank' ||
      link.getAttribute('router-ignore') !== null ||
      e.metaKey || e.ctrlKey || e.shiftKey || e.altKey
    ) return;

    e.preventDefault();
    const url = new URL(href, window.location.origin);
    this._dispatch(url.pathname, url.search + url.hash, { replace: false, state: {} });
  }

  async _dispatch(pathname, search = '', { replace, state }) {
    // Strip base prefix
    let path = pathname;
    if (this.base && path.startsWith(this.base)) {
      path = path.slice(this.base.length) || '/';
    }

    const query = parseQuery(search);
    const href  = window.location.origin + (this.base + path) + search;

    // Find matching route
    let matchedRoute = null;
    let params = {};
    for (const route of this._routes) {
      const p = matchRoute(route, path);
      if (p !== null) { matchedRoute = route; params = p; break; }
    }

    const to = { path, params, query, href, pattern: matchedRoute?.pattern };

    // Run before guards
    for (const guard of this._beforeEach) {
      const result = await guard(to, this._current);
      if (result === false) return;
      if (typeof result === 'string') {
        await this.navigate(result, { replace: true });
        return;
      }
    }

    // Save scroll position for current page (before navigating away)
    if (this.restoreScroll && this._current) {
      this._scrollPositions.set(this._current.href, window.scrollY);
    }

    // Update history
    const fullPath = this.base + path + search;
    if (replace || window.location.pathname + window.location.search === fullPath) {
      history.replaceState(state, '', fullPath);
    } else {
      history.pushState(state, '', fullPath);
    }

    this._current = to;

    // Invoke handler
    if (matchedRoute) {
      await matchedRoute.handler(to);
    } else if (this.onNotFound) {
      await this.onNotFound(to);
    }

    // Restore or reset scroll
    if (this.restoreScroll) {
      const saved = this._scrollPositions.get(href);
      window.scrollTo(0, saved ?? 0);
    }

    // Update active link state
    this._updateActiveLinks(path);

    // Run after hooks
    for (const hook of this._afterEach) {
      await hook(to, this._current);
    }
  }

  _updateActiveLinks(currentPath) {
    document.querySelectorAll('a[href]').forEach(link => {
      const url = new URL(link.getAttribute('href'), window.location.origin);
      const linkPath = url.pathname.replace(this.base, '') || '/';
      const isActive = linkPath === currentPath;
      link.classList.toggle('is-active', isActive);
      link.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
  }
}

// ─── Convenience factory ──────────────────────────────────────────────────

/**
 * Create and start a router in one call.
 *
 * @param {Object} routes - Map of pattern => handler function.
 * @param {Object} [options] - Router constructor options.
 * @returns {Router}
 *
 * @example
 * createRouter({
 *   '/':          () => renderHome(),
 *   '/about':     () => renderAbout(),
 *   '/posts/:id': ({ params }) => renderPost(params.id),
 *   '*':          () => render404(),
 * });
 */
export function createRouter(routes, options = {}) {
  const router = new Router(options);
  for (const [pattern, handler] of Object.entries(routes)) {
    router.on(pattern, handler);
  }
  return router.start();
}
