/* ============================================================
   Prescription app — fill on the phone, preview the A4 sheet,
   send the PDF to WhatsApp through Android's share sheet.
   Nothing is stored: every prescription starts from a blank form.
   ============================================================ */
'use strict';

const $   = (s, r = document) => r.querySelector(s);
const $$  = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]));
const val = id => ($('#' + id)?.value || '').trim();
const br  = s => esc(s).replace(/\n/g, '<br>');

const MAX_DRUGS = 8;
const MAX_STEPS = 4;

/* ---------- Urdu vocabulary — wording agreed with the doctor ---------- */
const UR = {
  drop:  'ایک قطرہ',                     // always one drop — never two
  freq: {
    drops: ['دن میں ایک بار', 'دن میں 2 بار', 'دن میں 3 بار', 'دن میں 4 بار',
            'ہر 6 گھنٹے بعد', 'ہر 4 گھنٹے بعد', 'ہر 3 گھنٹے بعد', 'ہر 2 گھنٹے بعد', 'ہر 1 گھنٹے بعد'],
    other: ['دن میں 4 بار', 'دن میں 3 بار', 'دن میں 2 بار', 'دن میں ایک بار'],
  },
  times: ['صبح', 'دوپہر', 'شام', 'رات'],
  eye:   ['دائیں آنکھ میں', 'بائیں آنکھ میں', 'دونوں آنکھوں میں'],
  unit:  { din: ['دن', 'دن'], hafta: ['ہفتہ', 'ہفتے'], mahina: ['مہینہ', 'مہینے'] },   // [singular, plural]
  then:  'پھر',
  end:   ['جاری رکھیں', 'پھر بند کر دیں'],
};

/* The doctor's examination order, front of the eye to the back. The form and
   the printed sheet are both generated from this list, so the order is set
   here once; a row the doctor leaves empty never reaches the patient's copy. */
const EXAM = [
  ['eyelid', 'Eyelid'], ['adnexa', 'Adnexa'], ['conj', 'Conjunctiva'], ['sclera', 'Sclera'],
  ['cornea', 'Cornea'], ['ac', 'AC'], ['iris', 'Iris'], ['lens', 'Lens'],
  ['vit', 'Vitreous'], ['fundus', 'Fundus'],
];

/* ---------- Hidayat — one button fills in a ready-made set --------------
   Transcribed from the doctor's own printed cards (Sept 2026). Two things
   were deliberately left out of the laser sets: the other centre's
   check-up fee note, and the line telling patients to ring that centre.
   A line ending in a colon prints as a sub-heading with no bullet.
   To add a set, copy an entry: `label` is the button, `lines` is the text,
   one instruction per line. Buttons append, so sets can be combined, and
   the doctor edits the box afterwards. */
const HID_7DAY = [
  'مندرجہ ذیل احتیاطیں 7 دن تک جاری رکھیں:',
  'آنکھوں کو کسی صورت مت ملیئے اور نہ ہی اوپر سے دبائیں',
  'آنکھوں کو صابن اور شیمپو سے بچائیں',
  'آنکھیں کھول کر پانی کے چھینٹے مت ماریں',
];

/* PRK and CXL are the same card with one word changed, so they share this */
const laserCard = procedure => [
  ...HID_7DAY,
  'ایک وقت میں ایک سے زائد قسم کے قطرے استعمال کرنے ہوں تو درمیان میں تقریباً 5 منٹ کا وقفہ ضروری ہے',
  'لیزر کروانے کے بعد ڈاکٹر کی ہدایات کے مطابق قطروں کا استعمال جاری رکھیں اور قطروں کا استعمال ڈاکٹر کے کہنے کے بعد ہی چھوڑیں',
  'آنکھوں میں ڈالنے والے قطرے آپ تب تک استعمال کرنے ہیں جب تک آپ جاگ رہے ہیں، رات کو نیند سے جاگ کر قطرے استعمال کرنے کی ضرورت نہیں ہے',
  'لیزر کروانے کے بعد پہلے 3 سے 4 روز تک آنکھوں میں درد اور چبھن ہو سکتی ہے، آنکھوں سے پانی بھی زیادہ نکل سکتا ہے ۔ یہ سب نارمل اور روٹین کی بات ہے، اس سے گھبرانے کی ضرورت نہیں ۔ چند دن بعد یہ درد اور چبھن خود بخود ختم ہو جائے گی',
  'آنکھوں سے زیادہ پانی نکلنے کی صورت میں آنکھوں کو زیادہ سے زیادہ بند رکھیں، اور ٹشو پیپر سے آنکھوں کو نیچے سے صاف کریں',
  `${procedure} کروانے کے بعد زیادہ تکلیف کی صورت میں آنکھوں پر کسی ٹھنڈی چیز سے ٹکور کریں`,
  'ٹیوب لائٹ یا بلب کی روشنی سے کوئی پرہیز نہیں، دھوپ کی شدت سے بچنے کے لیے دھوپ کا چشمہ (sunglasses) استعمال کریں',
  'لیزر کروانے کے بعد پہلے 7 دن تک آنکھوں میں پانی کے چھینٹے مت ماریں ۔ گردن سے نیچے تک نہا سکتے ہیں ۔ چہرے کو صاف کرنے کے لیے گیلا تولیہ یا (Wet Wipes) استعمال کریں',
  'نظر کو Stabilize ہونے میں دو سے آٹھ ہفتے لگ سکتے ہیں',
];

const HIDAYAT = [
  { label: 'Cataract', lines: [
    'گھر جا کر اگلے دن پٹی اُتار کر دھوپ کی عینک استعمال کریں',
    'دوائیں ڈسچارج شیٹ میں دی گئی ہدایات کے مطابق استعمال کریں',
    'وزن اٹھانے یا سر جھکانے سے پرہیز کریں',
    'ایک ماہ تک نماز اشاروں سے ادا کریں',
    'سخت چبا کر کھانے والی چیزوں سے پرہیز کریں',
    'کھانے میں مرچیں اور چکنائی کم استعمال کریں',
    'تمباکو نوشی سے مکمل پرہیز کریں',
    'کھانسی یا قبض کی صورت میں قریبی ڈاکٹر سے رجوع کریں',
    'ڈیابیٹس اور ہائی بلڈ پریشر کے مریض پرہیز اور علاج باقاعدگی سے جاری رکھیں',
    'نہاتے وقت یا منہ دھوتے وقت صابن والا پانی آنکھ میں نہ جانے دیں',
    'معائنے کے لیے مقررہ وقت اور تاریخ پر تشریف لائیں',
    'ایمرجنسی کی صورت میں پہلے بھی دکھا سکتے ہیں',
  ] },
  /* From VKC-Patient-Brochure-Urdu.pdf, trimmed on the doctor's instruction:
     Do's 1-3 and the last dropped, Don'ts 4 and the last dropped, the five
     "see your eye doctor" bullets condensed into the closing line, and the
     humidifier line dropped. Every line is a complete instruction that stands
     on its own — the brochure's یہ کریں / ان سے پرہیز کریں headings are gone,
     because a patient reading one line should not need the heading above it. */
  { label: 'General precautions', lines: [
    'چہرہ اور ہاتھ بار بار دھوئیں، خاص طور پر باہر سے آنے کے بعد',
    'بستر کی چادریں اور تکیے کے غلاف صاف اور گرد سے پاک رکھیں',
    'آنکھوں کو نہ ملیں اور نہ دبائیں، خارش ہو تب بھی نہیں',
    'گرد و غبار، پالتو جانوروں کے بال، دھوئیں اور تیز ہوا سے بچیں',
    'خارش یا سوجن کے دنوں میں کانٹیکٹ لینز استعمال نہ کریں',
    'موبائل، ٹی وی یا کمپیوٹر زیادہ دیر تک نہ دیکھیں، تھوڑی تھوڑی دیر بعد آنکھوں کو آرام دیں',
    'ڈاکٹر کے مشورے کے بغیر کوئی بھی قطرہ، خاص طور پر اسٹیرائیڈ قطرے، خود استعمال نہ کریں',
    'آنکھ میں درد ہو، روشنی کی حساسیت یا دھندلا پن اچانک بڑھ جائے، یا علامات کم نہ ہوں تو فوراً اپنے آنکھوں کے ڈاکٹر سے رجوع کریں',
  ] },
  { label: 'PRK',   lines: laserCard('پی آر کے (PRK)') },
  { label: 'CXL',   lines: laserCard('سی ایکس ایل (CXL)') },
  { label: 'LASIK', lines: [
    ...HID_7DAY,
    'ایک وقت میں ایک سے زائد قسم کے قطرے استعمال کرنے ہوں تو درمیان میں تقریباً 5 منٹ کا وقفہ ضروری ہے',
    'لیزر کروانے کے بعد چند گھنٹوں کے لیے آنکھوں میں درد اور چبھن ہو سکتی ہے، اس سے مت گھبرائیں ۔ یہ کچھ گھنٹوں بعد خود بخود ختم ہو جائے گی',
    'آنکھوں میں ڈالنے والے قطرے آپ تب تک استعمال کرنے ہیں جب تک آپ جاگ رہے ہیں، رات کو نیند سے جاگ کر قطرے استعمال کرنے کی ضرورت نہیں ہے',
    'لیزر کروانے کے بعد موبائل فون یا لیپ ٹاپ کے استعمال سے کوئی حرج نہیں لیکن پہلے ہفتے ان کا استعمال کم سے کم رکھیں',
    'ٹیوب لائٹ یا بلب کی روشنی سے کوئی پرہیز نہیں، دھوپ کی شدت سے بچنے کے لیے دھوپ کا چشمہ (sunglasses) استعمال کریں',
    'لیزر کروانے کے بعد پہلے 7 دن تک آنکھوں میں پانی کے چھینٹے مت ماریں ۔ گردن سے نیچے تک نہا سکتے ہیں ۔ چہرے کو صاف کرنے کے لیے گیلا تولیہ یا (Wet Wipes) استعمال کریں',
    'دوبارہ معائنے کے لیے ڈاکٹر جب بھی بلائیں، برائے مہربانی چیک اپ کے لیے ضرور آئیں',
    'لیزر کے پہلے کچھ دن تک آنکھوں میں سرخ نشان ہو سکتے ہیں ۔ یہ بالکل نارمل ہے اور اس سے نظر کو کوئی نقصان نہیں ۔ یہ سرخ نشان کچھ ہی وقت میں اپنے آپ ختم ہو جائیں گے',
  ] },
];

/* ---------- state ---------- */
const newStep = () => ({ freq: '', times: [], eye: '', dur: '', unit: 'din', text: null });
const newDrug = () => ({ name: '', form: 'drops', steps: [newStep()], end: '' });
const S = { rel: '', ageunit: 'y', drugs: [newDrug()] };   // rel: S/o · W/o · D/o, or none

/* One taper step -> one Urdu line. `text` holds a hand edit; any button
   press clears it, so buttons rebuild and typing tweaks afterwards. */
function composeStep(st, j, form){
  if (st.text !== null) return st.text;
  const n = parseInt(st.dur, 10);
  if (!(st.freq || st.times.length || st.eye || n > 0)) return '';
  const drops = form === 'drops';
  const p = [];
  if (drops) p.push(UR.drop);
  if (st.freq) p.push(st.freq);
  if (st.times.length) p.push(UR.times.filter(t => st.times.includes(t)).join('، '));
  if (drops && st.eye) p.push(st.eye);
  if (n > 0) p.push(`${n} ${UR.unit[st.unit][n === 1 ? 0 : 1]}`);
  return (j ? UR.then + ' ۔ ' : '') + p.join(' ۔ ');
}
const doseLines = d => [...d.steps.map((s, j) => composeStep(s, j, d.form)).filter(Boolean), ...(d.end ? [d.end] : [])];

/* ---------- small helpers ---------- */
const pad2     = n => String(n).padStart(2, '0');
const fmtDate  = d => `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}`;
const fmtTime  = d => { const h = d.getHours(); return `${h % 12 || 12}:${pad2(d.getMinutes())} ${h < 12 ? 'am' : 'pm'}`; };
const isoToDMY = s => s ? s.split('-').reverse().join('/') : '';

let toastT;
function toast(msg, ms = 2600){
  const t = $('#toast'); t.textContent = msg; t.classList.add('on');
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), ms);
}

/* sph / cyl / add carry a sign the numeric keypad can't type */
const sgn = (id, ph, s) =>
  `<div class="sgn"><button type="button" data-sign="${id}">${s}</button><input type="text" inputmode="decimal" id="${id}" placeholder="${ph}" autocomplete="off"></div>`;
function signed(id){
  const raw = val(id);
  if (!raw || /^[+-]/.test(raw)) return raw;
  const n = parseFloat(raw);
  if (isNaN(n)) return raw;
  if (n === 0) return '0.00';
  return ($(`[data-sign="${id}"]`).textContent === '−' ? '-' : '+') + n.toFixed(2);
}
/* the IOP correction factor keeps its number pad, so its sign comes from the ± button */
const cfVal = id => {
  const raw = val(id);
  if (!raw || /^[+-]/.test(raw)) return raw;
  return ($(`[data-sign="${id}"]`)?.textContent === '−' ? '-' : '+') + raw;
};

/* ============================================================
   FORM — generated rows
   ============================================================ */
/* RAPD closes the examination: one box, not a pair, because it is recorded
   for the affected eye ("+ve right eye") rather than eye by eye */
$('#exam').innerHTML = EXAM.map(([k, lab]) => `
  <div class="f"><label>${lab}</label>
    <div class="eyepair"><b>R</b><input type="text" id="ex-${k}-r" autocomplete="off"><b>L</b><input type="text" id="ex-${k}-l" autocomplete="off"></div>
  </div>`).join('')
  + `<div class="f"><label for="ex-rapd">RAPD</label>
       <input type="text" id="ex-rapd" autocomplete="off" placeholder="e.g. +ve right eye"></div>`;

$('#refr').innerHTML = [['r', 'Right eye'], ['l', 'Left eye']].map(([e, lab]) => `
  <div class="f"><label>${lab}</label>
    <div class="grid-3">
      ${sgn(`ref-${e}-sph`, 'Sph', '−')}${sgn(`ref-${e}-cyl`, 'Cyl', '−')}
      <input type="text" inputmode="numeric" id="ref-${e}-axis" placeholder="Axis" autocomplete="off">
    </div>
    <div class="grid-3" style="margin-top:8px">
      <input type="text" id="ref-${e}-va" placeholder="VA" autocomplete="off">
      ${sgn(`ref-${e}-add`, 'Add', '+')}
      <input type="text" id="ref-${e}-near" placeholder="Near" autocomplete="off">
    </div>
  </div>`).join('');

document.addEventListener('click', e => {
  const b = e.target.closest('[data-sign]');
  if (b) b.textContent = b.textContent === '−' ? '+' : '−';
});

/* one-of-these chips. S/o · W/o · D/o clears when you tap the chosen one again,
   because plenty of patients need no relation printed at all; a `data-sticky`
   group (the age unit) always keeps one chosen. */
$$('[data-single]').forEach(box => {
  const k = box.dataset.single, paint = () => $$('.chip', box).forEach(x => x.classList.toggle('on', x.dataset.v === S[k]));
  box.addEventListener('click', e => {
    const c = e.target.closest('.chip'); if (!c) return;
    S[k] = (S[k] === c.dataset.v && !box.hasAttribute('data-sticky')) ? '' : c.dataset.v;
    paint();
  });
  paint();
});

/* ---------- Hidayat ---------- */
$('#hid-sets').innerHTML = HIDAYAT.map((h, i) => `<button class="chip" data-hid="${i}">+ ${esc(h.label)}</button>`).join('')
  + '<button class="chip" data-hid-clear>Clear</button>';

$('#hid-sets').addEventListener('click', e => {
  const ta = $('#hid');
  if (e.target.closest('[data-hid-clear]')){
    if (ta.value.trim() && !confirm('Clear the Hidayat?')) return;
    ta.value = ''; return;
  }
  const b = e.target.closest('[data-hid]'); if (!b) return;
  const set = HIDAYAT[+b.dataset.hid];
  const have = ta.value.split('\n').map(l => l.trim());
  const add = set.lines.filter(l => !have.includes(l));      // tapping twice must not duplicate
  if (!add.length) return toast(`${set.label} is already there`);
  ta.value = (ta.value.trim() ? ta.value.trim() + '\n' : '') + add.join('\n');
  toast(`${set.label} added — edit the text if you need to`);
});

/* ---------- IOP: Final = Pre + CF -------------------------------------
   Filled in as he types, but the moment he types in Final himself it is his;
   clearing it hands the sum back. */
function recalcIop(e){
  const out = $(`#iop-${e}-final`);
  if (out.dataset.manual) return;
  const pre = parseFloat(val(`iop-${e}-pre`));
  if (isNaN(pre)) return void (out.value = '');
  const cf = parseFloat(cfVal(`iop-${e}-cf`));
  out.value = String(Math.round((pre + (isNaN(cf) ? 0 : cf)) * 10) / 10);
}
$('main').addEventListener('input', e => {
  const m = e.target.id?.match(/^iop-([rl])-(pre|cf|final)$/); if (!m) return;
  if (m[2] === 'final') e.target.dataset.manual = e.target.value.trim() ? '1' : '';
  recalcIop(m[1]);
});
$('main').addEventListener('click', e => {          // the ± button flips the sign of CF
  const m = e.target.closest('[data-sign]')?.dataset.sign.match(/^iop-([rl])-cf$/);
  if (m) setTimeout(() => recalcIop(m[1]), 0);      // after the generic handler has flipped it
});

/* Enter on a one-line field moves to the next visible field */
$('main').addEventListener('keydown', e => {
  if (e.key !== 'Enter' || !e.target.matches('input') || e.target.matches('[data-name]')) return;
  e.preventDefault();
  const all = $$('main input, main textarea').filter(el => el.offsetParent);
  const next = all[all.indexOf(e.target) + 1];
  if (next) next.focus(); else e.target.blur();
});

/* ============================================================
   Rx — drug cards
   ============================================================ */
function renderDrugs(){
  $('#drugs').innerHTML = S.drugs.map((d, i) => {
    const lines = doseLines(d);
    return `<div class="drug" data-i="${i}">
      <div class="hd"><span class="n">${i + 1}</span>
        <input type="text" data-name value="${esc(d.name)}" placeholder="Drug name" autocomplete="off" autocapitalize="characters" enterkeyhint="next">
        <button class="x" data-del aria-label="Remove drug">×</button></div>
      <button class="dosebtn${lines.length ? ' has' : ''}" data-dose>${lines.length
        ? `<span class="lines">${lines.map(esc).join('<br>')}</span>`
        : 'Set dosage · اردو'}</button>
    </div>`;
  }).join('');
  const full = S.drugs.length >= MAX_DRUGS;
  $('#adddrug').disabled = full;
  $('#adddrug').textContent = full ? `Maximum ${MAX_DRUGS} drugs` : '+ Add drug';
  countDrugs();
}
function countDrugs(){
  const n = S.drugs.filter(d => d.name.trim()).length;
  $('#rx-count').textContent = n ? `${n} / ${MAX_DRUGS}` : '';
}
const focusDrug = i => $$('#drugs [data-name]')[i]?.focus();

$('#drugs').addEventListener('input', e => {
  if (!e.target.matches('[data-name]')) return;
  S.drugs[+e.target.closest('.drug').dataset.i].name = e.target.value;
  countDrugs();
});

/* Enter walks to the next drug, adding a slot if needed — an empty slot is
   simply left off the sheet, which is how the doctor skips a number */
$('#drugs').addEventListener('keydown', e => {
  if (e.key !== 'Enter' || !e.target.matches('[data-name]')) return;
  e.preventDefault();
  const i = +e.target.closest('.drug').dataset.i;
  if (i + 1 < S.drugs.length) return focusDrug(i + 1);
  if (S.drugs.length < MAX_DRUGS){ S.drugs.push(newDrug()); renderDrugs(); focusDrug(i + 1); }
  else e.target.blur();
});

$('#drugs').addEventListener('click', e => {
  const card = e.target.closest('.drug'); if (!card) return;
  const i = +card.dataset.i, d = S.drugs[i];
  if (e.target.closest('[data-del]')){
    if ((d.name.trim() || doseLines(d).length) && !confirm(`Remove ${d.name.trim() || 'this drug'}?`)) return;
    if (S.drugs.length === 1) S.drugs[0] = newDrug(); else S.drugs.splice(i, 1);
    renderDrugs();
  } else if (e.target.closest('[data-dose]')) openPad(i);
});

$('#adddrug').onclick = () => {
  if (S.drugs.length >= MAX_DRUGS) return;
  S.drugs.push(newDrug()); renderDrugs(); focusDrug(S.drugs.length - 1);
};

/* ============================================================
   DOSAGE PAD
   ============================================================ */
let P = -1;
const isOn = (sel, v) => Array.isArray(sel) ? sel.includes(v) : sel === v;
const chips = (list, sel, key) => list.map(v =>
  `<button class="chip ur${isOn(sel, v) ? ' on' : ''}" data-k="${key}" data-v="${esc(v)}">${esc(v)}</button>`).join('');
const grp = (label, inner) => `<div class="grp"><span>${label}</span><div class="chips">${inner}</div></div>`;

function renderPad(){
  const d = S.drugs[P], drops = d.form === 'drops';
  $('#pad-title').textContent = d.name.trim() || `Drug ${P + 1}`;
  $$('#pad-form .chip').forEach(c => c.classList.toggle('on', c.dataset.v === d.form));
  $('#tlines').innerHTML = d.steps.map((st, j) => `
    <div class="tline" data-j="${j}">
      <div class="th"><b>${j ? `Step ${j + 1} · پھر` : 'Step 1'}</b>${j ? '<button class="rm" data-rmstep aria-label="Remove step">×</button>' : ''}</div>
      ${grp('How often', chips(UR.freq[d.form], st.freq, 'freq'))}
      ${grp('Time of day', chips(UR.times, st.times, 'times'))}
      ${drops ? grp('Eye', chips(UR.eye, st.eye, 'eye')) : ''}
      <div class="grp"><span>Duration</span><div class="dur">
        <input type="text" inputmode="numeric" pattern="[0-9]*" data-dur value="${esc(st.dur)}" placeholder="0" enterkeyhint="done">
        <div class="chips">${Object.keys(UR.unit).map(u =>
          `<button class="chip ur${st.unit === u ? ' on' : ''}" data-k="unit" data-v="${u}">${UR.unit[u][0]}</button>`).join('')}</div>
      </div></div>
      <div class="grp"><span>Line · tap to edit by hand</span>
        <textarea class="out" dir="rtl" rows="2" data-out>${esc(composeStep(st, j, d.form))}</textarea></div>
    </div>`).join('');
  const full = d.steps.length >= MAX_STEPS;
  $('#addline').disabled = full;
  $('#addline').textContent = full ? `Maximum ${MAX_STEPS} steps` : '+ پھر · add next step';
  $('#pad-end').innerHTML = chips(UR.end, d.end, 'end');
}

function openPad(i){ P = i; renderPad(); $('#padwrap').classList.add('on'); document.body.style.overflow = 'hidden'; pushLayer('pad'); }
function hidePad(){ $('#padwrap').classList.remove('on'); document.body.style.overflow = ''; renderDrugs(); }

$('#padwrap').addEventListener('click', e => {
  if (e.target.closest('[data-close]')) return history.back();
  const d = S.drugs[P];

  const form = e.target.closest('#pad-form .chip');
  if (form){
    d.form = form.dataset.v;
    d.steps.forEach(s => { s.text = null; if (!UR.freq[d.form].includes(s.freq)) s.freq = ''; });
    return renderPad();
  }
  if (e.target.closest('[data-rmstep]')){ d.steps.splice(+e.target.closest('.tline').dataset.j, 1); return renderPad(); }

  const c = e.target.closest('.chip[data-k]'); if (!c) return;
  const { k, v } = c.dataset;
  if (k === 'end'){ d.end = d.end === v ? '' : v; return renderPad(); }
  const st = d.steps[+c.closest('.tline').dataset.j];
  if (k === 'times') st.times = st.times.includes(v) ? st.times.filter(t => t !== v) : [...st.times, v];
  else if (k === 'unit') st.unit = v;
  else st[k] = st[k] === v ? '' : v;              // tap again to clear
  st.text = null;
  renderPad();
});

$('#padwrap').addEventListener('input', e => {
  const t = e.target.closest('.tline'); if (!t) return;
  const d = S.drugs[P], j = +t.dataset.j, st = d.steps[j];
  if (e.target.matches('[data-dur]')){
    st.dur = e.target.value.replace(/\D/g, '');
    st.text = null;
    $('[data-out]', t).value = composeStep(st, j, d.form);    // no re-render: keep the keyboard up
  } else if (e.target.matches('[data-out]')){
    st.text = e.target.value.trim() ? e.target.value : null;
  }
});
$('#padwrap').addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.matches('[data-dur]')) e.target.blur(); });

$('#addline').onclick = () => {
  const d = S.drugs[P]; if (d.steps.length >= MAX_STEPS) return;
  d.steps.push(newStep());
  renderPad();
  $('.pad .pb').scrollTop = 1e6;
};

/* ============================================================
   LETTERHEAD — drawn on every page (styles in sheet.css).
   Plain hyphen in the phone number: Montserrat has no U+2011.
   ============================================================ */
const LETTERHEAD = `<div class="lh">
  <div class="lh-bar"></div><div class="lh-wedge"></div>
  <div class="lh-name">DR TALHA NAFEES</div>
  <div class="lh-role">Consultant Ophthalmologist</div>
  <div class="lh-quals">MBBS · FCPS · MRCS (UK) · Vitreo-Retina Fellow</div>
  <div class="lh-rule top"></div><div class="lh-rule bot"></div>
  <div class="lh-contact">
    <div><span>0329-6496490</span><span>talhanafees@hotmail.com</span></div>
    <div><span>youtube.com/@talhanafees</span><span>instagram.com/tnlrbt</span></div>
  </div>
  <div class="lh-foot"></div>
</div>`;

/* ============================================================
   THE SHEET — built from state, empty fields simply left out.
   Top to bottom: patient · chief complaint · vision | pressure · clinical
   · investigations · procedure · Rx · refraction (bottom centre) · follow-up
   ============================================================ */
function sheetHTML(stamp){
  const f = (k, v, cls = '') => v ? `<div class="s-f ${cls}">${k ? `<span class="k">${k}</span>` : ''}<span class="v">${esc(v)}</span></div>` : '';
  const eyes = (r, l) => `<div class="s-eyes"><span>${r ? `<b>(R)</b>${esc(r)}` : ''}</span><span>${l ? `<b>(L)</b>${esc(l)}` : ''}</span></div>`;
  /* age is typed with the sex beside it ("58 F"); the number takes the M/Y unit
     and anything else he typed follows it — "58 F" + Y prints as "58 y F" */
  const age = val('p-age'), am = age.match(/^(\d+)\s*(.*)$/);
  const ageOut = am ? `${am[1]} ${S.ageunit}${am[2] ? ' ' + am[2] : ''}` : age;

  const pt = `<div class="s-pt">
      <div class="r">${f('NAME', val('p-name'), 'grow nm')}${f(S.rel, val('p-rel'), 'grow')}${f('AGE', ageOut)}</div>
      <div class="r">${f('ADDRESS', val('p-addr'), 'grow')}${f('MR NO.', val('p-mr'))}${f('DATE', stamp, 'date')}</div>
    </div>`;
  const chief = val('chief') ? `<div class="s-chief"><span class="k">CHIEF COMPLAINT</span><span class="v">${br(val('chief'))}</span></div>` : '';

  /* vision and pressure are two separate tables; the IOP one only exists if a reading was taken */
  const EYES = [['r', 'RIGHT'], ['l', 'LEFT']];
  const va = (val('va-r') || val('va-l')) ? `<div class="s-tbl s-va"><div class="s-cap">Vision</div><table class="s-rt">
      <tr><th></th><th>VA</th></tr>${EYES.map(([e, lab]) => `<tr><td>${lab}</td><td>${esc(val(`va-${e}`))}</td></tr>`).join('')}</table></div>` : '';
  const IOP = ['pre', 'pachy', 'cf', 'final'];
  const iv = (e, c) => c === 'cf' ? cfVal(`iop-${e}-cf`) : val(`iop-${e}-${c}`);
  const iop = IOP.some(c => iv('r', c) || iv('l', c)) ? `<div class="s-tbl s-iop"><div class="s-cap">Intraocular Pressure</div><table class="s-rt">
      <tr><th></th><th>Pre</th><th>Pachy</th><th>CF</th><th>Final</th></tr>${
      EYES.map(([e, lab]) => `<tr><td>${lab}</td>${IOP.map(c => `<td>${esc(iv(e, c))}</td>`).join('')}</tr>`).join('')}</table></div>` : '';
  const vp = (va || iop) ? `<div class="s-vp">${va}${iop}</div>` : '';

  const RF = ['sph', 'cyl', 'axis', 'va', 'add', 'near'];
  const rv = (e, c) => ['sph', 'cyl', 'add'].includes(c) ? signed(`ref-${e}-${c}`) : val(`ref-${e}-${c}`);
  /* refraction is printed last, centred at the bottom above the follow-up */
  const ref = RF.some(c => rv('r', c) || rv('l', c)) ? `<div class="s-tbl s-ref"><div class="s-cap">Refraction / Glasses</div><table class="s-rt">
      <tr><th></th><th>Sph</th><th>Cyl</th><th>Axis</th><th>VA</th><th>Add</th><th>Near Vision</th></tr>${
      EYES.map(([e, lab]) => `<tr><td>${lab}</td>${RF.map(c => `<td>${esc(rv(e, c))}</td>`).join('')}</tr>`).join('')}</table></div>` : '';

  /* clinical: history on the left, examination on the right */
  const c1 = [], c2 = [];
  const hist = [['SYSTEMIC', 'h-sys'], ['OCULAR', 'h-ocu']].filter(([, id]) => val(id));
  if (hist.length) c1.push('<div class="s-sec">History</div>' +
    hist.map(([k, id]) => `<div class="s-row full"><span class="k">${k}</span><span class="v">${br(val(id))}</span></div>`).join(''));
  const ex = EXAM.filter(([k]) => val(`ex-${k}-r`) || val(`ex-${k}-l`));
  const rapd = val('ex-rapd') ? `<div class="s-row"><span class="k">RAPD</span><span class="v">${esc(val('ex-rapd'))}</span></div>` : '';
  if (ex.length || rapd) c2.push('<div class="s-sec">Examination</div>' +
    ex.map(([k, lab]) => `<div class="s-row"><span class="k">${lab.toUpperCase()}</span>${eyes(val(`ex-${k}-r`), val(`ex-${k}-l`))}</div>`).join('') + rapd);
  const cols = [c1, c2].filter(c => c.length);
  const clin = cols.length ? `<div class="s-clin">${cols.map(c => `<div>${c.join('')}</div>`).join('')}</div>` : '';

  /* ocular and systemic investigations: two separate boxes */
  const inv = [['Ocular Investigations', 'a-inv-oc'], ['Systemic Investigations', 'a-inv-sys']].filter(([, id]) => val(id));
  const invs = inv.length ? `<div class="s-inv">${inv.map(([k, id]) =>
    `<div class="s-box"><div class="s-cap">${k}</div><div class="v">${br(val(id))}</div></div>`).join('')}</div>` : '';
  const proc = val('a-proc') ? `<div class="s-proc"><div class="s-sec">Procedure / Surgery</div><div class="v">${br(val('a-proc'))}</div></div>` : '';

  /* blank drug slots are skipped, and numbering closes up behind them */
  const drugs = S.drugs.filter(d => d.name.trim()).map((d, n) => {
    const lines = doseLines(d);
    return `<div class="s-drug"><div class="nm"><span class="no">${n + 1}.</span><span class="t">${esc(d.name.trim().toUpperCase())}</span></div>` +
      `<div class="s-dose">${lines.map(l => `<div>${esc(l)}</div>`).join('')}</div></div>`;
  }).join('');
  /* the hidden "continued" marks are revealed by the auto-fit when a block is split across pages */
  const rx = drugs ? `<div class="s-rx"><div class="s-rx-h"><span>R<i>x</i></span><small hidden>continued</small></div><div class="rx-list">${drugs}</div></div>` : '';

  /* Hidayat — the doctor's Urdu instructions, printed under the Rx.
     One line in, one line out; the heading carries no letter-spacing,
     which would break Nastaliq's joins when html2canvas rasterises it. */
  const hidLines = val('hid').split('\n').map(l => l.trim()).filter(Boolean);
  const hid = hidLines.length ? `<div class="s-hid"><div class="h"><b>ہدایات</b><small hidden>continued</small></div>
      <div class="v" dir="rtl" lang="ur">${hidLines.map(l => l.endsWith(':')
        ? `<div class="sub">${esc(l)}</div>`                 /* a line ending in : is a sub-heading */
        : `<div class="li">${esc(l)}</div>`).join('')}</div></div>` : '';

  const fu = `<div class="s-fu">${f('FOLLOW-UP', isoToDMY(val('fu')))}<span class="note">Please bring this prescription on your next visit.</span></div>`;

  return `
    <div class="sheet pg1">${LETTERHEAD}<div class="sheet-body">
      ${pt}${chief}${vp}${clin}${invs}${proc}${rx}${hid}
      <div class="s-gap"></div>${ref}<div class="s-cont" hidden></div>${fu}
    </div></div>
    <div class="sheet pgc" hidden>${LETTERHEAD}<div class="sheet-body">
      <div class="s-p2h">${f('NAME', val('p-name'))}${f('MR NO.', val('p-mr'))}${f('DATE', stamp)}<span class="pg"></span></div>
      <div class="p2c"></div>
      <div class="s-gap"></div><div class="s-cont" hidden></div>
    </div></div>`;
}

/* ============================================================
   AUTO-FIT — silent. Compress, then spill onto as many pages as it takes.
   Every page is measured: a page that is never measured is a page that
   quietly drops a drug off the bottom, and the patient never sees it.
   ============================================================ */
const MAX_PAGES = 4;
const TIERS = ['', 't1', 't2', 't3'];

/* The bottom strip is pinned with margin-top:auto and nothing is allowed to
   shrink, so if the content is too tall the strip is pushed past the body box.
   How far past is the overflow. */
function overflow(pg){
  const body = $('.sheet-body', pg);
  const last = [...body.children].filter(e => !e.hidden).at(-1);
  return last ? last.getBoundingClientRect().bottom - body.getBoundingClientRect().bottom : 0;
}

/* page 1 stacks its blocks directly; later pages hold them in .p2c */
const content = pg => $('.p2c', pg) || $('.sheet-body', pg);
const blocksOf = pg => [...content(pg).children]
  .filter(e => !e.hidden && !e.matches('.s-gap, .s-cont, .s-fu, .s-pt, .s-p2h'));

/* A long Rx or a long set of Hidayat is split entry by entry rather than
   moved whole, so page 1 fills up before page 2 starts. The tail lands in a
   copy of the block — same heading, marked "continued". */
function moveTail(block, dst, sel){
  const list = $(sel, block);
  let cont = dst.firstElementChild;
  if (!cont || !cont.matches('.cont') || cont.className.split(' ')[0] !== block.className.split(' ')[0]){
    cont = block.cloneNode(true);
    cont.classList.add('cont');
    cont.hidden = false;
    $(sel, cont).replaceChildren();
    dst.prepend(cont);
  }
  $(sel, cont).prepend(list.lastElementChild);
  if (!list.children.length) block.hidden = true;
  return true;
}

/* Move the bottom-most thing off `from` onto `to`. Everything is prepended,
   because blocks leave the page from the bottom up. */
function moveLast(from, to){
  const last = blocksOf(from).at(-1);
  if (!last) return false;
  const dst = content(to);
  if (last.matches('.s-rx') && $$('.rx-list > *', last).length > 1) return moveTail(last, dst, '.rx-list');
  if (last.matches('.s-hid') && $$('.v > *', last).length > 1) return moveTail(last, dst, '.v');
  dst.prepend(last);
  return true;
}

/* Lay the sheet out at one compression level. Returns how many pages it took
   and whether everything actually landed on a page. */
function attempt(html, tier){
  const live = $('#live');
  live.innerHTML = html;
  const tpl = $('.pgc', live), p1 = $('.pg1', live), pages = [p1];
  const setTier = p => { p.classList.remove('t1', 't2', 't3'); if (tier) p.classList.add(tier); };
  setTier(p1);

  let ok = true;
  /* opens the next page, which always carries the follow-up strip */
  const nextPage = i => {
    if (pages[i + 1]) return pages[i + 1];
    if (pages.length >= MAX_PAGES) return null;
    const p = tpl.cloneNode(true);
    p.hidden = false; p.classList.remove('pgc');
    setTier(p);
    tpl.before(p); pages.push(p);
    $('.s-cont', pages[i]).hidden = false;
    $('.sheet-body', p).appendChild($('.s-fu', live));
    return p;
  };

  /* Once a second page is unavoidable, the whole Hidayat goes there first:
     the prescription itself — clinical findings and the Rx — stays together
     on page 1, and the patient's instructions read as their own sheet. */
  if (overflow(p1) > 1){
    const hid = $('.s-hid', p1), p2 = hid && !hid.hidden ? nextPage(0) : null;
    if (p2) content(p2).prepend(hid);
  }

  for (let i = 0; i < pages.length; i++){
    for (let guard = 0; overflow(pages[i]) > 1 && guard < 80; guard++){
      const to = nextPage(i);
      if (!to || !moveLast(pages[i], to)){ ok = false; break; }
    }
    if (!ok) break;
  }

  pages.forEach((p, i) => {
    const cont = $('.s-cont', p), pg = $('.s-p2h .pg', p);
    if (cont) cont.textContent = `Page ${i + 1} of ${pages.length} — continued on the next page`;
    if (pg) pg.textContent = `PAGE ${i + 1} OF ${pages.length}`;
  });
  /* a continued Rx / Hidayat says so only when part of it is on an earlier page */
  for (const cls of ['s-rx', 's-hid']){
    let seen = false;
    for (const p of pages)
      for (const b of $$('.' + cls, p)){
        if (b.hidden) continue;
        const s = $('small', b); if (s) s.hidden = !seen;
        seen = true;
      }
  }
  return { pages: pages.length, ok: ok && pages.every(p => overflow(p) <= 1) };
}

/* Fewest pages wins; among the levels that achieve it, the roomiest wins —
   so a sheet is only squeezed when squeezing actually saves the patient a page. */
function fit(html){
  const tightest = attempt(html, 't3');
  if (!tightest.ok) return tightest;                    // nothing fits it: caller must block the send
  for (const t of TIERS){
    const r = attempt(html, t);
    if (r.ok && r.pages === tightest.pages) return r;
  }
  return attempt(html, 't3');
}

async function fontsReady(){
  if (!document.fonts) return;
  await Promise.all([
    document.fonts.load('400 16px Nastaliq', 'بپ'),
    document.fonts.load('400 16px Montserrat'), document.fonts.load('600 16px Montserrat'), document.fonts.load('700 16px Montserrat'),
  ]).catch(() => {});
  await document.fonts.ready;
}

/* ============================================================
   PREVIEW + PDF
   ============================================================ */
let PAGES = 1, PDF = null, GEN = 0;

async function openPreview(){
  if (!val('p-name')){
    toast('Add the patient’s name first');
    const n = $('#p-name'); n.closest('details').open = true; n.focus();
    return;
  }
  const orphan = S.drugs.findIndex(d => !d.name.trim() && doseLines(d).length);
  if (orphan >= 0) toast(`Drug ${orphan + 1} has a dosage but no name — left off`, 3600);

  const now = new Date();
  const html = sheetHTML(`${fmtDate(now)}  ${fmtTime(now)}`);
  $('#live').innerHTML = html;
  await fontsReady();
  const laid = fit(html);
  PAGES = laid.pages;

  $('#stage').innerHTML = $$('#live .sheet').filter(p => !p.hidden).map(p => p.outerHTML).join('');
  $('#pv').classList.add('on'); pushLayer('pv');
  scaleStage();

  const tok = ++GEN, btn = $('#pv-send');
  PDF = null; btn.disabled = true;
  /* A sheet that still overflows is cut off at the bottom — a drug or an
     instruction the patient would never see. Show it, say so, refuse to send. */
  $('#pv-warn').hidden = laid.ok;
  if (!laid.ok){ btn.textContent = 'Too long'; return; }

  /* build the PDF now, so tapping Send can hand it to Android instantly —
     the share sheet refuses to open if the tap is followed by a slow render */
  btn.textContent = 'Preparing…';
  try {
    const blob = await buildPdf();
    if (tok !== GEN) return;
    PDF = blob; btn.disabled = false; btn.textContent = 'Send';
  } catch (err){
    if (tok !== GEN) return;
    btn.textContent = 'Failed'; toast('Could not build the PDF: ' + err.message, 5000);
  }
}
function hidePreview(){ $('#pv').classList.remove('on'); GEN++; }

function scaleStage(){
  const n = $$('#stage .sheet').length; if (!n) return;
  const W = 793.7, H = 1122.5, GAP = 12;
  const k = Math.min(1, (window.innerWidth - 16) / W);
  const st = $('#stage'), sz = $('#sizer');
  st.style.cssText = `width:${W}px;transform:scale(${k});transform-origin:top left`;
  sz.style.cssText = `width:${W * k}px;height:${(n * H + (n - 1) * GAP) * k}px;margin:0 auto;overflow:hidden`;
}
window.addEventListener('resize', scaleStage);

/* html2canvas lays the page out again inside a cloned copy, and that copy
   re-requests every stylesheet, font and image. Offline those requests fail
   and the PDF comes out unstyled with no letterhead. So the clone gets no
   <link> tags at all — just the sheet CSS inline, with every url() already
   turned into a data: URL read through the offline cache. */
let SHEET_CSS = null;
async function inlineSheetCss(){
  if (SHEET_CSS) return SHEET_CSS;
  const toData = async url => {
    const blob = await (await fetch(url)).blob();
    return new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(blob); });
  };
  let css = await (await fetch('sheet.css')).text();
  for (const u of new Set([...css.matchAll(/url\('([^']+)'\)/g)].map(m => m[1])))
    css = css.split(`url('${u}')`).join(`url('${await toData(u)}')`);
  return (SHEET_CSS = css);
}

/* rasterised on purpose: text-based PDF generation mangles Nastaliq shaping */
async function buildPdf(){
  const css = await inlineSheetCss();
  const pdf = new window.jspdf.jsPDF({ unit: 'mm', format: 'a4', compress: true });
  const pages = $$('#live .sheet').filter(p => !p.hidden);
  for (let i = 0; i < pages.length; i++){
    const c = await html2canvas(pages[i], {
      scale: 2.5, backgroundColor: '#ffffff', logging: false,
      ignoreElements: el => el.tagName === 'LINK',
      onclone: async doc => {
        const st = doc.createElement('style');
        st.textContent = css + '#live{position:absolute;left:0;top:0}';
        doc.head.appendChild(st);
        await Promise.all(['400 16px Nastaliq', '400 16px Montserrat', '600 16px Montserrat', '700 16px Montserrat']
          .map(f => doc.fonts.load(f, 'Aبپ'))).catch(() => {});
      },
    });
    if (i) pdf.addPage();
    pdf.addImage(c.toDataURL('image/jpeg', 0.9), 'JPEG', 0, 0, 210, 297);
  }
  return pdf.output('blob');
}

function fileName(){
  const clean = val('p-name').replace(/[\\/:*?"<>|]+/g, '').trim() || 'Patient';
  return `Prescription - ${clean} - ${fmtDate(new Date()).replace(/\//g, '-')}.pdf`;
}

async function share(){
  const file = new File([PDF], fileName(), { type: 'application/pdf' });
  if (navigator.canShare && navigator.canShare({ files: [file] })){
    try { await navigator.share({ files: [file] }); toast('Sent'); }
    catch (err){ if (err.name !== 'AbortError') toast('Could not share: ' + err.message, 4000); }
    return;
  }
  /* desktop / unsupported browsers: hand over the file instead */
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(file), download: file.name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  toast('Sharing isn’t available here — PDF downloaded instead', 4000);
}

$('#preview').onclick = openPreview;
$('#pv-back').onclick = () => history.back();
$('#pv-send').onclick = () => {
  if (!PDF) return;
  if (PAGES > 1){                                    // silent fit, but more than one sheet is his call
    $('#ask-n').textContent = `${PAGES} pages`;
    $('#ask').classList.add('on');
  } else share();
};
$('#ask-no').onclick = () => $('#ask').classList.remove('on');
$('#ask-go').onclick = () => { $('#ask').classList.remove('on'); share(); };

/* ============================================================
   ANDROID BACK — closes the top layer instead of leaving the app
   ============================================================ */
const layers = [];
function pushLayer(name){ layers.push(name); history.pushState({ layer: name }, ''); }
window.addEventListener('popstate', () => {
  $('#ask').classList.remove('on');
  const l = layers.pop();
  if (l === 'pad') hidePad();
  else if (l === 'pv') hidePreview();
});

/* nothing is saved, so warn before a reload or close throws the form away */
let leaving = false;
const dirty = () => $$('main input, main textarea').some(el => el.value.trim()) || S.drugs.some(d => d.name.trim() || doseLines(d).length);
window.addEventListener('beforeunload', e => { if (!leaving && dirty()){ e.preventDefault(); e.returnValue = ''; } });
$('#new').onclick = () => {
  if (dirty() && !confirm('Clear this prescription and start a new one?')) return;
  leaving = true; location.reload();
};

/* ============================================================
   OFFLINE
   ============================================================ */
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost'))
  navigator.serviceWorker.register('sw.js').catch(() => {});

renderDrugs();
inlineSheetCss().catch(() => {});        // warm it up so the first preview isn't slower
window.RxApp = { S, newDrug, newStep, renderDrugs, openPreview, pages: () => PAGES, pdf: () => PDF };   // test hook
