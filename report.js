/* Builds the printable report into #report. The print stylesheet hides everything else,
   so "Print report" followed by "Save as PDF" gives a clean one-page summary. */

import { h, riskText, riskPct, signedPts, bandOf, displayValue, fmt } from './util.js';

function flagFor(feature, value) {
  if (value === undefined) return '';
  if (feature.kind === 'number') {
    if (!feature.ref) return '';
    return value < feature.ref[0] ? 'Below typical' : value > feature.ref[1] ? 'Above typical' : 'Typical';
  }
  if (feature.kind === 'ordinal') {
    return feature.normalLevels.length && !feature.normalLevels.includes(value) ? 'Raised' : '';
  }
  const option = feature.options.find((o) => o.value === value);
  return option && option.adverse ? 'Flagged' : '';
}

export function summaryText(schema, result) {
  const band = bandOf(result.risk, schema.bands);
  const agreeing = result.label === 'ckd' ? result.votes.ckd : result.votes.notckd;
  const lines = [
    `CKD Risk Lab estimate: ${riskPct(result.risk)} (${band.label.toLowerCase()} risk). The ensemble predicts ${result.label === 'ckd' ? 'CKD' : 'not CKD'}; ${agreeing} of ${result.votes.total} models agree.`,
    `Reliability: ${result.reliability.level} (${result.reliability.summary}).`,
  ];
  const drivers = result.explanation ? result.explanation.contributions.filter((c) => Math.abs(c.delta) >= 0.005).slice(0, 4) : [];
  if (drivers.length) lines.push(`Main drivers: ${drivers.map((c) => `${c.label} ${c.display} (${signedPts(c.delta)} points)`).join(', ')}.`);
  lines.push(schema.disclaimer);
  return lines.join('\n');
}

export function buildReport(root, schema, result, inputs) {
  const band = bandOf(result.risk, schema.bands);
  const agreeing = result.label === 'ckd' ? result.votes.ckd : result.votes.notckd;

  const strip = h('div', { class: 'rp-strip' },
    schema.bands.map((b) => h('span', { class: `band-${b.key}`, style: { flex: String((b.to - b.from) * 100) } }, b.label)),
    h('i', { style: { left: `${result.risk * 100}%` } }));

  const measurements = schema.groups.map((group) => h('div', { class: 'rp-group' },
    h('h3', null, group.label),
    h('table', null,
      h('tbody', null, schema.features.filter((f) => f.group === group.id).map((f) => h('tr', null,
        h('th', { scope: 'row' }, f.label),
        h('td', null, displayValue(f, inputs[f.key])),
        h('td', { class: 'rp-ref' }, f.ref ? `${fmt(f.ref[0], f.decimals)} to ${fmt(f.ref[1], f.decimals)}` : ''),
        h('td', { class: 'rp-flag' }, flagFor(f, inputs[f.key]))))))));

  const drivers = result.explanation ? result.explanation.contributions.slice(0, 8) : [];

  // Optional sections are null when empty; filter them out, because replaceChildren would print them as the text "null".
  root.replaceChildren(...[
    h('header', { class: 'rp-head' },
      h('h1', null, 'CKD Risk Lab report'),
      h('p', null, `Generated ${new Date().toLocaleString(undefined, { dateStyle: 'long', timeStyle: 'short' })}`)),
    h('section', { class: 'rp-summary' },
      h('p', { class: 'rp-risk' }, `${riskText(result.risk)}%`),
      h('div', null,
        h('p', { class: 'rp-band' }, `${band.label} risk`),
        h('p', null, `The ensemble predicts ${result.label === 'ckd' ? 'CKD' : 'not CKD'}. ${agreeing} of ${result.votes.total} models agree.`),
        h('p', null, `Reliability: ${result.reliability.level} (${result.reliability.summary}).`))),
    strip,
    h('h2', null, 'Measurements'),
    h('div', { class: 'rp-columns' }, measurements),
    drivers.length ? h('h2', null, 'What drives this result') : null,
    drivers.length ? h('table', { class: 'rp-table' }, h('tbody', null, drivers.map((c) => h('tr', null,
      h('th', { scope: 'row' }, c.label), h('td', null, c.display), h('td', null, `${signedPts(c.delta)} points`))))) : null,
    h('h2', null, 'Model votes'),
    h('table', { class: 'rp-table' }, h('tbody', null, result.models.map((m) => h('tr', null,
      h('th', { scope: 'row' }, m.name), h('td', null, riskPct(m.risk)), h('td', null, m.vote === 'ckd' ? 'CKD' : 'Not CKD'))))),
    result.notes.length ? h('h2', null, 'Data quality') : null,
    result.notes.length ? h('ul', null, result.notes.map((n) => h('li', null, n.message))) : null,
    h('p', { class: 'rp-disclaimer' }, schema.disclaimer),
  ].filter(Boolean));
}
