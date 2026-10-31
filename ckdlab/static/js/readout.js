/* The analyzer panel. The risk strip is the centrepiece: one axis carries the ensemble estimate
   (large marker), every model's own estimate (small dots) and the four risk bands. */

import { h, icon, riskText, riskPct, signedPts, bandOf, reducedMotion, clamp } from './util.js';
import { createWhatIf } from './whatif.js';

const PIN = 12;         // dot diameter in px
const PIN_ROW = 13;     // vertical distance between rows of dots
const PIN_STEP = 13;    // horizontal nudge used to separate overlapping dots
const PIN_ROWS = 3;     // keep the lane short: at most this many rows

function stripBase(bands) {
  const track = h('div', { class: 'strip-track' },
    bands.map((b) => h('span', { class: `strip-band band-${b.key}`, style: { flex: String((b.to - b.from) * 100) } })),
    h('span', { class: 'strip-threshold', style: { left: '50%' } }));
  const scale = h('div', { class: 'strip-scale', 'aria-hidden': 'true' },
    bands.map((b) => h('span', { class: 'strip-name', style: { flex: String((b.to - b.from) * 100) } }, b.label)));
  const ticks = h('div', { class: 'strip-ticks', 'aria-hidden': 'true' },
    ['0%', '20%', '50%', '80%', '100%'].map((t, i) => h('span', { style: { left: `${[0, 20, 50, 80, 100][i]}%` } }, t)));
  return { track, scale, ticks };
}

export function createReadout(root, schema, hooks) {
  const bands = schema.bands;
  let result = null;
  let frame = 0;
  let showAll = false;
  const pinEls = new Map();

  /* ------------------------------------------------------------ empty state */
  const emptyStrip = stripBase(bands);
  const empty = h('div', { class: 'rd-empty' },
    h('h2', null, 'No assessment yet'),
    h('p', null, 'Enter measurements on the left, or load a sample patient, and the estimate will appear here with the reasons behind it.'),
    h('div', { class: 'strip strip-ghost', 'aria-hidden': 'true' },
      h('div', { class: 'strip-lane' }), emptyStrip.track, emptyStrip.scale, emptyStrip.ticks));

  /* ----------------------------------------------------------- result pieces */
  const numberEl = h('span', { class: 'rd-number' });
  const bandChip = h('span', { class: 'chip chip-band' });
  const decisionEl = h('p', { class: 'rd-decision' });
  const agreeEl = h('p', { class: 'rd-agree' });
  const announce = h('p', { class: 'sr-only', 'aria-live': 'polite' });
  const top = h('div', { class: 'rd-top' },
    h('div', { class: 'rd-risk', 'aria-hidden': 'true' }, numberEl, h('span', { class: 'rd-pct' }, '%')),
    h('div', { class: 'rd-verdict' }, bandChip, decisionEl, agreeEl),
    announce);

  const lane = h('div', { class: 'strip-lane' });
  const marker = h('span', { class: 'strip-marker' }, h('i'));
  const resultStrip = stripBase(bands);
  resultStrip.track.append(marker);
  const strip = h('div', { class: 'strip', role: 'img' }, lane, resultStrip.track, resultStrip.scale, resultStrip.ticks);

  const reliabilityEl = h('div', { class: 'rd-reliab' });
  const votesList = h('ul', { class: 'votes' });
  const votesHead = h('p', { class: 'rd-sub' });
  const driversCaption = h('p', { class: 'rd-sub' });
  const driversList = h('ul', { class: 'drivers' });
  const driversMore = h('button', { type: 'button', class: 'link-btn', hidden: true, onclick: () => { showAll = !showAll; renderDrivers(result); } });
  const cells = h('div', { class: 'cells', role: 'img' });
  const cellsText = h('p', { class: 'rd-sub' });
  const notesList = h('ul', { class: 'notes' });
  const whatIfBox = h('section', { class: 'rd-sec whatif' });
  const whatIf = createWhatIf(whatIfBox, schema, { onApply: (key, value) => hooks.onApplyWhatIf(key, value) });

  const stale = h('p', { class: 'rd-stale', hidden: true }, 'Inputs changed. Assess again to update this result.');
  const actions = h('div', { class: 'rd-actions' },
    h('button', { type: 'button', class: 'btn btn-small btn-ghost', onclick: () => hooks.onPrint() }, icon('print', 16), 'Print report'),
    h('button', { type: 'button', class: 'btn btn-small btn-ghost', onclick: () => hooks.onCopy() }, icon('copy', 16), 'Copy summary'));

  const resultEl = h('div', { class: 'rd-result', hidden: true },
    stale, top, strip, reliabilityEl,
    h('section', { class: 'rd-sec' }, h('h3', null, 'Model votes'), votesHead, votesList),
    h('section', { class: 'rd-sec' }, h('h3', null, 'What drives this result'), driversCaption, driversList, driversMore),
    h('section', { class: 'rd-sec' }, h('h3', null, 'Data quality'), cells, cellsText, notesList),
    whatIfBox,
    actions);

  const errorEl = h('div', { class: 'rd-error', role: 'alert', hidden: true });
  const loading = h('div', { class: 'rd-loading', hidden: true, 'aria-hidden': 'true' });
  root.replaceChildren(loading, errorEl, empty, resultEl);

  /* ---------------------------------------------------------------- renderers */
  function animateNumber(from, to) {
    cancelAnimationFrame(frame);
    if (reducedMotion() || from === to) { numberEl.textContent = riskText(to); return; }
    const started = performance.now();
    const duration = 700;
    const step = (now) => {
      const t = clamp((now - started) / duration, 0, 1);
      const eased = 1 - (1 - t) ** 3;
      numberEl.textContent = riskText(from + (to - from) * eased);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
  }

  /* Beeswarm: dots keep their true position unless they would overlap, in which case they stack
     (up to PIN_ROWS rows) and then fan inwards by a few pixels. Agreement reads as a tight cluster. */
  function layoutPins(models, width) {
    const placed = [];
    return [...models].sort((a, b) => a.risk - b.risk).map((m) => {
      const ideal = m.risk * width;
      const base = clamp(ideal, PIN / 2, width - PIN / 2);
      const inward = m.risk < 0.5 ? 1 : -1;
      let best = null;
      for (let row = 0; row < PIN_ROWS; row += 1) {
        for (let k = 0; k <= 4; k += 1) {
          for (const sign of k === 0 ? [0] : [inward, -inward]) {
            const dx = sign * k * PIN_STEP;
            const x = base + dx;
            if (x < PIN / 2 || x > width - PIN / 2) continue;
            if (placed.some((p) => Math.hypot(p.x - x, (p.row - row) * PIN_ROW) < PIN_STEP - 0.5)) continue;
            const cost = Math.abs(dx) + row * 9;
            if (!best || cost < best.cost) best = { x, row, cost };
          }
        }
      }
      best = best || { x: base, row: PIN_ROWS - 1, cost: 0 };
      placed.push(best);
      return { ...m, row: best.row, offset: best.x - ideal };
    });
  }

  function renderStrip(res, first) {
    const placed = layoutPins(res.models, resultStrip.track.clientWidth || 360);
    const rowsUsed = Math.max(...placed.map((p) => p.row)) + 1;
    lane.style.height = `${rowsUsed * PIN_ROW + 8}px`;
    const seen = new Set();
    placed.forEach((m, order) => {
      seen.add(m.key);
      let pin = pinEls.get(m.key);
      if (!pin) {
        pin = h('button', { type: 'button', class: 'pin', tabindex: '0' });
        pinEls.set(m.key, pin);
        lane.append(pin);
      }
      pin.style.setProperty('--i', String(order));
      pin.style.left = `calc(${(m.risk * 100).toFixed(2)}% + ${m.offset.toFixed(1)}px)`;
      pin.style.bottom = `${m.row * PIN_ROW}px`;
      pin.dataset.vote = m.vote;
      pin.dataset.edge = m.risk < 0.14 ? 'left' : m.risk > 0.86 ? 'right' : 'mid';
      pin.dataset.tip = `${m.name}: ${riskPct(m.risk)}`;
      pin.setAttribute('aria-label', `${m.name}: ${riskPct(m.risk)}, votes ${m.vote === 'ckd' ? 'CKD' : 'not CKD'}`);
    });
    [...pinEls.keys()].filter((k) => !seen.has(k)).forEach((k) => { pinEls.get(k).remove(); pinEls.delete(k); });

    const target = `${res.risk * 100}%`;
    strip.classList.toggle('is-entering', first && !reducedMotion());
    if (first) { marker.style.left = '0%'; void marker.offsetWidth; }
    marker.style.left = target;
    const lows = Math.min(...res.models.map((m) => m.risk));
    const highs = Math.max(...res.models.map((m) => m.risk));
    strip.setAttribute('aria-label',
      `Ensemble risk ${riskPct(res.risk)}. Individual models range from ${riskPct(lows)} to ${riskPct(highs)}.`);
  }

  function renderReliability(res) {
    const level = res.reliability.level;
    const bars = [1, 2, 3].map((n) => h('i', { class: n <= { low: 1, moderate: 2, high: 3 }[level] ? 'on' : null }));
    reliabilityEl.replaceChildren(
      h('div', { class: 'rd-reliab-row' },
        h('span', { class: `signal signal-${level}`, 'aria-hidden': 'true' }, bars),
        h('p', null, h('strong', null, `Reliability: ${level[0].toUpperCase()}${level.slice(1)}`), h('span', { class: 'rd-muted' }, res.reliability.summary))),
      h('details', { class: 'mini' },
        h('summary', null, 'How is this judged?'),
        h('p', null, 'A rule of thumb from how many measurements were provided, how many models agree, and whether values fall inside the range the models were trained on. It is not a statistical confidence interval.')));
  }

  function renderVotes(res) {
    const agreeing = res.label === 'ckd' ? res.votes.ckd : res.votes.notckd;
    votesHead.textContent = `${res.votes.ckd} of ${res.votes.total} models say CKD. The ensemble is the average of their risks.`;
    votesList.replaceChildren(...res.models.map((m) => {
      const spec = schema.models.find((x) => x.key === m.key);
      return h('li', { class: 'vote', 'data-vote': m.vote },
        h('span', { class: 'vote-name', title: spec ? spec.blurb : '' }, m.name),
        h('span', { class: 'vote-bar', 'aria-hidden': 'true' }, h('i', { style: { width: `${Math.max(1.5, m.risk * 100)}%` } })),
        h('span', { class: 'vote-risk' }, riskPct(m.risk)),
        h('span', { class: 'vote-chip' }, m.vote === 'ckd' ? 'CKD' : 'Not CKD'));
    }));
    agreeEl.textContent = `${agreeing} of ${res.votes.total} models agree.`;
  }

  function renderDrivers(res) {
    const ex = res.explanation;
    if (!ex) return;
    const total = ex.contributions;
    const biggest = Math.max(...total.map((c) => Math.abs(c.delta)), 0);
    const shift = Math.abs(res.risk - ex.baselineRisk) < 0.02 ? 'keep' : 'move';
    driversCaption.textContent = `Starting from a typical healthy profile (${riskPct(ex.baselineRisk)} risk), the values you entered ${shift} the estimate ${shift === 'keep' ? 'at' : 'to'} ${riskPct(res.risk)}. Bars show the change in risk, in percentage points.`;

    if (biggest < 0.01) {
      driversList.replaceChildren(h('li', { class: 'rd-muted' }, 'Every value sits close to the healthy reference, so no single measurement moves the estimate.'));
      driversMore.hidden = true;
      return;
    }
    const visible = showAll ? total : total.slice(0, 8);
    driversList.replaceChildren(...visible.map((c) => {
      const up = c.delta >= 0;
      const width = `${(Math.abs(c.delta) / biggest) * 50}%`;
      return h('li', { class: `driver ${up ? 'up' : 'down'}${Math.abs(c.delta) < 0.005 ? ' faint' : ''}` },
        h('span', { class: 'd-label' }, c.label, h('em', null, c.display)),
        h('span', { class: 'd-bar', 'aria-hidden': 'true' }, h('i', { style: { width } })),
        h('span', { class: 'd-val' }, signedPts(c.delta)));
    }));
    driversMore.hidden = total.length <= 8;
    driversMore.textContent = showAll ? 'Show fewer' : `Show all ${total.length}`;
  }

  function renderQuality(res) {
    const missing = new Set(res.completeness.missing);
    cells.setAttribute('aria-label', `${res.completeness.provided} of ${res.completeness.total} measurements provided`);
    cells.replaceChildren(...schema.features.map((f) =>
      h('i', { class: missing.has(f.key) ? 'cell' : 'cell on', title: `${f.label}: ${missing.has(f.key) ? 'not provided' : 'provided'}` })));
    cellsText.textContent = `${res.completeness.provided} of ${res.completeness.total} measurements provided.`;
    notesList.replaceChildren(...res.notes.map((n) =>
      h('li', { class: `note note-${n.level}` }, icon(n.level === 'warn' ? 'warn' : 'info', 16), h('span', null, n.message))));
  }

  /* ------------------------------------------------------------------- public */
  function showResult(res, inputs) {
    const first = result === null;
    const previous = result;
    result = res;
    empty.hidden = true;
    errorEl.hidden = true;
    resultEl.hidden = false;
    stale.hidden = true;

    const band = bandOf(res.risk, bands);
    root.dataset.band = band.key;
    bandChip.textContent = `${band.label} risk`;
    bandChip.dataset.band = band.key;
    decisionEl.textContent = res.label === 'ckd' ? 'The ensemble predicts CKD.' : 'The ensemble predicts not CKD.';
    announce.textContent = `Estimated CKD risk ${riskText(res.risk)} percent, ${band.label.toLowerCase()}. ${decisionEl.textContent}`;
    animateNumber(previous ? previous.risk : 0, res.risk);

    renderStrip(res, first);
    renderReliability(res);
    renderVotes(res);
    renderDrivers(res);
    renderQuality(res);
    whatIf.setContext(inputs, res);
  }

  function showEmpty() {
    result = null;
    pinEls.forEach((p) => p.remove());
    pinEls.clear();
    delete root.dataset.band;
    resultEl.hidden = true;
    errorEl.hidden = true;
    empty.hidden = false;
  }

  function showError(message) {
    errorEl.replaceChildren(icon('warn', 18), h('p', null, message));
    errorEl.hidden = false;
  }

  return {
    showResult, showEmpty, showError,
    clearError: () => { errorEl.hidden = true; },
    setBusy: (busy) => { loading.hidden = !busy; },
    setStale: (value) => { if (result) stale.hidden = !value; },
    get hasResult() { return result !== null; },
    get result() { return result; },
  };
}
