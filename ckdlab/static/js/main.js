/* Entry point. Wires the form, the readout, the other views and the router together. */

import { $, $$, h, icon, toast, debounce, reducedMotion } from './util.js';
import { api } from './api.js';
import { createForm } from './form.js';
import { createReadout } from './readout.js';
import { createModelsView } from './models.js';
import { createBatchView } from './batch.js';
import { createHistory } from './history.js';
import { buildReport, summaryText } from './report.js';

const VIEWS = ['assess', 'models', 'batch', 'history', 'about'];
const TITLES = { assess: 'Assess', models: 'Models', batch: 'Batch', history: 'History', about: 'About' };

function initTheme() {
  const button = $('#theme-toggle');
  const root = document.documentElement;
  const paint = () => {
    const dark = root.dataset.theme === 'dark';
    button.replaceChildren(icon(dark ? 'sun' : 'moon', 19));
    button.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
  };
  button.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('ckdlab.theme', next); } catch { /* storage blocked */ }
    paint();
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
    let saved = null;
    try { saved = localStorage.getItem('ckdlab.theme'); } catch { /* ignore */ }
    if (!saved) { root.dataset.theme = event.matches ? 'dark' : 'light'; paint(); }
  });
  paint();
}

function initRouter(onShow) {
  const current = () => location.hash.replace(/^#\/?/, '') || 'assess';
  const show = (requested, { moveFocus = false } = {}) => {
    const name = VIEWS.includes(requested) ? requested : 'assess';
    $$('.view').forEach((view) => { view.hidden = view.dataset.view !== name; });
    $$('[data-nav]').forEach((link) => {
      if (link.dataset.nav === name) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    document.title = name === 'assess' ? 'CKD Risk Lab' : `${TITLES[name]} - CKD Risk Lab`;
    onShow(name);
    if (moveFocus) {
      window.scrollTo(0, 0);
      $(`#view-${name} h1`)?.focus({ preventScroll: true });
    }
  };
  window.addEventListener('hashchange', () => show(current(), { moveFocus: true }));
  show(current());
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = h('textarea', { 'aria-hidden': 'true', style: { position: 'fixed', opacity: '0' } }, text);
    document.body.append(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }
  toast('Summary copied to the clipboard');
}

function fatal(error) {
  $('#main').replaceChildren(h('div', { class: 'fatal' },
    h('h1', null, 'The model server is not responding'),
    h('p', null, error.message),
    h('button', { type: 'button', class: 'btn btn-primary', onclick: () => location.reload() }, 'Try again')));
}

async function boot() {
  initTheme();

  let schema;
  try {
    schema = await api.schema();
  } catch (error) {
    fatal(error);
    return;
  }

  $('#disclaimer').textContent = schema.disclaimer;
  $('#band-legend').replaceChildren(...schema.bands.map((band) => h('li', null,
    h('span', { class: `swatch band-${band.key}`, 'aria-hidden': 'true' }),
    h('span', null, h('strong', null, band.label), ` ${Math.round(band.from * 100)}% to ${Math.round(band.to * 100)}%`))));

  const state = { seq: 0, controller: null, inputs: null };
  const debouncedLive = debounce(() => assess('live'), 450);

  const readout = createReadout($('#readout'), schema, {
    onApplyWhatIf: (key, value) => { form.setValue(key, value); assess('manual'); },
    onPrint: () => {
      if (!readout.result) return;
      buildReport($('#report'), schema, readout.result, state.inputs);
      window.print();
    },
    onCopy: () => { if (readout.result) copyText(summaryText(schema, readout.result)); },
  });

  const history = createHistory(schema, $('#history-body'), {
    onCount: (count) => {
      const badge = $('#history-count');
      badge.hidden = count === 0;
      badge.textContent = String(count);
    },
    onOpen: (entry) => {
      form.setInputs(entry.inputs, { silent: true });
      location.hash = '#assess';
      assess('history');
    },
  });

  const form = createForm($('#patient-form'), schema, {
    onChange: ({ source }) => {
      if (source !== 'user') return;
      readout.clearError();
      if (!readout.hasResult) return;
      const ready = form.isValid() && form.providedCount() >= schema.minFields;
      if (form.live && ready) {
        readout.setStale(false);
        debouncedLive();
      } else {
        debouncedLive.cancel();
        readout.setStale(true);
      }
    },
    onSubmit: () => assess('manual'),
    onSample: () => assess('sample'),
    onClear: () => {
      debouncedLive.cancel();
      state.controller?.abort();
      state.inputs = null;
      readout.showEmpty();
    },
    onLiveChange: (on) => {
      if (on && readout.hasResult && form.isValid() && form.providedCount() >= schema.minFields) assess('live');
    },
  });

  async function assess(source) {
    debouncedLive.cancel();
    if (!form.isValid() || form.providedCount() < schema.minFields) return;
    const inputs = form.getInputs();
    state.seq += 1;
    const mine = state.seq;
    state.controller?.abort();
    state.controller = new AbortController();
    readout.clearError();
    readout.setBusy(true);
    if (source !== 'live') form.setBusy(true);
    try {
      const result = await api.predict(inputs, { signal: state.controller.signal });
      if (mine !== state.seq) return;
      state.inputs = inputs;
      readout.showResult(result, inputs);
      if (source === 'manual') history.add(inputs, result);
      if (source !== 'live' && window.matchMedia('(max-width: 1099px)').matches) {
        $('#readout').scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
      }
    } catch (error) {
      if (error.name === 'AbortError' || mine !== state.seq) return;
      if (error.status === 422 && error.details) form.markErrors(error.details);
      readout.showError(error.message);
    } finally {
      if (mine === state.seq) { readout.setBusy(false); form.setBusy(false); }
    }
  }

  const models = createModelsView($('#models-body'), $('#models-lede'));
  models.setLabels(schema.features);
  createBatchView($('#batch-body'), schema);

  initRouter((name) => {
    if (name === 'models') models.load();
    if (name === 'history') history.render();
  });
}

boot();
