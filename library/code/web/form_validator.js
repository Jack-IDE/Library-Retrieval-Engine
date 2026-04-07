/**
 * form_validator.js — Client-side form validation using the Constraint Validation API.
 *
 * Disables native browser validation UI and replaces it with accessible
 * custom error messages. Supports real-time validation on blur and input,
 * custom rules, async validation, and ARIA error linking.
 */

// ─── Default Error Messages ────────────────────────────────────────────────

const DEFAULT_MESSAGES = {
  valueMissing:    (input) => `${labelText(input)} is required.`,
  typeMismatch:    (input) => {
    if (input.type === 'email') return 'Please enter a valid email address.';
    if (input.type === 'url')   return 'Please enter a valid URL.';
    return 'Please enter a valid value.';
  },
  tooShort:        (input) => `Must be at least ${input.minLength} characters.`,
  tooLong:         (input) => `Cannot exceed ${input.maxLength} characters.`,
  rangeUnderflow:  (input) => `Minimum value is ${input.min}.`,
  rangeOverflow:   (input) => `Maximum value is ${input.max}.`,
  stepMismatch:    (input) => `Must be a multiple of ${input.step}.`,
  patternMismatch: (input) => input.dataset.patternError || 'Please match the required format.',
  badInput:        ()      => 'Please enter a valid value.',
};

// ─── Helpers ──────────────────────────────────────────────────────────────

function labelText(input) {
  const label = input.labels?.[0] || document.querySelector(`label[for="${input.id}"]`);
  return label ? label.textContent.replace(/\s*\*\s*$/, '').trim() : 'This field';
}

function getOrCreateErrorEl(input, container) {
  const existingId = input.getAttribute('aria-errormessage');
  if (existingId) {
    const el = document.getElementById(existingId);
    if (el) return el;
  }
  const id = `${input.id || input.name}-error-${Math.random().toString(36).slice(2, 7)}`;
  const el = document.createElement('span');
  el.id = id;
  el.className = 'field__error';
  el.setAttribute('role', 'alert');
  el.hidden = true;
  container.appendChild(el);
  input.setAttribute('aria-errormessage', id);
  return el;
}

function linkErrorEl(input, errorEl) {
  const existing = input.getAttribute('aria-describedby') || '';
  if (!existing.includes(errorEl.id)) {
    input.setAttribute('aria-describedby', [existing, errorEl.id].filter(Boolean).join(' '));
  }
}

// ─── FieldValidator ───────────────────────────────────────────────────────

class FieldValidator {
  /**
   * @param {HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement} input
   * @param {Object} [options]
   * @param {string} [options.containerSelector='.field'] - Selector for the field wrapper.
   * @param {string} [options.errorClass='field--error'] - Class added to container on error.
   * @param {string} [options.validClass='field--valid'] - Class added to container on valid.
   * @param {Object} [options.messages] - Override default error messages.
   * @param {Object} [options.rules] - Custom sync rules: { ruleName: (value, input) => errorMsg | null }
   * @param {Object} [options.asyncRules] - Async rules: { ruleName: async (value, input) => errorMsg | null }
   */
  constructor(input, options = {}) {
    this.input = input;
    this.opts = {
      containerSelector: '.field',
      errorClass: 'field--error',
      validClass: 'field--valid',
      messages: {},
      rules: {},
      asyncRules: {},
      ...options,
    };
    this.container = input.closest(this.opts.containerSelector) || input.parentElement;
    this.errorEl = getOrCreateErrorEl(input, this.container);
    linkErrorEl(input, this.errorEl);
    this._asyncTimer = null;
    this._lastAsyncValue = Symbol('init');
  }

  /** Validate the field. Returns true if valid. */
  async validate() {
    const value = this.input.value;

    // 1. Native constraint validation
    if (!this.input.checkValidity()) {
      const validity = this.input.validity;
      for (const key of Object.keys(DEFAULT_MESSAGES)) {
        if (validity[key]) {
          const msgFn = this.opts.messages[key] || DEFAULT_MESSAGES[key];
          this._setError(typeof msgFn === 'function' ? msgFn(this.input) : msgFn);
          return false;
        }
      }
    }

    // 2. Custom sync rules
    for (const [, ruleFn] of Object.entries(this.opts.rules)) {
      const msg = ruleFn(value, this.input);
      if (msg) { this._setError(msg); return false; }
    }

    // 3. Custom async rules (debounced externally — called directly here)
    for (const [, ruleFn] of Object.entries(this.opts.asyncRules)) {
      const msg = await ruleFn(value, this.input);
      if (msg) { this._setError(msg); return false; }
    }

    this._clearError();
    return true;
  }

  /** Validate synchronously only (no async rules). */
  validateSync() {
    const value = this.input.value;

    if (!this.input.checkValidity()) {
      const validity = this.input.validity;
      for (const key of Object.keys(DEFAULT_MESSAGES)) {
        if (validity[key]) {
          const msgFn = this.opts.messages[key] || DEFAULT_MESSAGES[key];
          this._setError(typeof msgFn === 'function' ? msgFn(this.input) : msgFn);
          return false;
        }
      }
    }

    for (const [, ruleFn] of Object.entries(this.opts.rules)) {
      const msg = ruleFn(value, this.input);
      if (msg) { this._setError(msg); return false; }
    }

    this._clearError();
    return true;
  }

  _setError(message) {
    this.container.classList.add(this.opts.errorClass);
    this.container.classList.remove(this.opts.validClass);
    this.input.setAttribute('aria-invalid', 'true');
    this.errorEl.textContent = message;
    this.errorEl.hidden = false;
  }

  _clearError() {
    this.container.classList.remove(this.opts.errorClass);
    this.container.classList.add(this.opts.validClass);
    this.input.setAttribute('aria-invalid', 'false');
    this.errorEl.textContent = '';
    this.errorEl.hidden = true;
  }

  reset() {
    this.container.classList.remove(this.opts.errorClass, this.opts.validClass);
    this.input.removeAttribute('aria-invalid');
    this.errorEl.textContent = '';
    this.errorEl.hidden = true;
  }
}

// ─── FormValidator ────────────────────────────────────────────────────────

export class FormValidator {
  /**
   * Attach validation to a <form> element.
   *
   * @param {HTMLFormElement} form
   * @param {Object} [options]
   * @param {Object} [options.fields] - Per-field validator options, keyed by input name.
   * @param {Function} [options.onSubmit] - Called with validated FormData on valid submit.
   * @param {Function} [options.onInvalid] - Called when submit is blocked by validation errors.
   * @param {boolean} [options.validateOnBlur=true] - Validate fields on blur.
   * @param {boolean} [options.validateOnInput=true] - Re-validate dirty fields on input.
   *
   * @example
   * const v = new FormValidator(document.querySelector('form'), {
   *   fields: {
   *     username: {
   *       rules: {
   *         noSpaces: (val) => /\s/.test(val) ? 'Username cannot contain spaces.' : null,
   *       },
   *       asyncRules: {
   *         unique: async (val) => {
   *           const res = await fetch(`/api/check-username?q=${val}`);
   *           const { available } = await res.json();
   *           return available ? null : 'This username is already taken.';
   *         },
   *       },
   *     },
   *   },
   *   onSubmit: (data) => console.log(Object.fromEntries(data)),
   * });
   */
  constructor(form, options = {}) {
    this.form = form;
    this.opts = {
      validateOnBlur: true,
      validateOnInput: true,
      fields: {},
      onSubmit: null,
      onInvalid: null,
      ...options,
    };

    this.form.setAttribute('novalidate', '');
    this._validators = new Map();
    this._dirty = new Set();
    this._submitBtn = null;
    this._init();
  }

  _init() {
    const inputs = Array.from(
      this.form.querySelectorAll('input, select, textarea')
    ).filter(el => !el.disabled && el.type !== 'hidden' && el.type !== 'submit');

    for (const input of inputs) {
      const fieldOpts = this.opts.fields[input.name] || {};
      this._validators.set(input, new FieldValidator(input, fieldOpts));

      if (this.opts.validateOnBlur) {
        input.addEventListener('blur', () => {
          this._dirty.add(input);
          this._validators.get(input).validateSync();
          // Trigger async validation after blur
          if (Object.keys(fieldOpts.asyncRules || {}).length) {
            this._validators.get(input).validate();
          }
        });
      }

      if (this.opts.validateOnInput) {
        input.addEventListener('input', () => {
          if (this._dirty.has(input)) {
            this._validators.get(input).validateSync();
          }
        });
      }
    }

    this._submitBtn = this.form.querySelector('[type="submit"]');

    this.form.addEventListener('submit', async (e) => {
      e.preventDefault();
      this._setSubmitting(true);

      // Mark all fields dirty and run full validation
      const results = await Promise.all(
        Array.from(this._validators.entries()).map(([input, v]) => {
          this._dirty.add(input);
          return v.validate();
        })
      );

      this._setSubmitting(false);
      const allValid = results.every(Boolean);

      if (!allValid) {
        const firstInvalid = Array.from(this._validators.keys())
          .find(input => input.getAttribute('aria-invalid') === 'true');
        firstInvalid?.focus();
        this.opts.onInvalid?.();
        return;
      }

      this.opts.onSubmit?.(new FormData(this.form));
    });
  }

  _setSubmitting(loading) {
    if (!this._submitBtn) return;
    this._submitBtn.disabled = loading;
    this._submitBtn.classList.toggle('button--loading', loading);
    this._submitBtn.setAttribute('aria-busy', String(loading));
  }

  /** Programmatically validate all fields. Returns true if all valid. */
  async validate() {
    const results = await Promise.all(
      Array.from(this._validators.values()).map(v => v.validate())
    );
    return results.every(Boolean);
  }

  /** Reset validation state on all fields. */
  reset() {
    this._dirty.clear();
    this._validators.forEach(v => v.reset());
    this.form.reset();
  }

  /** Set a server-side error on a specific field by name. */
  setFieldError(name, message) {
    const input = this.form.elements[name];
    if (!input) return;
    const validator = this._validators.get(input);
    if (validator) validator._setError(message);
  }
}

// ─── Standalone Helpers ───────────────────────────────────────────────────

/** Common custom rule functions for use in the `rules` option. */
export const rules = {
  /** Minimum character count (after trim). */
  minLength: (min) => (val) =>
    val.trim().length < min ? `Must be at least ${min} characters.` : null,

  /** Maximum character count (after trim). */
  maxLength: (max) => (val) =>
    val.trim().length > max ? `Cannot exceed ${max} characters.` : null,

  /** Value must match another field's value. */
  matches: (otherName, label) => (val, input) => {
    const other = input.form?.elements[otherName];
    return other && val !== other.value ? `Must match ${label}.` : null;
  },

  /** Validate against a regex pattern. */
  pattern: (regex, message) => (val) =>
    val && !regex.test(val) ? message : null,

  /** Require at least one checked checkbox in a group. */
  requireOne: (groupName) => (_, input) => {
    const checked = input.form?.querySelectorAll(`[name="${groupName}"]:checked`);
    return checked?.length === 0 ? 'Please select at least one option.' : null;
  },

  /** File type validation. */
  fileType: (acceptedTypes) => (_, input) => {
    if (!input.files?.length) return null;
    const file = input.files[0];
    const ok = acceptedTypes.some(type =>
      type.startsWith('.') ? file.name.endsWith(type) : file.type === type
    );
    return ok ? null : `File must be: ${acceptedTypes.join(', ')}.`;
  },

  /** File size validation. */
  fileSize: (maxBytes) => (_, input) => {
    if (!input.files?.length) return null;
    return input.files[0].size > maxBytes
      ? `File must be smaller than ${Math.round(maxBytes / 1024 / 1024)}MB.`
      : null;
  },
};
