/**
 * theme_switcher.js — Dark / light / system theme management.
 *
 * Reads the OS preference via matchMedia, persists the user's choice in
 * localStorage, applies a data-theme attribute to <html>, and emits events
 * when the theme changes. Zero dependencies.
 *
 * Usage:
 *   import { ThemeSwitcher } from './theme_switcher.js';
 *   const theme = new ThemeSwitcher();
 *   theme.init();
 *
 * CSS contract:
 *   :root                    { --color-bg: #fff; --color-text: #111; }
 *   [data-theme="dark"]      { --color-bg: #111; --color-text: #f9f9f9; }
 *   [data-theme="light"]     { --color-bg: #fff; --color-text: #111; }
 *
 * The script should be inlined in <head> (before body renders) to avoid
 * a flash of incorrect theme on page load. See getInlineScript() below.
 */

const STORAGE_KEY = 'theme-preference';
const THEMES      = ['light', 'dark', 'system'];
const ROOT        = document.documentElement;

export class ThemeSwitcher {
  /**
   * @param {Object} [options]
   * @param {string} [options.storageKey='theme-preference'] - localStorage key.
   * @param {string} [options.attribute='data-theme'] - HTML attribute to set on <html>.
   * @param {string} [options.defaultTheme='system'] - 'light' | 'dark' | 'system'.
   */
  constructor(options = {}) {
    this.storageKey  = options.storageKey  ?? STORAGE_KEY;
    this.attribute   = options.attribute   ?? 'data-theme';
    this.defaultTheme = options.defaultTheme ?? 'system';
    this._mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    this._listeners  = new Map();
  }

  // ─── Core ───────────────────────────────────────────────────────────────

  /**
   * Initialize the theme. Call once at app startup.
   * Applies saved preference (or OS default) to <html>.
   */
  init() {
    const saved = this._getSaved();
    this._apply(saved);

    // Re-apply when OS preference changes (only affects 'system' mode)
    this._mediaQuery.addEventListener('change', () => {
      if (this._getSaved() === 'system') {
        this._apply('system');
      }
    });

    return this;
  }

  /**
   * Get the current saved preference ('light' | 'dark' | 'system').
   * Does not reflect the resolved theme — use getResolved() for that.
   */
  getPreference() {
    return this._getSaved();
  }

  /**
   * Get the resolved (actual) theme being displayed: 'light' or 'dark'.
   * When preference is 'system', resolves from the OS setting.
   */
  getResolved() {
    const pref = this._getSaved();
    if (pref === 'system') return this._systemTheme();
    return pref;
  }

  /**
   * Set the theme preference.
   * @param {'light'|'dark'|'system'} theme
   */
  set(theme) {
    if (!THEMES.includes(theme)) {
      console.warn(`[ThemeSwitcher] Unknown theme: "${theme}". Use: ${THEMES.join(', ')}.`);
      return;
    }
    localStorage.setItem(this.storageKey, theme);
    this._apply(theme);
  }

  /** Toggle between light and dark (ignores 'system'). */
  toggle() {
    this.set(this.getResolved() === 'dark' ? 'light' : 'dark');
  }

  /** Cycle through: system → light → dark → system */
  cycle() {
    const current = this._getSaved();
    const idx = THEMES.indexOf(current);
    this.set(THEMES[(idx + 1) % THEMES.length]);
  }

  /**
   * Subscribe to theme changes.
   * @param {Function} callback - Called with { preference, resolved } on every change.
   * @returns {() => void} - Unsubscribe function.
   */
  onChange(callback) {
    const id = Symbol();
    this._listeners.set(id, callback);
    return () => this._listeners.delete(id);
  }

  // ─── Button helpers ──────────────────────────────────────────────────────

  /**
   * Connect a toggle button. Updates its aria-label and aria-pressed on change.
   *
   * @param {HTMLButtonElement} btn
   * @param {Object} [labels]
   * @param {string} [labels.light='Switch to dark mode']
   * @param {string} [labels.dark='Switch to light mode']
   */
  connectToggleButton(btn, labels = {}) {
    const update = () => {
      const resolved = this.getResolved();
      const isDark    = resolved === 'dark';
      btn.setAttribute('aria-pressed', String(isDark));
      btn.setAttribute('aria-label', isDark
        ? (labels.dark  ?? 'Switch to light mode')
        : (labels.light ?? 'Switch to dark mode')
      );
      btn.dataset.theme = resolved;
    };

    btn.addEventListener('click', () => this.toggle());
    this.onChange(update);
    update();
    return this;
  }

  /**
   * Connect a <select> element with light/dark/system options.
   * @param {HTMLSelectElement} select
   */
  connectSelect(select) {
    select.value = this._getSaved();
    select.addEventListener('change', () => this.set(select.value));
    this.onChange(({ preference }) => { select.value = preference; });
    return this;
  }

  /**
   * Connect a group of radio inputs (name="theme", values: light/dark/system).
   * @param {NodeList|Element[]} radios
   */
  connectRadios(radios) {
    const update = ({ preference }) => {
      radios.forEach(r => { r.checked = r.value === preference; });
    };

    radios.forEach(r => {
      r.addEventListener('change', () => {
        if (r.checked) this.set(r.value);
      });
    });

    this.onChange(update);
    update({ preference: this._getSaved() });
    return this;
  }

  // ─── Private ─────────────────────────────────────────────────────────────

  _getSaved() {
    const stored = localStorage.getItem(this.storageKey);
    return THEMES.includes(stored) ? stored : this.defaultTheme;
  }

  _systemTheme() {
    return this._mediaQuery.matches ? 'dark' : 'light';
  }

  _apply(preference) {
    const resolved = preference === 'system' ? this._systemTheme() : preference;

    ROOT.setAttribute(this.attribute, resolved);
    ROOT.style.colorScheme = resolved;

    // Update meta theme-color if present
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      const style = getComputedStyle(ROOT);
      const bg = style.getPropertyValue('--color-bg').trim();
      if (bg) metaTheme.setAttribute('content', bg);
    }

    // Dispatch custom event for frameworks / other scripts
    ROOT.dispatchEvent(new CustomEvent('themechange', {
      bubbles: true,
      detail: { preference, resolved },
    }));

    // Notify listeners
    this._listeners.forEach(cb => cb({ preference, resolved }));
  }
}

// ─── Inline Script ─────────────────────────────────────────────────────────

/**
 * Returns a minimal inline script string that should be placed in <head>
 * BEFORE any stylesheets. This prevents the flash of incorrect theme
 * (FOIT/FOUC) on page load by applying the theme before the browser paints.
 *
 * @param {string} [storageKey='theme-preference']
 * @param {string} [attribute='data-theme']
 * @returns {string}
 *
 * @example
 * // In your HTML generator or SSR template:
 * const script = getInlineScript();
 * // Emit: <script>/* inline script content *\/</script>
 */
export function getInlineScript(storageKey = STORAGE_KEY, attribute = 'data-theme') {
  return `
(function(){
  var key='${storageKey}',attr='${attribute}';
  var saved=localStorage.getItem(key);
  var valid=['light','dark','system'];
  var pref=valid.includes(saved)?saved:'system';
  var resolved=pref==='system'
    ?(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')
    :pref;
  document.documentElement.setAttribute(attr,resolved);
  document.documentElement.style.colorScheme=resolved;
})();
`.trim();
}

// ─── Singleton factory ────────────────────────────────────────────────────

let _instance = null;

/**
 * Get or create a singleton ThemeSwitcher instance.
 * Useful when multiple components need to access the same theme state.
 */
export function getThemeSwitcher(options) {
  if (!_instance) _instance = new ThemeSwitcher(options).init();
  return _instance;
}
