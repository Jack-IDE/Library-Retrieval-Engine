# Forms and Inputs

## Input Field Anatomy

A well-built form field has five parts: label, optional hint text, the input itself, error state, and valid state. Every part serves a distinct role.

```html
<div class="field" id="field-email">
  <label class="field__label" for="email">
    Email address
    <span class="field__required" aria-hidden="true">*</span>
  </label>
  <span class="field__hint" id="email-hint">We'll send your receipt here.</span>
  <input
    class="field__input"
    type="email"
    id="email"
    name="email"
    autocomplete="email"
    required
    aria-required="true"
    aria-describedby="email-hint email-error"
    placeholder="you@example.com"
  >
  <span class="field__error" id="email-error" role="alert" hidden></span>
</div>
```

```css
.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field__label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text);
}

.field__required { color: #dc2626; margin-left: 2px; }

.field__hint {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.field__input {
  padding: var(--space-2) var(--space-3);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--color-text);
  background: var(--color-bg);
  width: 100%;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast);
}

.field__input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 25%, transparent);
}

.field__input:invalid:not(:placeholder-shown) {
  border-color: #dc2626;
}

/* Error state applied via JS */
.field--error .field__input {
  border-color: #dc2626;
}

.field__error {
  font-size: var(--text-sm);
  color: #dc2626;
  font-weight: 500;
}
```

## Input Types and When to Use Them

```html
<!-- Text — generic single-line text -->
<input type="text" autocomplete="name">

<!-- Email — shows @ keyboard on mobile, validates format -->
<input type="email" autocomplete="email">

<!-- Password — masked, triggers password manager -->
<input type="password" autocomplete="current-password">
<input type="password" autocomplete="new-password">  <!-- for registration -->

<!-- Number — numeric keyboard on mobile, spinner arrows -->
<input type="number" min="1" max="99" step="1">

<!-- Tel — telephone keyboard on mobile, no validation -->
<input type="tel" autocomplete="tel">

<!-- URL — shows .com button on mobile, validates format -->
<input type="url" autocomplete="url">

<!-- Search — shows search keyboard on mobile, clear button -->
<input type="search">

<!-- Date — native date picker (styling varies wildly by browser) -->
<input type="date" min="2024-01-01" max="2030-12-31">

<!-- Range — slider -->
<input type="range" min="0" max="100" step="5" value="50">

<!-- Color — native color picker -->
<input type="color" value="#3b82f6">

<!-- File -->
<input type="file" accept="image/*,.pdf" multiple>

<!-- Checkbox — use for independent boolean choices -->
<input type="checkbox" id="agree" name="agree" value="yes">

<!-- Radio — use for mutually exclusive options in a group -->
<input type="radio" id="plan-free" name="plan" value="free">
<input type="radio" id="plan-pro"  name="plan" value="pro">

<!-- Hidden — submitted with form but not shown -->
<input type="hidden" name="csrf_token" value="abc123">
```

## Custom Checkbox and Radio

Native checkboxes and radios are hard to style. The standard technique is to visually hide the native input while keeping it keyboard and screen-reader accessible, then style a custom indicator via CSS:

```html
<label class="checkbox">
  <input class="checkbox__input" type="checkbox" name="subscribe">
  <span class="checkbox__box" aria-hidden="true"></span>
  <span class="checkbox__label">Subscribe to newsletter</span>
</label>
```

```css
.checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
}

.checkbox__input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  margin: -1px;
}

.checkbox__box {
  width: 18px;
  height: 18px;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  flex-shrink: 0;
  transition: background var(--duration-fast), border-color var(--duration-fast);
  position: relative;
}

/* Checkmark via pseudo-element */
.checkbox__box::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 5px;
  width: 5px;
  height: 9px;
  border: 2px solid white;
  border-top: none;
  border-left: none;
  transform: rotate(45deg) scale(0);
  transition: transform var(--duration-fast);
}

.checkbox__input:checked ~ .checkbox__box {
  background: var(--color-accent);
  border-color: var(--color-accent);
}

.checkbox__input:checked ~ .checkbox__box::after {
  transform: rotate(45deg) scale(1);
}

/* Focus ring on the visual box */
.checkbox__input:focus-visible ~ .checkbox__box {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
```

## Select Dropdown

The native `<select>` element has limited styling support. Replace the arrow with a custom SVG:

```css
.select-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
}

.select-wrapper::after {
  content: '';
  position: absolute;
  right: var(--space-3);
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid var(--color-text-muted);
  pointer-events: none;
}

select {
  appearance: none;
  width: 100%;
  padding: var(--space-2) var(--space-8) var(--space-2) var(--space-3);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-base);
  color: var(--color-text);
  cursor: pointer;
}

select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 25%, transparent);
}
```

## Textarea

```html
<label for="message">Message</label>
<textarea
  id="message"
  name="message"
  rows="5"
  maxlength="1000"
  placeholder="Write your message here..."
  aria-describedby="message-count"
></textarea>
<span id="message-count" aria-live="polite">0 / 1000</span>
```

```css
textarea {
  resize: vertical;      /* allow vertical resize only */
  min-height: 100px;
  font-family: inherit;  /* textareas do not inherit font by default */
  line-height: var(--leading-normal);
}
```

```javascript
const textarea = document.getElementById('message');
const counter  = document.getElementById('message-count');
textarea.addEventListener('input', () => {
  counter.textContent = `${textarea.value.length} / ${textarea.maxLength}`;
});
```

## Form Validation

Use the Constraint Validation API with custom error messages rather than default browser UI:

```javascript
class FormValidator {
  constructor(form) {
    this.form = form;
    this.form.setAttribute('novalidate', '');
    this.form.addEventListener('submit', (e) => this.handleSubmit(e));
    this.form.querySelectorAll('input, select, textarea').forEach(input => {
      input.addEventListener('blur', () => this.validateField(input));
      input.addEventListener('input', () => {
        if (input.closest('.field--error')) this.validateField(input);
      });
    });
  }

  validateField(input) {
    const field = input.closest('.field');
    const errorEl = field.querySelector('.field__error');
    let message = '';

    if (input.validity.valueMissing) {
      message = `${input.labels[0]?.textContent.replace('*','').trim()} is required.`;
    } else if (input.validity.typeMismatch && input.type === 'email') {
      message = 'Please enter a valid email address.';
    } else if (input.validity.tooShort) {
      message = `Must be at least ${input.minLength} characters.`;
    } else if (input.validity.tooLong) {
      message = `Cannot exceed ${input.maxLength} characters.`;
    } else if (input.validity.rangeUnderflow) {
      message = `Minimum value is ${input.min}.`;
    } else if (input.validity.rangeOverflow) {
      message = `Maximum value is ${input.max}.`;
    } else if (input.validity.patternMismatch && input.dataset.patternError) {
      message = input.dataset.patternError;
    }

    const isInvalid = Boolean(message);
    field.classList.toggle('field--error', isInvalid);
    input.setAttribute('aria-invalid', isInvalid ? 'true' : 'false');
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.hidden = !isInvalid;
    }
    return !isInvalid;
  }

  handleSubmit(e) {
    const inputs = this.form.querySelectorAll('input, select, textarea');
    const allValid = Array.from(inputs).map(i => this.validateField(i)).every(Boolean);
    if (!allValid) {
      e.preventDefault();
      this.form.querySelector('[aria-invalid="true"]')?.focus();
    }
  }
}

new FormValidator(document.querySelector('form'));
```

## Password Visibility Toggle

```html
<div class="field field--password">
  <label for="pwd">Password</label>
  <div class="field__input-wrapper">
    <input type="password" id="pwd" class="field__input" autocomplete="current-password">
    <button type="button" class="field__toggle-btn" aria-label="Show password" aria-pressed="false">
      <!-- Eye icon SVG -->
    </button>
  </div>
</div>
```

```javascript
document.querySelector('.field__toggle-btn').addEventListener('click', function() {
  const input = document.getElementById('pwd');
  const showing = input.type === 'text';
  input.type = showing ? 'password' : 'text';
  this.setAttribute('aria-pressed', String(!showing));
  this.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
});
```

## Search with Autocomplete

```html
<div class="search" role="combobox" aria-expanded="false" aria-haspopup="listbox">
  <input
    class="search__input"
    type="search"
    aria-label="Search"
    aria-autocomplete="list"
    aria-controls="search-results"
    autocomplete="off"
    spellcheck="false"
  >
  <ul class="search__results" id="search-results" role="listbox" hidden>
    <!-- populated dynamically -->
  </ul>
</div>
```
