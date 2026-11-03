/* ============================================================
   PATIENT RECORDS — kept in this browser's own storage (IndexedDB),
   on the PC the app is used on. Nothing is ever sent anywhere.

   Every storage call lives in this file, so if the records ever move
   (to a server on the clinic PC, say) this is the only file to change.

   The database name is specific to this app: every site published under
   zaeem-a.github.io shares one browser origin, and so one IndexedDB.
   ============================================================ */
'use strict';

const Records = (() => {
  const DB = 'rx-kashif', VERSION = 1;
  const PATIENT_FIELDS = ['mr', 'name', 'rel_kind', 'rel_name', 'age', 'age_unit', 'phone', 'cnic', 'address',
                          'created_at', 'updated_at', 'last_visit', 'last_visit_no'];

  const pad6   = n => String(n).padStart(6, '0');
  const digits = s => String(s ?? '').replace(/\D/g, '');
  /* 0300-1234567, 03001234567 and +92 300 1234567 are one number: compare the
     national part, without the leading 0 or the 92 country code */
  const phoneKey = s => {
    let d = digits(s);
    if (d.startsWith('92') && d.length > 10) d = d.slice(2);
    else if (d.startsWith('0')) d = d.slice(1);
    return d;
  };
  const pick = (o, keys) => Object.fromEntries(keys.filter(k => o[k] !== undefined).map(k => [k, o[k]]));

  /* IndexedDB requests and transactions as promises. Awaiting one request
     inside a transaction keeps it alive; awaiting anything else would not. */
  const req  = r  => new Promise((ok, no) => { r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error); });
  const done = tx => new Promise((ok, no) => { tx.oncomplete = () => ok(); tx.onerror = tx.onabort = () => no(tx.error || new Error('aborted')); });

  let dbp = null;
  function open(){
    if (dbp) return dbp;
    dbp = new Promise((ok, no) => {
      if (!self.indexedDB) return no(new Error('this browser has no IndexedDB'));
      const r = indexedDB.open(DB, VERSION);
      r.onupgradeneeded = () => {
        const db = r.result;
        db.createObjectStore('patients', { keyPath: 'mr' });
        const v = db.createObjectStore('visits', { keyPath: 'id', autoIncrement: true });
        v.createIndex('mr', 'mr');
        v.createIndex('session', 'session', { unique: true });   // one visit per prescription
        db.createObjectStore('meta', { keyPath: 'key' });
      };
      r.onsuccess = () => ok(r.result);
      r.onerror   = () => no(r.error);
      r.onblocked = () => no(new Error('the records are open in an older tab — close it'));
    });
    dbp.catch(() => { dbp = null; });
    return dbp;
  }

  async function available(){
    try { await open(); return true; } catch { return false; }
  }

  /* MR, name or phone; partial, any case. A clinic's patient list fits in
     memory, so this filters the whole store — visits are not read at all,
     because each patient carries its own last visit and visit count. */
  async function search(q){
    q = String(q ?? '').trim();
    if (!q) return [];
    const db = await open();
    const all = await req(db.transaction('patients').objectStore('patients').getAll());
    const lc = q.toLowerCase(), raw = digits(q), ph = phoneKey(q);
    return all
      .filter(p => (p.name || '').toLowerCase().includes(lc)
                || (raw && p.mr.includes(raw))
                || (ph.length >= 3 && phoneKey(p.phone).includes(ph)))
      .sort((a, b) => (b.last_visit || '').localeCompare(a.last_visit || '') || (a.name || '').localeCompare(b.name || ''))
      .slice(0, 20);
  }

  async function get(mr){
    if (!mr) return null;
    const db = await open();
    return (await req(db.transaction('patients').objectStore('patients').get(mr))) || null;
  }

  /* the visit this form already saved, if it was sent before */
  async function sessionVisit(session){
    const db = await open();
    return (await req(db.transaction('visits').objectStore('visits').index('session').get(session))) || null;
  }

  /* next free number, skipping any MR the doctor typed in by hand */
  async function reserveMr(){
    const db = await open();
    const tx = db.transaction(['meta', 'patients'], 'readwrite');
    const meta = tx.objectStore('meta'), pats = tx.objectStore('patients');
    let n = (await req(meta.get('mr')))?.value || 1;
    while (await req(pats.getKey(pad6(n))) !== undefined) n++;
    meta.put({ key: 'mr', value: n + 1 });
    await done(tx);
    return pad6(n);
  }

  /* Called once the prescription has actually gone out. Re-sending the same
     prescription updates its visit instead of adding a second one. */
  async function saveVisit({ session, patient, snapshot, visitNo }){
    const db = await open();
    const tx = db.transaction(['patients', 'visits'], 'readwrite');
    const pats = tx.objectStore('patients'), vis = tx.objectStore('visits');
    const now = new Date().toISOString();

    const old   = await req(pats.get(patient.mr));
    const prior = await req(vis.index('session').get(session));
    const no = prior ? prior.visit_no : (visitNo || (old?.last_visit_no || 0) + 1);

    vis.put({ ...(prior || {}), mr: patient.mr, visit_no: no, session, sent_at: now, snapshot });
    pats.put({
      ...pick(old || {}, PATIENT_FIELDS),
      ...pick(patient, PATIENT_FIELDS),
      created_at: old?.created_at || now,
      updated_at: now,
      last_visit: now,
      last_visit_no: Math.max(old?.last_visit_no || 0, no),
    });
    await done(tx);
    return no;
  }

  async function stats(){
    const db = await open();
    const tx = db.transaction(['patients', 'visits', 'meta']);
    const [patients, visits, backup] = await Promise.all([
      req(tx.objectStore('patients').count()),
      req(tx.objectStore('visits').count()),
      req(tx.objectStore('meta').get('backup')),
    ]);
    return { patients, visits, lastBackup: backup?.value || null };
  }

  /* ---------- backup ---------- */
  async function exportAll(){
    const db = await open();
    const tx = db.transaction(['patients', 'visits', 'meta']);
    const [patients, visits, meta] = await Promise.all(
      ['patients', 'visits', 'meta'].map(s => req(tx.objectStore(s).getAll())));
    const at = new Date().toISOString();
    const t2 = db.transaction('meta', 'readwrite');
    t2.objectStore('meta').put({ key: 'backup', value: at });
    await done(t2);
    return new Blob([JSON.stringify({ app: DB, version: VERSION, exported_at: at, patients, visits, meta })],
                    { type: 'application/json' });
  }

  /* Merges, never replaces: restoring an older backup cannot delete anything
     saved since. Patients match by MR (the newer copy wins), visits by the
     prescription they came from. */
  async function importAll(text){
    let data;
    try { data = JSON.parse(text); } catch { throw new Error('the file is not a records backup'); }
    if (data?.app !== DB || !Array.isArray(data.patients) || !Array.isArray(data.visits))
      throw new Error('the file is not a records backup from this app');

    const db = await open();
    const tx = db.transaction(['patients', 'visits', 'meta'], 'readwrite');
    const pats = tx.objectStore('patients'), vis = tx.objectStore('visits'), meta = tx.objectStore('meta');
    const touched = new Set();
    let newPatients = 0, newVisits = 0;

    for (const p of data.patients){
      if (!p || typeof p.mr !== 'string' || !p.mr) continue;
      const cur = await req(pats.get(p.mr));
      if (!cur) newPatients++;
      if (!cur || (p.updated_at || '') > (cur.updated_at || '')) pats.put({ ...pick(cur || {}, PATIENT_FIELDS), ...pick(p, PATIENT_FIELDS) });
      touched.add(p.mr);
    }
    for (const v of data.visits){
      if (!v || typeof v.session !== 'string' || typeof v.mr !== 'string') continue;
      if (await req(vis.index('session').get(v.session))) continue;
      const { id, ...rest } = v;
      vis.add(rest);
      newVisits++;
      touched.add(v.mr);
    }
    /* keep each patient's visit count and last visit in step with what's now stored */
    for (const mr of touched){
      const p = await req(pats.get(mr));
      if (!p) continue;
      const vs = await req(vis.index('mr').getAll(mr));
      p.last_visit_no = Math.max(0, ...vs.map(v => v.visit_no || 0));
      p.last_visit = vs.map(v => v.sent_at || '').sort().at(-1) || p.last_visit;
      pats.put(p);
    }
    const here  = (await req(meta.get('mr')))?.value || 1;
    const there = data.meta?.find?.(m => m?.key === 'mr')?.value || 1;
    meta.put({ key: 'mr', value: Math.max(here, there) });
    await done(tx);
    return { patients: newPatients, visits: newVisits };
  }

  /* ask the browser not to clear the records when the disk runs low */
  const persist = () => navigator.storage?.persist ? navigator.storage.persist().catch(() => false) : Promise.resolve(false);

  return { available, search, get, sessionVisit, reserveMr, saveVisit, stats, exportAll, importAll, persist, phoneKey };
})();
