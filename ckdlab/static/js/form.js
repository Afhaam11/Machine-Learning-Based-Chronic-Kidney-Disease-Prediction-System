/* The patient form. Built entirely from /api/schema, so adding a measurement on the server
   adds it here too. Blank is a valid answer for every field: it means "not measured". */

import { h, icon, fmt, snap, scaleFor, clamp } from './util.js';

function parseNumber(text) {
  let t = text.trim();
  if (!t) return { empty: true };
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(t)) t = t.replace(/,/g, '');   // 8,400
  else t = t.replace(',', '.');                                          // 4,5
  if (!/^[+-]?(\d+\.?\d*|\.\d+)$/.test(t)) return { error: 'Enter a number.' };
  return { value: Number(t) };
}

export function createForm(root, schema, hooks) {
  const fields = new Map();
  const groupCounters = new Map();
  const groupTotals = new Map();
  let live = true;
  let busy = false;

  /* ------------------------------------------------------------ shared row bits */
  function labelCell(feature, controlId, rowEl) {
    const hint = h('p', { class: 'row-hint', id: `${controlId}-hint`, hidden: true }, feature.hint);
    const button = h('button', {
      type: 'button', class: 'hint-btn', 'aria-label': `About ${feature.label.toLowerCase()}`,
      'aria-expanded': 'false', 'aria-controls': hint.id,
      onclick: () => {
        const open = hint.hidden;
        hint.hidden = !open;
        button.setAttribute('aria-expanded', String(open));
      },
    }, icon('info', 15));
    const labelEl = feature.kind === 'number'
      ? h('label', { class: 'row-label', for: controlId }, feature.label)
      : h('span', { class: 'row-label', id: `${controlId}-label` }, feature.label);
    rowEl.append(h('div', { class: 'row-head' }, labelEl, button));
    return hint;
  }

  /* --------------------------------------------------------------- number field */
  function numberField(feature) {
    const id = `f-${feature.key}`;
    const state = { value: null, error: null, serverError: null };
    const input = h('input', {
      id, class: 'num', type: 'text', inputmode: 'decimal', autocomplete: 'off', spellcheck: 'false',
      'aria-describedby': `${id}-note`,
    });
    const marker = h('i', { class: 'range-marker', 'data-state': 'none' });
    const [uLo, uHi] = feature.ui;
    const scale = scaleFor(feature);
    const refEl = feature.ref
      ? h('i', {
        class: 'range-ref',
        style: {
          left: `${clamp(scale.toPos(feature.ref[0]), 0, 1) * 100}%`,
          width: `${(clamp(scale.toPos(feature.ref[1]), 0, 1) - clamp(scale.toPos(feature.ref[0]), 0, 1)) * 100}%`,
        },
      })
      : null;
    const note = h('p', { class: 'row-note', id: `${id}-note` });
    const row = h('div', { class: 'row', 'data-key': feature.key, 'data-kind': 'number' });
    const hint = labelCell(feature, id, row);
    row.append(
      h('div', { class: 'row-input', style: { '--unit-ch': String(feature.unit.length) } }, input, feature.unit ? h('span', { class: 'unit', 'aria-hidden': 'true' }, feature.unit) : null),
      h('div', { class: 'range', 'aria-hidden': 'true' }, h('i', { class: 'range-track' }), refEl, marker),
      note,
      hint,
    );

    function read() {
      const parsed = parseNumber(input.value);
      state.serverError = null;
      if (parsed.empty) { state.value = null; state.error = null; return; }
      if (parsed.error) { state.value = null; state.error = parsed.error; return; }
      if (parsed.value < feature.lo || parsed.value > feature.hi) {
        state.value = null;
        state.error = `${feature.label} must be between ${fmt(feature.lo, feature.decimals)} and ${fmt(feature.hi, feature.decimals)}${feature.unit ? ` ${feature.unit}` : ''}.`;
        return;
      }
      state.value = parsed.value;
      state.error = null;
    }

    function paint() {
      const v = state.value;
      const message = state.error || state.serverError;
      input.setAttribute('aria-invalid', message ? 'true' : 'false');
      row.classList.toggle('has-value', v !== null);
      row.classList.toggle('has-error', Boolean(message));

      // range strip marker
      if (v === null) {
        marker.dataset.state = 'none';
      } else {
        const pos = scale.toPos(v);
        marker.style.left = `${clamp(pos, 0, 1) * 100}%`;
        marker.dataset.clamped = pos < 0 || pos > 1 ? 'true' : 'false';
        marker.dataset.state = !feature.ref ? 'plain' : v < feature.ref[0] ? 'low' : v > feature.ref[1] ? 'high' : 'ok';
      }

      // note line
      note.replaceChildren();
      if (message) {
        note.append(h('span', { class: 'note-error' }, message));
        return;
      }
      if (feature.ref) {
        const range = `${fmt(feature.ref[0], feature.decimals)} to ${fmt(feature.ref[1], feature.decimals)}`;
        let text = `Typical ${range} ${feature.unit}`.trim();
        let tone = 'muted';
        if (v !== null) {
          tone = v < feature.ref[0] || v > feature.ref[1] ? 'flag' : 'ok';
          text = v < feature.ref[0] ? `Below typical (${range})` : v > feature.ref[1] ? `Above typical (${range})` : `In typical range (${range})`;
        }
        note.append(h('span', { class: `note-main tone-${tone}` }, text));
      }
      const tr = feature.trainingRange;
      if (v !== null && tr && (v < tr[0] || v > tr[1])) {
        note.append(h('span', { class: 'note-warn' }, `Outside the training range (${fmt(tr[0], feature.decimals)} to ${fmt(tr[1], feature.decimals)})`));
      }
    }

    input.addEventListener('input', () => { read(); paint(); changed('user'); });
    input.addEventListener('blur', () => { if (state.value !== null) { /* tidy display */ input.value = String(state.value); } });
    input.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      event.preventDefault();
      const base = state.value ?? (feature.ref ? (feature.ref[0] + feature.ref[1]) / 2 : (uLo + uHi) / 2);
      const delta = (event.key === 'ArrowUp' ? 1 : -1) * feature.step * (event.shiftKey ? 10 : 1);
      const next = clamp(snap(feature, base + delta), feature.lo, feature.hi);
      input.value = String(next);
      read(); paint(); changed('user');
    });

    paint();
    return {
      el: row,
      get: () => state.value,
      invalid: () => Boolean(state.error || state.serverError),
      set(value) { input.value = value === null || value === undefined ? '' : String(value); read(); paint(); },
      setServerError(message) { state.serverError = message; paint(); },
      focus: () => input.focus(),
    };
  }

  /* ---------------------------------------------- segmented field (binary/ordinal) */
  function segmentedField(feature) {
    const name = `f-${feature.key}`;
    const state = { serverError: null };
    const options = feature.kind === 'binary'
      ? feature.options.map((o) => ({ value: o.value, label: o.label, adverse: o.adverse }))
      : feature.levels.map((l) => ({
        value: l.value, label: l.label,
        adverse: feature.normalLevels.length > 0 && !feature.normalLevels.includes(l.value),
      }));
    const radios = [];
    const labels = options.map((option, i) => {
      const radio = h('input', {
        type: 'radio', name, id: `${name}-${i}`, value: String(i),
        onchange: () => { state.serverError = null; paint(); changed('user'); },
      });
      radios.push(radio);
      return h('label', { class: 'seg-opt', 'data-adverse': option.adverse ? 'true' : null }, radio, h('span', null, option.label));
    });
    const group = h('div', { class: `seg${options.length > 3 ? ' seg-wide' : ''}`, role: 'radiogroup', 'aria-labelledby': `${name}-label` }, labels);
    const clear = h('button', {
      type: 'button', class: 'clear-btn', hidden: true, 'aria-label': `Clear ${feature.label.toLowerCase()}`,
      onclick: () => { radios.forEach((r) => { r.checked = false; }); paint(); changed('user'); radios[0].focus(); },
    }, icon('x', 14));
    const note = h('p', { class: 'row-note', id: `${name}-note` });
    const row = h('div', { class: 'row row-seg', 'data-key': feature.key, 'data-kind': feature.kind });
    const hint = labelCell(feature, name, row);
    row.append(h('div', { class: 'row-input row-input-seg' }, group, clear), note, hint);

    const get = () => {
      const index = radios.findIndex((r) => r.checked);
      return index === -1 ? null : options[index].value;
    };

    function paint() {
      const value = get();
      row.classList.toggle('has-value', value !== null);
      row.classList.toggle('has-error', Boolean(state.serverError));
      clear.hidden = value === null;
      note.replaceChildren(state.serverError ? h('span', { class: 'note-error' }, state.serverError) : '');
    }

    paint();
    return {
      el: row,
      get,
      invalid: () => Boolean(state.serverError),
      set(value) {
        const index = options.findIndex((o) =>
          feature.kind === 'binary' ? o.value === value : value !== null && Math.abs(o.value - Number(value)) < 1e-9);
        radios.forEach((r, i) => { r.checked = i === index; });
        state.serverError = null;
        paint();
      },
      setServerError(message) { state.serverError = message; paint(); },
      focus: () => radios[Math.max(0, radios.findIndex((r) => r.checked))].focus(),
    };
  }

  /* -------------------------------------------------------------------- layout */
  const sampleButtons = new Map();
  const sampleNote = h('p', { class: 'sample-note', hidden: true, 'aria-live': 'polite' });

  function loadSample(sample) {
    setInputs(sample.inputs, { silent: true });
    sampleButtons.forEach((btn, id) => btn.setAttribute('aria-pressed', String(id === sample.id)));
    sampleNote.textContent = sample.description;
    sampleNote.hidden = false;
    summarize();
    hooks.onSample(sample);
  }

  const head = h('header', { class: 'sheet-head' },
    h('div', { class: 'sheet-intro' },
      h('h1', { id: 'form-title', tabindex: '-1' }, 'Patient measurements'),
      h('p', { class: 'lede' }, 'Fill in what you have. Blank fields are estimated from typical values, and the result tells you how much that matters.')),
    h('div', { class: 'samples', role: 'group', 'aria-labelledby': 'samples-label' },
      h('span', { class: 'samples-label', id: 'samples-label' }, 'Load a sample'),
      h('div', { class: 'samples-row' }, schema.samples.map((sample) => {
        const btn = h('button', {
          type: 'button', class: 'sample-btn', 'aria-pressed': 'false', title: sample.description,
          onclick: () => loadSample(sample),
        }, sample.title);
        sampleButtons.set(sample.id, btn);
        return btn;
      })),
      sampleNote),
  );

  const progressCount = h('strong', null, '0 of 24');
  const progressFill = h('i');
  const clearAllBtn = h('button', { type: 'button', class: 'link-btn', onclick: () => clearAll() }, 'Clear all');
  const progress = h('div', { class: 'progress' },
    h('p', { class: 'progress-text' }, progressCount, ' measurements provided'),
    h('div', { class: 'progress-bar', 'aria-hidden': 'true' }, progressFill),
    clearAllBtn);

  const sections = schema.groups.map((group) => {
    const members = schema.features.filter((f) => f.group === group.id);
    groupTotals.set(group.id, members.length);
    const counter = h('span', { class: 'group-count' });
    groupCounters.set(group.id, counter);
    const rows = members.map((feature) => {
      const field = feature.kind === 'number' ? numberField(feature) : segmentedField(feature);
      fields.set(feature.key, field);
      return field.el;
    });
    return h('section', { class: 'group', 'aria-labelledby': `group-${group.id}` },
      h('div', { class: 'group-head' },
        h('h2', { id: `group-${group.id}` }, group.label),
        counter,
        h('p', { class: 'group-desc' }, group.description)),
      h('div', { class: 'rows' }, rows));
  });

  const submitBtn = h('button', { type: 'submit', class: 'btn btn-primary', id: 'assess-btn' }, 'Assess risk');
  const submitNote = h('p', { class: 'submit-note', id: 'submit-note' });
  const liveToggle = h('input', {
    type: 'checkbox', id: 'live-toggle', checked: true,
    onchange: () => { live = liveToggle.checked; hooks.onLiveChange?.(live); },
  });
  const foot = h('footer', { class: 'sheet-foot' },
    h('div', { class: 'sheet-actions' }, submitBtn,
      h('label', { class: 'switch', for: 'live-toggle', title: 'Re-run the assessment automatically after each edit' },
        liveToggle, h('span', { class: 'switch-ui', 'aria-hidden': 'true' }), h('span', null, 'Update as I type'))),
    submitNote);
  submitBtn.setAttribute('aria-describedby', 'submit-note');

  root.replaceChildren(head, progress, ...sections, foot);
  root.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!submitBtn.disabled) hooks.onSubmit();
  });
  root.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); root.requestSubmit(); }
  });

  /* ------------------------------------------------------------------- state */
  function getInputs() {
    const inputs = {};
    fields.forEach((field, key) => { const v = field.get(); if (v !== null) inputs[key] = v; });
    return inputs;
  }
  const providedCount = () => Object.keys(getInputs()).length;
  const isValid = () => ![...fields.values()].some((f) => f.invalid());

  function summarize() {
    const total = schema.features.length;
    const count = providedCount();
    progressCount.textContent = `${count} of ${total}`;
    progressFill.style.width = `${(count / total) * 100}%`;
    clearAllBtn.hidden = count === 0;

    schema.groups.forEach((group) => {
      const provided = schema.features.filter((f) => f.group === group.id && fields.get(f.key).get() !== null).length;
      groupCounters.get(group.id).textContent = `${provided} of ${groupTotals.get(group.id)}`;
    });

    const valid = isValid();
    const enough = count >= schema.minFields;
    submitBtn.disabled = busy || !valid || !enough;
    submitNote.textContent = !valid ? 'Fix the highlighted fields to continue.'
      : !enough ? `Enter at least ${schema.minFields} measurements to assess risk.` : '';
  }

  function changed(source) {
    if (source === 'user') {
      sampleNote.hidden = true;
      sampleButtons.forEach((btn) => btn.setAttribute('aria-pressed', 'false'));
    }
    summarize();
    hooks.onChange?.({ source });
  }

  function setInputs(values, { silent = false } = {}) {
    fields.forEach((field, key) => field.set(values[key] === undefined ? null : values[key]));
    summarize();
    if (!silent) changed('program');
  }

  function setValue(key, value) {
    fields.get(key)?.set(value);
    changed('program');
  }

  function clearAll() {
    setInputs({}, { silent: true });
    sampleNote.hidden = true;
    sampleButtons.forEach((btn) => btn.setAttribute('aria-pressed', 'false'));
    summarize();
    hooks.onClear?.();
  }

  function markErrors(details) {
    let first = null;
    (details || []).forEach((d) => {
      const field = fields.get(d.field);
      if (field) { field.setServerError(d.message); first = first || field; }
    });
    summarize();
    first?.focus();
  }

  function setBusy(value) {
    busy = value;
    submitBtn.classList.toggle('is-busy', value);
    submitBtn.textContent = value ? 'Assessing…' : 'Assess risk';
    summarize();
  }

  summarize();
  return {
    el: root, getInputs, setInputs, setValue, clearAll, providedCount, isValid, markErrors, setBusy,
    get live() { return live; },
  };
}
