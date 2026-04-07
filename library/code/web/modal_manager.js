/**
 * modal_manager.js — Native <dialog>-first modal helper.
 *
 * Handles:
 * - open / close
 * - restoring focus to opener
 * - closing on backdrop click
 * - wiring close buttons with [data-close-modal]
 * - Escape dismissal via native dialog behavior
 *
 * Usage:
 *   import { bindModalTriggers, createModalController } from './modal_manager.js';
 *   bindModalTriggers();
 */

function isDialog(el) {
  return el instanceof HTMLDialogElement;
}

export function createModalController(dialog) {
  if (!isDialog(dialog)) {
    throw new TypeError('createModalController expects an HTMLDialogElement');
  }

  let opener = null;

  function open(trigger = document.activeElement) {
    opener = trigger instanceof HTMLElement ? trigger : null;
    if (!dialog.open) dialog.showModal();
  }

  function close(returnFocus = true) {
    if (dialog.open) dialog.close();
    if (returnFocus && opener) opener.focus();
  }

  dialog.addEventListener('click', (event) => {
    const rect = dialog.getBoundingClientRect();
    const clickedBackdrop = (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    );
    if (clickedBackdrop) close();
  });

  dialog.querySelectorAll('[data-close-modal]').forEach((btn) => {
    btn.addEventListener('click', () => close());
  });

  dialog.addEventListener('close', () => {
    if (opener) opener.focus();
  });

  return { open, close, dialog };
}

export function bindModalTriggers(root = document) {
  const cache = new Map();

  root.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-modal-target]');
    if (!trigger) return;

    const id = trigger.getAttribute('data-modal-target');
    if (!id) return;

    const dialog = document.getElementById(id);
    if (!isDialog(dialog)) return;

    let controller = cache.get(id);
    if (!controller) {
      controller = createModalController(dialog);
      cache.set(id, controller);
    }

    controller.open(trigger);
  });
}
