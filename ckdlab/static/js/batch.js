/* Batch view: score a whole CSV. Every cell that came from the file is rendered as text,
   and the exported CSV neutralises spreadsheet formulas. */

import { h, icon, fmt, riskPct, csvCell, downloadText } from './util.js';
import { api } from './api.js';

const PAGE = 100;

export function createBatchView(root, schema) {
  const total = schema.features.length;
  let current = null;
  const view = { filter: 'all', sort: null, shown: PAGE };

  const input = h('input', {
    type: 'file', accept: '.csv,.txt,text/csv', id: 'batch-file', class: 'sr-only', tabindex: '-1',
    onchange: () => { if (input.files[0]) run(input.files[0]); input.value = ''; },
  });
  const zone = h('label', {
    class: 'dropzone', for: 'batch-file', tabindex: '0', 'aria-label': 'Choose a CSV file, or drop one here',
  }, icon('upload', 28), h('strong', null, 'Drop a CSV file here'), h('span', null, 'or click to choose one'));
  zone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  ['dragenter', 'dragover'].forEach((type) => zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.add('is-over'); }));
  ['dragleave', 'drop'].forEach((type) => zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.remove('is-over'); }));
  zone.addEventListener('drop', (e) => { const file = e.dataTransfer?.files?.[0]; if (file) run(file); });

  const help = h('p', { class: 'drop-help' },
    h('a', { href: '/api/template.csv', download: 'ckd-template.csv' }, icon('download', 15), 'Download a template'),
    ' with the three sample patients, or upload the original dataset as it is. Column names are case-insensitive, and an optional id column is carried through.');
  const status = h('div', { class: 'batch-status', 'aria-live': 'polite' });
  const results = h('div', { class: 'batch-results', hidden: true });
  root.replaceChildren(h('div', { class: 'batch-intro' }, zone, input, help), status, results);

  async function run(file) {
    results.hidden = true;
    status.replaceChildren(h('p', { class: 'callout' }, h('span', { class: 'spinner', 'aria-hidden': 'true' }), h('span', null, `Scoring ${file.name}…`)));
    try {
      const data = await api.batch(file);
      current = { fileName: file.name, data };
      Object.assign(view, { filter: 'all', sort: null, shown: PAGE });
      status.replaceChildren();
      renderResults();
    } catch (err) {
      status.replaceChildren(h('p', { class: 'callout callout-warn', role: 'alert' }, icon('warn', 18), h('span', null, err.message)));
    }
  }

  function filtered() {
    const { rows } = current.data;
    let out = rows;
    if (view.filter === 'ckd') out = rows.filter((r) => r.label === 'ckd');
    else if (view.filter === 'notckd') out = rows.filter((r) => r.label === 'notckd');
    else if (view.filter === 'notes') out = rows.filter((r) => r.issues.length > 0);
    if (view.sort) {
      const dir = view.sort === 'asc' ? 1 : -1;
      out = [...out].sort((a, b) => ((a.risk ?? -1) - (b.risk ?? -1)) * dir);
    }
    return out;
  }

  function renderResults() {
    const { summary, rows } = current.data;
    const hasId = rows.some((r) => r.id !== null && r.id !== '');
    const hasRef = rows.some((r) => 'reference' in r);

    const tile = (label, value, sub) => h('div', { class: 'tile' }, h('dt', null, label), h('dd', null, value, sub ? h('small', null, sub) : null));
    const tiles = h('dl', { class: 'tiles' },
      tile('Rows scored', fmt(summary.scored), summary.skipped ? `${fmt(summary.skipped)} skipped, too few values` : `of ${fmt(summary.rows)} rows`),
      tile('Flagged as CKD', fmt(summary.flaggedCkd), summary.scored ? `${Math.round((summary.flaggedCkd / summary.scored) * 100)}% of scored rows` : null),
      tile('Average risk', summary.meanRisk === null ? 'n/a' : riskPct(summary.meanRisk), 'across scored rows'),
      tile('Rows with notes', fmt(summary.withIssues), 'invalid or missing values'));

    const counts = {
      all: rows.length,
      ckd: rows.filter((r) => r.label === 'ckd').length,
      notckd: rows.filter((r) => r.label === 'notckd').length,
      notes: rows.filter((r) => r.issues.length > 0).length,
    };
    const chips = [['all', 'All'], ['ckd', 'Predicted CKD'], ['notckd', 'Predicted not CKD'], ['notes', 'With notes']].map(([key, label]) =>
      h('button', {
        type: 'button', class: 'filter-chip', 'aria-pressed': String(view.filter === key),
        onclick: () => { view.filter = key; view.shown = PAGE; renderTable(); chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.key === key))); },
        'data-key': key,
      }, label, h('span', { class: 'chip-count' }, fmt(counts[key]))));

    const tbody = h('tbody');
    const more = h('button', { type: 'button', class: 'btn btn-small btn-light', onclick: () => { view.shown += PAGE; renderTable(); } });
    const sortBtn = h('button', {
      type: 'button', class: 'th-btn', title: 'Sort by risk',
      onclick: () => { view.sort = view.sort === null ? 'desc' : view.sort === 'desc' ? 'asc' : null; renderTable(); },
    }, 'Risk', icon('chevron', 13));
    const riskTh = h('th', { scope: 'col', class: 'col-risk', 'aria-sort': 'none' }, sortBtn);
    const table = h('table', { class: 'table batch-table' },
      h('caption', { class: 'sr-only' }, `Scores for ${current.fileName}`),
      h('thead', null, h('tr', null,
        h('th', { scope: 'col', class: 'col-num' }, 'Row'),
        hasId ? h('th', { scope: 'col' }, 'ID') : null,
        riskTh,
        h('th', { scope: 'col' }, 'Prediction'),
        h('th', { scope: 'col', class: 'col-num', title: 'Models voting CKD' }, 'Votes'),
        h('th', { scope: 'col', class: 'col-num', title: 'Measurements provided' }, 'Fields'),
        h('th', { scope: 'col' }, 'Notes'),
        hasRef ? h('th', { scope: 'col' }, 'File label') : null)),
      tbody);

    function renderTable() {
      const list = filtered();
      const slice = list.slice(0, view.shown);
      riskTh.setAttribute('aria-sort', view.sort === 'asc' ? 'ascending' : view.sort === 'desc' ? 'descending' : 'none');
      tbody.replaceChildren(...slice.map((r) => h('tr', { class: r.risk === null ? 'is-skipped' : null },
        h('td', { class: 'col-num muted' }, String(r.row)),
        hasId ? h('td', { class: 'col-id' }, r.id ?? '') : null,
        h('td', { class: 'col-risk' }, r.risk === null ? h('span', { class: 'muted' }, 'n/a')
          : h('span', { class: 'risk-cell' },
            h('span', { class: 'mini-bar', 'aria-hidden': 'true' }, h('i', { 'data-band': r.band, style: { width: `${Math.max(1.5, r.risk * 100)}%` } })),
            h('span', { class: 'risk-num' }, riskPct(r.risk)))),
        h('td', null, r.label === null ? h('span', { class: 'chip chip-plain' }, 'Skipped')
          : h('span', { class: `chip chip-vote ${r.label}` }, r.label === 'ckd' ? 'CKD' : 'Not CKD')),
        h('td', { class: 'col-num' }, r.votesCkd === null ? '\u2013' : `${r.votesCkd}/${summary.members}`),
        h('td', { class: 'col-num' }, `${r.provided}/${total}`),
        h('td', { class: 'col-notes' }, r.issues.length
          ? h('span', { class: 'note-pill', title: r.issues.join('\n') }, icon('warn', 14), r.issues.length === 1 ? r.issues[0] : `${r.issues.length} notes`)
          : ''),
        hasRef ? h('td', null, r.reference ? h('span', { class: `ref ${r.reference === r.label ? 'match' : 'differs'}` },
          r.reference === 'ckd' ? 'CKD' : 'Not CKD', r.label === null ? '' : r.reference === r.label ? icon('check', 14) : ' (differs)') : '') : null)));
      if (!slice.length) tbody.replaceChildren(h('tr', null, h('td', { colspan: '8', class: 'empty-row' }, 'No rows match this filter.')));
      const remaining = list.length - slice.length;
      more.hidden = remaining <= 0;
      more.textContent = `Show ${Math.min(PAGE, remaining)} more`;
    }

    const agreement = summary.agreement && summary.agreement.compared
      ? h('p', { class: 'callout' }, icon('info', 18), h('span', null,
        `The file includes labels, and the ensemble matches ${fmt(summary.agreement.matches)} of ${fmt(summary.agreement.compared)}. If this file overlaps the training data, that agreement is optimistic.`))
      : null;
    const columns = h('p', { class: 'rd-muted-light' },
      `Used ${summary.columnsUsed.length} of ${total} measurement columns.`,
      summary.columnsIgnored.length ? ` Ignored: ${summary.columnsIgnored.slice(0, 8).join(', ')}${summary.columnsIgnored.length > 8 ? ', and more' : ''}.` : '');

    const exportCsv = () => {
      const head = ['row', 'id', 'risk_percent', 'prediction', 'band', 'models_voting_ckd', 'measurements_provided', 'notes', ...(hasRef ? ['file_label', 'matches_file_label'] : [])];
      const lines = [head.join(',')];
      current.data.rows.forEach((r) => {
        const cells = [r.row, r.id ?? '', r.risk === null ? '' : (r.risk * 100).toFixed(1), r.label ?? 'skipped', r.band ?? '',
          r.votesCkd ?? '', r.provided, r.issues.join(' | ')];
        if (hasRef) cells.push(r.reference ?? '', r.reference && r.label ? (r.reference === r.label ? 'yes' : 'no') : '');
        lines.push(cells.map(csvCell).join(','));
      });
      downloadText(`${current.fileName.replace(/\.[^.]+$/, '')}-scored.csv`, `${lines.join('\n')}\n`);
    };

    results.replaceChildren(
      h('div', { class: 'results-head' },
        h('h2', null, current.fileName),
        h('div', { class: 'results-actions' },
          h('button', { type: 'button', class: 'btn btn-small btn-light', onclick: exportCsv }, icon('download', 16), 'Download results'),
          h('button', { type: 'button', class: 'link-btn', onclick: () => { results.hidden = true; current = null; zone.focus(); } }, 'Score another file'))),
      tiles, ...(agreement ? [agreement] : []), columns,
      h('div', { class: 'filters', role: 'group', 'aria-label': 'Filter rows' }, chips),
      h('div', { class: 'table-wrap' }, table),
      h('div', { class: 'more-row' }, more));
    results.hidden = false;
    renderTable();
  }
}
