/* History is kept in this browser's localStorage and nowhere else. */

import { h, icon, riskPct, relativeTime, bandOf } from './util.js';

const KEY = 'ckdlab.history.v1';
const LIMIT = 30;

export function createHistory(schema, root, hooks) {
  let entries = read();
  let confirming = false;
  let confirmTimer;

  function read() {
    try {
      const parsed = JSON.parse(localStorage.getItem(KEY) || '[]');
      return Array.isArray(parsed) ? parsed.filter((e) => e && e.inputs && typeof e.risk === 'number') : [];
    } catch { return []; }
  }

  function write() {
    try { localStorage.setItem(KEY, JSON.stringify(entries)); } catch { /* storage full or blocked: keep working in memory */ }
    hooks.onCount(entries.length);
  }

  function add(inputs, result) {
    const top = (result.explanation ? result.explanation.contributions : []).slice(0, 3)
      .map((c) => `${c.label} ${c.display}`);
    const entry = {
      id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      ts: Date.now(), inputs, risk: result.risk, label: result.label,
      votes: result.votes, provided: result.completeness.provided, top,
    };
    const same = entries[0] && JSON.stringify(entries[0].inputs) === JSON.stringify(inputs);
    entries = [entry, ...(same ? entries.slice(1) : entries)].slice(0, LIMIT);
    write();
  }

  function remove(id) {
    entries = entries.filter((e) => e.id !== id);
    write();
    render();
  }

  function render() {
    if (!entries.length) {
      root.replaceChildren(h('p', { class: 'callout' }, icon('info', 18),
        h('span', null, 'Nothing here yet. Run an assessment and it will be listed on this page.'),
        h('a', { class: 'btn btn-small btn-light', href: '#assess' }, 'Go to Assess')));
      return;
    }
    const clear = h('button', {
      type: 'button', class: 'btn btn-small btn-light', onclick: () => {
        if (!confirming) {
          confirming = true;
          clear.textContent = 'Click again to clear everything';
          clear.classList.add('btn-danger');
          confirmTimer = setTimeout(() => { confirming = false; render(); }, 4000);
          return;
        }
        clearTimeout(confirmTimer);
        confirming = false;
        entries = [];
        write();
        render();
      },
    }, icon('trash', 16), confirming ? 'Click again to clear everything' : 'Clear history');
    if (confirming) clear.classList.add('btn-danger');

    root.replaceChildren(
      h('div', { class: 'history-head' }, h('p', { class: 'rd-muted-light' }, `${entries.length} saved, newest first. The ${LIMIT} most recent are kept.`), clear),
      h('ul', { class: 'history-list' }, entries.map((e) => {
        const band = bandOf(e.risk, schema.bands);
        return h('li', { class: 'history-item', 'data-band': band.key },
          h('div', { class: 'hi-risk' }, riskPct(e.risk)),
          h('div', { class: 'hi-main' },
            h('p', { class: 'hi-title' }, `${band.label} risk`, h('span', { class: 'hi-sub' }, e.label === 'ckd' ? 'Predicted CKD' : 'Predicted not CKD')),
            h('p', { class: 'hi-meta' }, `${e.provided} of ${schema.features.length} measurements, ${e.votes.ckd} of ${e.votes.total} models say CKD`),
            e.top.length ? h('p', { class: 'hi-top' }, `Main drivers: ${e.top.join(', ')}`) : null),
          h('div', { class: 'hi-side' },
            h('time', { datetime: new Date(e.ts).toISOString() }, relativeTime(e.ts)),
            h('div', { class: 'hi-actions' },
              h('button', { type: 'button', class: 'btn btn-small btn-light', onclick: () => hooks.onOpen(e) }, 'Open'),
              h('button', { type: 'button', class: 'icon-btn icon-btn-small', 'aria-label': 'Delete this entry', onclick: () => remove(e.id) }, icon('trash', 16)))));
      })));
  }

  hooks.onCount(entries.length);
  return { add, render };
}
