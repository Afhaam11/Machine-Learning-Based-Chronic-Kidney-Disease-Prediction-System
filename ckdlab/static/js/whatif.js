/* What-if panel. One API call sweeps the chosen measurement across its range; after that the
   slider (or dragging on the chart) projects the risk locally by interpolation, so it feels instant. */

import { h, fmt, snap, scaleFor, interpolate, clamp, displayValue, riskPct, signedPts, bandOf } from './util.js';
import { curveChart } from './charts.js';
import { api } from './api.js';

export function createWhatIf(container, schema, hooks) {
  const byKey = new Map(schema.features.map((f) => [f.key, f]));
  let inputs = null;
  let result = null;
  let featureKey = null;
  let chart = null;
  let controller = null;
  let seq = 0;

  const select = h('select', {
    id: 'wi-select', class: 'select',
    onchange: () => { featureKey = select.value; load(); },
  });
  const body = h('div', { class: 'wi-body' });
  container.replaceChildren(
    h('h3', null, 'What if'),
    h('p', { class: 'rd-sub' }, 'Change one measurement and watch the estimate move. Everything else stays as entered.'),
    h('div', { class: 'wi-pick' }, h('label', { for: 'wi-select' }, 'Measurement'), select),
    body,
  );

  function renderOptions() {
    const provided = [];
    const missing = [];
    schema.features.forEach((f) => (inputs[f.key] !== undefined ? provided : missing).push(f));
    const groups = [h('optgroup', { label: 'Provided' }, provided.map((f) => h('option', { value: f.key }, `${f.label} (${displayValue(f, inputs[f.key])})`)))];
    if (missing.length) groups.push(h('optgroup', { label: 'Not provided yet' }, missing.map((f) => h('option', { value: f.key }, f.label))));
    select.replaceChildren(...groups);
    select.value = featureKey;
  }

  function defaultFeature() {
    const top = result.explanation && result.explanation.contributions[0];
    return top ? top.key : Object.keys(inputs)[0];
  }

  /** Called whenever a new assessment arrives. */
  function setContext(nextInputs, nextResult) {
    inputs = nextInputs;
    result = nextResult;
    if (!featureKey || !byKey.has(featureKey)) featureKey = defaultFeature();
    renderOptions();
    load();
  }

  async function load() {
    chart?.destroy();
    chart = null;
    seq += 1;
    const mine = seq;
    controller?.abort();
    controller = new AbortController();
    body.replaceChildren(h('p', { class: 'rd-muted' }, 'Calculating…'));
    try {
      const data = await api.sensitivity(inputs, featureKey, { signal: controller.signal });
      if (mine === seq) render(data);
    } catch (err) {
      if (err.name === 'AbortError') return;
      body.replaceChildren(h('p', { class: 'rd-muted' }, err.message));
    }
  }

  function render(data) {
    const feature = byKey.get(featureKey);
    const discrete = feature.kind !== 'number';
    const spread = Math.max(...data.risk) - Math.min(...data.risk);
    const currentRisk = data.current.risk;

    const valueText = h('strong', { class: 'wi-value-text' });
    const riskNum = h('span', { class: 'wi-risk-num' });
    const deltaEl = h('span', { class: 'wi-delta' });
    const riskBox = h('div', { class: 'wi-risk' }, riskNum, deltaEl);
    const useBtn = h('button', { type: 'button', class: 'btn btn-small btn-light' }, 'Use this value');
    const resetBtn = h('button', { type: 'button', class: 'link-btn' }, 'Reset');
    const summary = h('div', { class: 'wi-summary' },
      h('div', { class: 'wi-value' }, h('span', { class: 'wi-label' }, feature.label), valueText), riskBox);
    const flat = h('p', { class: 'rd-muted wi-flat', hidden: spread >= 0.05 },
      'On its own, this measurement barely moves the estimate for this patient. Other values keep it where it is.');

    const showRisk = (risk) => {
      riskNum.textContent = riskPct(risk);
      riskBox.dataset.band = bandOf(risk, schema.bands).key;
      const diff = risk - currentRisk;
      deltaEl.textContent = Math.abs(diff) < 0.005 ? 'same as now' : `${signedPts(diff)} points vs now`;
    };

    if (discrete) {
      const currentIndex = data.current.value === null ? -1
        : feature.kind === 'binary' ? Math.round(data.current.value)
          : data.grid.findIndex((g) => Math.abs(g - data.current.value) < 1e-9);
      let index = currentIndex === -1 ? 0 : currentIndex;
      const buttons = data.grid.map((_g, i) => h('button', {
        type: 'button', class: 'opt-bar', 'aria-pressed': 'false', 'data-band': bandOf(data.risk[i], schema.bands).key,
        onclick: () => setIndex(i),
      },
      h('span', { class: 'opt-risk' }, riskPct(data.risk[i])),
      h('span', { class: 'opt-track' }, h('i', { style: { height: `${Math.max(2, data.risk[i] * 100)}%` } })),
      h('span', { class: 'opt-label' }, data.labels[i]),
      i === currentIndex ? h('span', { class: 'opt-now' }, 'now') : null));
      const setIndex = (i) => {
        index = i;
        buttons.forEach((b, j) => b.setAttribute('aria-pressed', String(j === i)));
        valueText.textContent = data.labels[i];
        showRisk(data.risk[i]);
        useBtn.disabled = i === currentIndex;
      };
      useBtn.addEventListener('click', () => {
        hooks.onApply(featureKey, feature.kind === 'binary' ? feature.options[index].value : data.grid[index]);
      });
      resetBtn.addEventListener('click', () => setIndex(currentIndex === -1 ? 0 : currentIndex));
      body.replaceChildren(summary, h('div', { class: 'opt-bars', role: 'group', 'aria-label': `${feature.label} options` }, buttons), flat,
        h('div', { class: 'wi-actions' }, useBtn, resetBtn));
      setIndex(index);
      return;
    }

    // continuous measurement
    const scale = scaleFor(feature);
    const fallback = feature.ref ? (feature.ref[0] + feature.ref[1]) / 2 : (feature.ui[0] + feature.ui[1]) / 2;
    const start = data.current.value ?? snap(feature, fallback);
    let value = start;
    const slider = h('input', {
      type: 'range', class: 'slider', min: '0', max: '1000', step: '1',
      'aria-label': `${feature.label} what-if value`,
      oninput: () => setValue(clamp(snap(feature, scale.fromPos(Number(slider.value) / 1000)), feature.ui[0], feature.ui[1]), 'slider'),
    });
    const chartBox = h('div', { class: 'wi-chart' });
    const legend = h('p', { class: 'wi-legend' },
      h('span', { class: 'key key-current' }, data.current.value === null ? 'Now (not provided)' : 'Now'),
      h('span', { class: 'key key-whatif' }, 'What-if'),
      feature.ref ? h('span', { class: 'key key-ref' }, 'Typical range') : null);

    const setValue = (v, from) => {
      value = v;
      valueText.textContent = `${fmt(v, feature.decimals)} ${feature.unit}`.trim();
      showRisk(interpolate(data.grid, data.risk, v));
      chart?.setValue(v);
      if (from !== 'slider') slider.value = String(Math.round(clamp(scale.toPos(v), 0, 1) * 1000));
      useBtn.disabled = data.current.value !== null && Math.abs(v - data.current.value) < 1e-9;
    };
    useBtn.addEventListener('click', () => hooks.onApply(featureKey, value));
    resetBtn.addEventListener('click', () => setValue(start, 'reset'));

    body.replaceChildren(summary, chartBox, slider, legend, flat, h('div', { class: 'wi-actions' }, useBtn, resetBtn));
    chart = curveChart(chartBox, {
      feature, grid: data.grid, risk: data.risk, current: data.current, bands: schema.bands, value: start,
      onPick: (v) => setValue(v, 'chart'),
    });
    setValue(start, 'init');
  }

  return { setContext };
}
