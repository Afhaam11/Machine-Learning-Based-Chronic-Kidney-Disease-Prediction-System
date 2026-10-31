/* Hand-written SVG charts. They size themselves to their container and redraw on resize.
   Colours come from CSS classes, so both themes work without any chart code. */

import { s, clamp, interpolate, scaleFor, snap, fmt } from './util.js';

function niceStep(raw) {
  const exp = Math.floor(Math.log10(raw));
  const base = raw / 10 ** exp;
  const nice = base <= 1 ? 1 : base <= 2 ? 2 : base <= 5 ? 5 : 10;
  return nice * 10 ** exp;
}

function ticksFor(feature) {
  const [lo, hi] = feature.ui;
  if (feature.scale === 'log') {
    const out = [];
    for (let p = -2; p <= 3; p += 1) {
      for (const m of [1, 2, 5]) {
        const v = m * 10 ** p;
        if (v >= lo && v <= hi) out.push(v);
      }
    }
    return out;
  }
  const step = niceStep((hi - lo) / 4);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

/* ------------------------------------------------------------ what-if risk curve */

/** options: {feature, grid, risk, current: {value, risk}, bands, value, onPick} */
export function curveChart(container, options) {
  const { feature, grid, risk, bands, onPick } = options;
  const scale = scaleFor(feature);
  const height = 176;
  const margin = { l: 38, r: 12, t: 8, b: 28 };
  let width = 0;
  let value = options.value;
  let whatIfGroup = null;
  let pw = 0;

  const svg = s('svg', { class: 'chart chart-curve', height, role: 'img' });
  container.replaceChildren(svg);

  const bandKey = (p) => (bands.find((b) => p < b.to) || bands[bands.length - 1]).key;

  function draw() {
    pw = width - margin.l - margin.r;
    const ph = height - margin.t - margin.b;
    const x = (v) => margin.l + clamp(scale.toPos(v), 0, 1) * pw;
    const y = (p) => margin.t + (1 - p) * ph;

    svg.setAttribute('width', width);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('aria-label', `Estimated risk as ${feature.label.toLowerCase()} changes from ${fmt(feature.ui[0], feature.decimals)} to ${fmt(feature.ui[1], feature.decimals)}.`);
    svg.replaceChildren();

    bands.forEach((b) => svg.append(s('rect', {
      class: `chart-band band-${b.key}`, x: margin.l, y: y(b.to), width: pw, height: y(b.from) - y(b.to),
    })));
    if (feature.ref) {
      svg.append(s('rect', {
        class: 'chart-ref', x: x(feature.ref[0]), y: margin.t, width: Math.max(2, x(feature.ref[1]) - x(feature.ref[0])), height: ph,
      }));
    }
    svg.append(s('line', { class: 'chart-threshold', x1: margin.l, x2: margin.l + pw, y1: y(0.5), y2: y(0.5) }));

    [0, 0.5, 1].forEach((p) => svg.append(s('text', {
      class: 'chart-tick', x: margin.l - 7, y: y(p) + 4, 'text-anchor': 'end',
    }, `${p * 100}%`)));
    ticksFor(feature).forEach((t) => {
      svg.append(s('line', { class: 'chart-axis', x1: x(t), x2: x(t), y1: margin.t + ph, y2: margin.t + ph + 4 }));
      svg.append(s('text', { class: 'chart-tick', x: x(t), y: margin.t + ph + 17, 'text-anchor': 'middle' }, fmt(t, feature.decimals)));
    });
    svg.append(s('line', { class: 'chart-axis', x1: margin.l, x2: margin.l + pw, y1: margin.t + ph, y2: margin.t + ph }));

    svg.append(s('path', {
      class: 'chart-line',
      d: grid.map((g, i) => `${i ? 'L' : 'M'}${x(g).toFixed(1)} ${y(risk[i]).toFixed(1)}`).join(''),
    }));

    const cur = options.current;
    if (cur && cur.value !== null) {
      svg.append(s('line', { class: 'chart-guide', x1: x(cur.value), x2: x(cur.value), y1: margin.t, y2: margin.t + ph }));
      svg.append(s('circle', { class: 'chart-current', cx: x(cur.value), cy: y(cur.risk), r: 5 }));
    }

    whatIfGroup = s('g', { class: 'chart-whatif' },
      s('line', { class: 'whatif-guide', y1: margin.t, y2: margin.t + ph }),
      s('circle', { class: 'whatif-dot', r: 6.5 }));
    svg.append(whatIfGroup);

    const overlay = s('rect', { class: 'chart-hit', x: margin.l, y: margin.t, width: pw, height: ph });
    const pick = (event) => {
      const rect = svg.getBoundingClientRect();
      const pos = (event.clientX - rect.left - margin.l) / pw;
      onPick?.(clamp(snap(feature, scale.fromPos(clamp(pos, 0, 1))), feature.ui[0], feature.ui[1]));
    };
    overlay.addEventListener('pointerdown', (event) => { overlay.setPointerCapture(event.pointerId); pick(event); });
    overlay.addEventListener('pointermove', (event) => { if (event.buttons) pick(event); });
    svg.append(overlay);

    place(value, { x, y });
  }

  function place(v, fns) {
    if (!whatIfGroup || v === null || v === undefined) return;
    const x = fns?.x || ((val) => margin.l + clamp(scale.toPos(val), 0, 1) * pw);
    const y = fns?.y || ((p) => margin.t + (1 - p) * (height - margin.t - margin.b));
    const r = interpolate(grid, risk, v);
    const px = x(v);
    const [guide, dot] = whatIfGroup.children;
    guide.setAttribute('x1', px); guide.setAttribute('x2', px);
    dot.setAttribute('cx', px); dot.setAttribute('cy', y(r));
    dot.setAttribute('class', `whatif-dot band-${bandKey(r)}`);
  }

  const observer = new ResizeObserver(() => {
    const w = Math.round(container.clientWidth);
    if (w > 0 && w !== width) { width = w; draw(); }
  });
  observer.observe(container);

  return {
    setValue(v) { value = v; place(v); },
    destroy() { observer.disconnect(); },
  };
}

/* ------------------------------------------------------------------ ROC curves */

/** options: {models, selected, zoom, onSelect}. models carry roc: {fpr, tpr}. */
export function rocChart(container, options) {
  let { selected, zoom } = options;
  const { models, onSelect } = options;
  const height = 300;
  const margin = { l: 44, r: 14, t: 10, b: 38 };
  let width = 0;
  const svg = s('svg', { class: 'chart chart-roc', height, role: 'img', 'aria-label': 'ROC curves for each model' });
  container.replaceChildren(svg);

  function draw() {
    const [x0, x1, y0, y1] = zoom ? [0, 0.2, 0.8, 1] : [0, 1, 0, 1];
    const pw = width - margin.l - margin.r;
    const ph = height - margin.t - margin.b;
    const x = (v) => margin.l + ((v - x0) / (x1 - x0)) * pw;
    const y = (v) => margin.t + (1 - (v - y0) / (y1 - y0)) * ph;
    svg.setAttribute('width', width);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.replaceChildren(
      s('defs', null, s('clipPath', { id: 'roc-clip' }, s('rect', { x: margin.l, y: margin.t, width: pw, height: ph }))),
    );

    const steps = zoom ? 4 : 5;
    for (let i = 0; i <= steps; i += 1) {
      const gx = x0 + ((x1 - x0) * i) / steps;
      const gy = y0 + ((y1 - y0) * i) / steps;
      svg.append(s('line', { class: 'chart-grid', x1: x(gx), x2: x(gx), y1: margin.t, y2: margin.t + ph }));
      svg.append(s('line', { class: 'chart-grid', x1: margin.l, x2: margin.l + pw, y1: y(gy), y2: y(gy) }));
      svg.append(s('text', { class: 'chart-tick', x: x(gx), y: margin.t + ph + 16, 'text-anchor': 'middle' }, gx.toFixed(zoom ? 2 : 1)));
      svg.append(s('text', { class: 'chart-tick', x: margin.l - 7, y: y(gy) + 4, 'text-anchor': 'end' }, gy.toFixed(zoom ? 2 : 1)));
    }
    svg.append(s('text', { class: 'chart-label', x: margin.l + pw / 2, y: height - 4, 'text-anchor': 'middle' }, 'False positive rate'));
    svg.append(s('text', {
      class: 'chart-label', transform: `translate(12 ${margin.t + ph / 2}) rotate(-90)`, 'text-anchor': 'middle',
    }, 'True positive rate'));

    const layer = s('g', { 'clip-path': 'url(#roc-clip)' });
    layer.append(s('line', { class: 'chart-chance', x1: x(0), y1: y(0), x2: x(1), y2: y(1) }));
    const ordered = [...models].sort((a, b) => Number(a.key === selected) - Number(b.key === selected) || Number(a.is_ensemble) - Number(b.is_ensemble));
    ordered.forEach((m) => {
      const d = m.roc.fpr.map((f, i) => `${i ? 'L' : 'M'}${x(f).toFixed(1)} ${y(m.roc.tpr[i]).toFixed(1)}`).join('');
      const cls = `roc-line${m.is_ensemble ? ' is-ensemble' : ''}${m.key === selected ? ' is-selected' : ''}`;
      layer.append(s('path', { class: cls, d }));
    });
    ordered.forEach((m) => {
      const d = m.roc.fpr.map((f, i) => `${i ? 'L' : 'M'}${x(f).toFixed(1)} ${y(m.roc.tpr[i]).toFixed(1)}`).join('');
      const hit = s('path', { class: 'roc-hit', d }, s('title', null, `${m.name}: AUC ${m.roc_auc.toFixed(3)}`));
      hit.addEventListener('click', () => onSelect?.(m.key));
      layer.append(hit);
    });
    svg.append(layer);
    svg.append(s('rect', { class: 'chart-frame', x: margin.l, y: margin.t, width: pw, height: ph }));
  }

  const observer = new ResizeObserver(() => {
    const w = Math.round(container.clientWidth);
    if (w > 0 && w !== width) { width = w; draw(); }
  });
  observer.observe(container);

  return {
    update(next) {
      if (next.selected !== undefined) selected = next.selected;
      if (next.zoom !== undefined) zoom = next.zoom;
      if (width) draw();
    },
    destroy() { observer.disconnect(); },
  };
}
