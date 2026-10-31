/* Shared helpers. Nothing here ever builds HTML from strings: all content goes through
   textContent / text nodes, so values from an uploaded file can never inject markup. */

const SVG_NS = 'http://www.w3.org/2000/svg';

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function appendChildren(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

function applyAttrs(el, attrs) {
  if (!attrs) return;
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'style' && typeof value === 'object') {
      for (const [prop, val] of Object.entries(value)) el.style.setProperty(prop, String(val));
    } else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else {
      el.setAttribute(key, value === true ? '' : String(value));
    }
  }
}

/** Create an HTML element: h('div', {class: 'x'}, child, 'text', ...) */
export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  applyAttrs(el, attrs);
  appendChildren(el, children);
  return el;
}

/** Create an SVG element. */
export function s(tag, attrs, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  applyAttrs(el, attrs);
  appendChildren(el, children);
  return el;
}

const ICONS = {
  sun: 'M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
  info: 'M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18zM12 11v5M12 8h.01',
  warn: 'M12 3l10 18H2zM12 10v5M12 18h.01',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  upload: 'M12 16V4M7 9l5-5 5 5M4 20h16',
  download: 'M12 4v12M7 11l5 5 5-5M4 20h16',
  print: 'M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v7H7z',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  copy: 'M9 9h11v11H9zM5 15H4V4h11v1',
  reset: 'M3 12a9 9 0 1 0 3-6.7M3 4v5h5',
  x: 'M6 6l12 12M18 6L6 18',
  chevron: 'M6 9l6 6 6-6',
  file: 'M6 3h8l4 4v14H6zM14 3v4h4',
};

export function icon(name, size = 18) {
  return s('svg', {
    viewBox: '0 0 24 24', width: size, height: size, fill: 'none', stroke: 'currentColor',
    'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    'aria-hidden': 'true', focusable: 'false', class: 'icon',
  }, s('path', { d: ICONS[name] }));
}

/* ------------------------------------------------------------------ formatting */

/** Risk as a whole-number string. Never claims certainty: <1 and >99 at the extremes. */
export function riskText(p) {
  if (p < 0.005) return '<1';
  if (p > 0.995) return '>99';
  return String(Math.round(p * 100));
}
export const riskPct = (p) => `${riskText(p)}%`;

/** Change in risk as signed percentage points, using a real minus sign. */
export function signedPts(delta) {
  const v = Math.round(delta * 100);
  if (v === 0) return '0';
  return v > 0 ? `+${v}` : `\u2212${Math.abs(v)}`;
}

export function fmt(value, decimals = 0) {
  return Number(value).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: decimals });
}

export function displayValue(feature, value) {
  if (value === null || value === undefined) return 'not provided';
  if (feature.kind === 'binary') {
    const option = feature.options.find((o) => o.value === value);
    return option ? option.label : String(value);
  }
  if (feature.kind === 'ordinal') {
    const level = feature.levels.find((l) => Math.abs(l.value - value) < 1e-9);
    return level ? level.label : String(value);
  }
  return `${fmt(value, feature.decimals)} ${feature.unit}`.trim();
}

export function relativeTime(timestamp) {
  const seconds = Math.round((Date.now() - timestamp) / 1000);
  if (seconds < 45) return 'just now';
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  return new Date(timestamp).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/* ---------------------------------------------------------------------- maths */

export const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

export function debounce(fn, ms) {
  let timer;
  const wrapped = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

/** Piecewise-linear interpolation; xs must be ascending. */
export function interpolate(xs, ys, x) {
  const n = xs.length;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[n - 1]) return ys[n - 1];
  let i = 1;
  while (xs[i] < x) i += 1;
  const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
  return ys[i - 1] + t * (ys[i] - ys[i - 1]);
}

/** Map a measurement onto 0..1 along its display scale (linear or log). */
export function scaleFor(feature) {
  const [lo, hi] = feature.ui;
  const log = feature.scale === 'log';
  const a = log ? Math.log(lo) : lo;
  const b = log ? Math.log(hi) : hi;
  return {
    toPos: (v) => ((log ? Math.log(Math.max(v, 1e-9)) : v) - a) / (b - a),
    fromPos: (p) => {
      const x = a + clamp(p, 0, 1) * (b - a);
      return log ? Math.exp(x) : x;
    },
  };
}

/** Snap to the feature's step and tidy floating point noise. */
export function snap(feature, value) {
  const step = feature.step || 1;
  return Number((Math.round(value / step) * step).toFixed((feature.decimals || 0) + 1));
}

export const bandOf = (risk, bands) => bands.find((b) => risk < b.to) || bands[bands.length - 1];

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ------------------------------------------------------------------------ I/O */

let toastTimer;
export function toast(message, ms = 2600) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), ms);
}

/** One CSV cell. Guards against spreadsheet formula injection from user-supplied text. */
export function csvCell(value) {
  let text = value === null || value === undefined ? '' : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function downloadText(filename, text, mime = 'text/csv') {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = h('a', { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
