/* Models view. Everything shown here is read from /api/models, i.e. from the cross-validation
   that ran at training time. Nothing is hard-coded. */

import { h, icon, fmt } from './util.js';
import { api } from './api.js';
import { rocChart } from './charts.js';

const COLUMNS = [
  { key: 'name', label: 'Model' },
  { key: 'accuracy', label: 'Accuracy', tip: 'Share of all patients classified correctly.' },
  { key: 'precision', label: 'Precision', tip: 'Of the patients flagged as CKD, the share who really have it.' },
  { key: 'recall', label: 'Recall', tip: 'Of the patients who have CKD, the share that was caught.' },
  { key: 'f1', label: 'F1', tip: 'Balance of precision and recall.' },
  { key: 'roc_auc', label: 'ROC AUC', tip: 'How well the risk score ranks CKD patients above the others (1 is perfect, 0.5 is a coin flip).' },
];

const pct = (v, digits = 1) => `${(v * 100).toFixed(digits)}%`;
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function section(title, ...children) {
  return h('section', { class: 'panel' }, h('h2', null, title), ...children);
}

export function createModelsView(bodyEl, ledeEl) {
  let loaded = false;
  let roc = null;

  async function load() {
    if (loaded) return;
    try {
      const data = await api.models();
      loaded = true;
      render(data);
    } catch (err) {
      ledeEl.textContent = 'The evaluation could not be loaded.';
      bodyEl.replaceChildren(h('p', { class: 'callout callout-warn' }, icon('warn', 18), h('span', null, err.message)));
    }
  }

  function render(data) {
    roc?.destroy();
    const { dataset, evaluation } = data;
    if (!data.models.length || !evaluation) {
      ledeEl.textContent = 'This model was trained without an evaluation.';
      bodyEl.replaceChildren(h('p', { class: 'callout' }, icon('info', 18),
        h('span', null, 'Run python -m ckdlab.train to generate cross-validated scores, ROC curves and feature importance.')));
      return;
    }

    ledeEl.textContent = `Scores come from ${evaluation.folds}-fold cross-validation, repeated ${plural(evaluation.repeats, 'time')}, on ${dataset.rows} patients. Every patient is scored by models that never saw them.`;

    const state = { selected: 'ensemble', sortKey: null, dir: 'desc', zoom: false };
    const byKey = new Map(data.models.map((m) => [m.key, m]));

    /* --------------------------------------------------------------- table */
    const tbody = h('tbody');
    const headCells = new Map();
    const table = h('table', { class: 'table models-table' },
      h('caption', { class: 'sr-only' }, 'Cross-validated performance of each model. Select a row to compare it.'),
      h('thead', null, h('tr', null, COLUMNS.map((col) => {
        const th = h('th', { scope: 'col', class: col.key === 'name' ? 'col-name' : 'col-num', 'aria-sort': 'none' },
          h('button', { type: 'button', class: 'th-btn', title: col.tip || 'Sort by name', onclick: () => sortBy(col.key) }, col.label, icon('chevron', 13)));
        headCells.set(col.key, th);
        return th;
      }))), tbody);

    function ordered() {
      const rows = [...data.models];
      if (!state.sortKey) return [...rows.filter((m) => m.is_ensemble), ...rows.filter((m) => !m.is_ensemble)];
      const dir = state.dir === 'asc' ? 1 : -1;
      return rows.sort((a, b) => (state.sortKey === 'name' ? a.name.localeCompare(b.name) : a[state.sortKey] - b[state.sortKey]) * dir);
    }

    function renderTable() {
      const rows = ordered();
      const best = {};
      COLUMNS.slice(1).forEach((col) => {
        const top = Math.max(...rows.map((m) => m[col.key]));
        const winners = rows.filter((m) => Math.abs(m[col.key] - top) < 1e-9).length;
        best[col.key] = winners <= rows.length / 2 ? top : null;
      });
      headCells.forEach((th, key) => th.setAttribute('aria-sort', state.sortKey === key ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none'));
      tbody.replaceChildren(...rows.map((m) => h('tr', { class: `${m.is_ensemble ? 'is-ensemble ' : ''}${m.key === state.selected ? 'is-selected' : ''}` },
        h('th', { scope: 'row', class: 'col-name' },
          h('button', { type: 'button', class: 'row-btn', 'aria-pressed': String(m.key === state.selected), title: m.blurb, onclick: () => select(m.key) },
            h('span', { class: 'model-name' }, m.name), h('span', { class: 'model-family' }, m.family))),
        ...COLUMNS.slice(1).map((col) => {
          const text = col.key === 'roc_auc' ? m[col.key].toFixed(3) : pct(m[col.key]);
          return h('td', { class: `col-num${best[col.key] !== null && Math.abs(m[col.key] - best[col.key]) < 1e-9 ? ' best' : ''}` },
            text, col.key === 'accuracy' && m.accuracy_std !== undefined ? h('small', null, `\u00b1${(m.accuracy_std * 100).toFixed(1)}`) : null);
        }))));
    }

    function sortBy(key) {
      if (state.sortKey === key) state.dir = state.dir === 'desc' ? 'asc' : 'desc';
      else { state.sortKey = key; state.dir = key === 'name' ? 'asc' : 'desc'; }
      renderTable();
    }

    /* ---------------------------------------------------- confusion matrix */
    const matrix = h('div', { class: 'matrix' });
    const matrixNote = h('p', { class: 'rd-muted-light' });
    const matrixTitle = h('h3', null);

    function renderMatrix() {
      const m = byKey.get(state.selected);
      const { tp, fn, fp, tn } = m.confusion;
      const ckd = tp + fn;
      const healthy = fp + tn;
      const cell = (label, count, share, good) => h('div', { class: `mx-cell ${good ? 'good' : 'bad'}`, style: { '--k': String(Math.min(1, share * 1.2 + 0.08)) } },
        h('strong', null, fmt(count)), h('span', null, label));
      matrixTitle.textContent = `Confusion matrix: ${m.name}`;
      matrix.replaceChildren(
        h('span', { class: 'mx-corner' }),
        h('span', { class: 'mx-col' }, 'Predicted CKD'), h('span', { class: 'mx-col' }, 'Predicted not CKD'),
        h('span', { class: 'mx-row' }, 'Actually CKD'),
        cell('caught', tp, ckd ? tp / ckd : 0, true), cell('missed', fn, ckd ? fn / ckd : 0, false),
        h('span', { class: 'mx-row' }, 'Actually not CKD'),
        cell('false alarms', fp, healthy ? fp / healthy : 0, false), cell('cleared', tn, healthy ? tn / healthy : 0, true));
      matrixNote.textContent = `Of ${fmt(ckd)} patients with CKD, ${fmt(tp)} were caught (recall ${pct(m.recall)}). Of ${fmt(healthy)} without, ${fmt(tn)} were cleared (specificity ${pct(m.specificity)}).`;
    }

    function select(key) {
      state.selected = key;
      renderTable();
      renderMatrix();
      roc.update({ selected: key });
    }

    /* ------------------------------------------------------------- ROC chart */
    const rocBox = h('div', { class: 'roc-box' });
    const zoomToggle = h('input', { type: 'checkbox', id: 'roc-zoom', onchange: () => roc.update({ zoom: zoomToggle.checked }) });
    const rocSection = h('div', { class: 'chart-panel' },
      h('h3', null, 'ROC curves'),
      rocBox,
      h('div', { class: 'chart-foot' },
        h('label', { class: 'switch switch-light', for: 'roc-zoom' }, zoomToggle, h('span', { class: 'switch-ui', 'aria-hidden': 'true' }, ''), h('span', null, 'Zoom to the top-left corner')),
        h('p', { class: 'rd-muted-light' }, 'Click a curve or a table row to compare. The dashed line is a coin flip.')));

    /* ------------------------------------------------------ importance + data */
    const top = data.importance.slice(0, 12);
    const importance = section('Which measurements matter most',
      h('p', { class: 'rd-muted-light' }, 'How much the ensemble\u2019s probability estimates get worse when one measurement is shuffled, measured on held-out patients. Longer bars mean the models lean on that measurement more.'),
      h('ul', { class: 'bars' }, top.map((row) => h('li', { class: 'bar-row' },
        h('span', { class: 'bar-label' }, row.label),
        h('span', { class: 'bar-track', 'aria-hidden': 'true' }, h('i', { style: { width: `${Math.max(1, row.relative * 100)}%` } })),
        h('span', { class: 'bar-val' }, `${Math.round(row.relative * 100)}`)))));

    const missing = Object.entries(dataset.missing_fraction).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const labelFor = (key) => (schemaLabels.get(key) || key);
    const snapshot = section('The data behind it',
      h('dl', { class: 'facts' },
        h('div', null, h('dt', null, 'Patients'), h('dd', null, fmt(dataset.rows))),
        h('div', null, h('dt', null, 'With CKD'), h('dd', null, fmt(dataset.class_counts.ckd))),
        h('div', null, h('dt', null, 'Without CKD'), h('dd', null, fmt(dataset.class_counts.notckd))),
        h('div', null, h('dt', null, 'Complete rows'), h('dd', null, fmt(dataset.complete_rows), h('small', null, ` of ${fmt(dataset.rows)}`)))),
      h('p', { class: 'rd-muted-light' }, `Cleaning repaired ${fmt(dataset.cells_repaired)} cells with stray tabs or spaces and blanked ${fmt(dataset.cells_blanked)} implausible values, which are then treated as missing.`),
      h('h3', null, 'Most often missing'),
      h('ul', { class: 'bars bars-muted' }, missing.map(([key, fraction]) => h('li', { class: 'bar-row' },
        h('span', { class: 'bar-label' }, labelFor(key)),
        h('span', { class: 'bar-track', 'aria-hidden': 'true' }, h('i', { style: { width: `${Math.max(1, fraction * 100)}%` } })),
        h('span', { class: 'bar-val' }, `${Math.round(fraction * 100)}%`)))));

    const v = data.versions || {};
    const usedXgb = data.members.some((m) => m.key === 'xgboost');
    const provenance = h('p', { class: 'provenance' },
      `Trained ${new Date(data.generated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })} in ${data.seconds} s on scikit-learn ${v['scikit-learn'] || '?'}.`,
      usedXgb ? '' : ' XGBoost was not installed when this model was trained, so scikit-learn\u2019s gradient boosting stands in for it.');

    bodyEl.replaceChildren(
      h('p', { class: 'callout' }, icon('info', 18),
        h('span', null, 'Read these scores with care. The dataset is small and its two classes are well separated, so near-perfect results are expected here. They do not show how the models would perform in a clinic.')),
      section('Model comparison', h('div', { class: 'table-wrap' }, table)),
      h('div', { class: 'two-up' },
        h('section', { class: 'panel' }, rocSection),
        h('section', { class: 'panel' }, matrixTitle, matrix, matrixNote)),
      h('div', { class: 'two-up' }, importance, snapshot),
      provenance);

    roc = rocChart(rocBox, { models: data.models, selected: state.selected, zoom: false, onSelect: select });
    renderTable();
    renderMatrix();
  }

  const schemaLabels = new Map();
  return {
    load,
    setLabels(features) { features.forEach((f) => schemaLabels.set(f.key, f.label)); },
  };
}
