/* DFIR Co-pilot viewer — shared utilities (B-3) */

const AGENT_COLORS = {
  'DFIR-Liaison': { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/40', dot: 'bg-blue-400' },
  'DFIR-Classifier': { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/40', dot: 'bg-purple-400' },
  'DFIR-HostForensics': { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/40', dot: 'bg-emerald-400' },
  'DFIR-NetworkForensics': { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/40', dot: 'bg-amber-400' },
  'DFIR-Captain': { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/40', dot: 'bg-red-400' },
};

const EVENT_ICONS = {
  CASE_OPENED: '📂', COLLECTION_PLAN_ISSUED: '📋', EVIDENCE_RECEIVED: '📥',
  EVIDENCE_CLASSIFIED: '🏷️', SPECIALIST_FINDING: '🔍', SPECIALIST_CHALLENGE: '⚡',
  CAPTAIN_REDIRECT: '🎯', CAPTAIN_VERDICT: '⚖️', REPORT_DRAFTED: '📝', CASE_SEALED: '🔒',
};

const CASE_META = {
  '001': { name: 'Acme Ransomware', org: 'Acme Accounting', location: 'Calgary, AB', difficulty: 'low', tagline: 'LockBit-style ransomware — clean happy path', hero: false },
  '002': { name: 'Vector Insider Threat', org: 'Vector Aerospace', location: 'Mississauga, ON', difficulty: 'medium', tagline: 'Host vs Network debate — the hero demo', hero: true },
  '003': { name: 'TrueLedger Supply Chain', org: 'TrueLedger SaaS', location: 'Vancouver, BC', difficulty: 'high', tagline: 'Captain re-scopes mid-investigation', hero: false },
};

function difficultyBadge(level) {
  const map = {
    low: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    medium: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    high: 'bg-red-500/20 text-red-300 border-red-500/30',
  };
  return map[level] || map.medium;
}

function agentStyle(id) {
  return AGENT_COLORS[id] || { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/40', dot: 'bg-slate-400' };
}

async function loadCaseFile(caseNum) {
  const res = await fetch(`../data/case_${caseNum}_output.json`);
  if (!res.ok) throw new Error(`Failed to load case ${caseNum}`);
  return res.json();
}

async function loadAuditChain(caseNum) {
  const res = await fetch(`../data/case_${caseNum}_audit.jsonl`);
  if (!res.ok) throw new Error(`Failed to load audit chain ${caseNum}`);
  const text = await res.text();
  return text.trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
}

function simpleMarkdown(md) {
  return md
    .replace(/^# (.+)$/gm, '<h2 class="text-xl font-semibold text-white mt-6 mb-3">$1</h2>')
    .replace(/^## (.+)$/gm, '<h3 class="text-lg font-medium text-slate-200 mt-4 mb-2">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white">$1</strong>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-slate-300">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal text-slate-300">$2</li>')
    .replace(/\n\n/g, '</p><p class="text-slate-300 mb-3">')
    .replace(/^([^<\n].*)$/gm, (m) => m.startsWith('<') ? m : `<p class="text-slate-300 mb-3">${m}</p>`);
}

function formatTimestamp(iso) {
  const d = new Date(iso);
  return d.toLocaleString('en-CA', { dateStyle: 'medium', timeStyle: 'short' });
}

function copyToClipboard(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = orig; }, 1500);
  });
}

function sortKeysDeep(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(sortKeysDeep);
  return Object.keys(obj).sort().reduce((acc, k) => { acc[k] = sortKeysDeep(obj[k]); return acc; }, {});
}

async function verifyAuditChain(events) {
  const ZERO = '0'.repeat(64);
  const enc = new TextEncoder();
  for (const ev of events) {
    const fields = { seq: ev.seq, timestamp: ev.timestamp, event_type: ev.event_type, agent_id: ev.agent_id, payload: ev.payload, prev_hash: ev.prev_hash };
    const sorted = sortKeysDeep(fields);
    const buf = await crypto.subtle.digest('SHA-256', enc.encode(JSON.stringify(sorted)));
    const computed = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
    if (computed !== ev.hash) return { ok: false, brokenAt: ev.seq };
    const expectedPrev = ev.seq === 0 ? ZERO : events[ev.seq - 1].hash;
    if (ev.prev_hash !== expectedPrev) return { ok: false, brokenAt: ev.seq };
  }
  return { ok: true, brokenAt: null };
}

function renderAuditChain(container, events, verifyResult) {
  const badge = verifyResult.ok
    ? '<span class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-sm font-medium">Chain Verified ✓</span>'
    : `<span class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 text-sm font-medium">Chain Broken at seq ${verifyResult.brokenAt} ✗</span>`;

  container.innerHTML = `<div class="mb-6">${badge}</div><div class="relative space-y-0">` +
    events.map((ev, i) => {
      const st = agentStyle(ev.agent_id);
      const icon = EVENT_ICONS[ev.event_type] || '•';
      const payloadSummary = JSON.stringify(ev.payload).slice(0, 80) + (JSON.stringify(ev.payload).length > 80 ? '…' : '');
      return `
        <div class="relative flex gap-4 pb-8 ${i < events.length - 1 ? '' : 'pb-0'}">
          ${i < events.length - 1 ? '<div class="absolute left-[1.125rem] top-10 bottom-0 w-px bg-gradient-to-b from-slate-600 to-slate-700"></div>' : ''}
          <div class="flex-shrink-0 w-9 h-9 rounded-full ${st.bg} ${st.border} border flex items-center justify-center text-sm z-10">${icon}</div>
          <div class="flex-1 min-w-0">
            <div class="rounded-lg border border-slate-700/80 bg-slate-800/50 p-4">
              <div class="flex flex-wrap items-center gap-2 mb-2">
                <span class="text-xs font-mono text-slate-500">seq ${ev.seq}</span>
                <span class="text-xs px-2 py-0.5 rounded ${st.bg} ${st.text} ${st.border} border">${ev.agent_id.replace('DFIR-', '')}</span>
                <span class="text-xs text-slate-400">${ev.event_type.replace(/_/g, ' ')}</span>
              </div>
              <p class="text-xs text-slate-500 mb-2" title="${ev.timestamp}">${formatTimestamp(ev.timestamp)}</p>
              <p class="text-sm text-slate-300 mb-3 font-mono truncate">${payloadSummary}</p>
              <div class="flex items-center gap-2">
                <code class="text-xs font-mono text-slate-400 break-all flex-1">${ev.hash}</code>
                <button type="button" class="copy-hash text-xs px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 shrink-0" data-hash="${ev.hash}">Copy</button>
              </div>
            </div>
          </div>
        </div>`;
    }).join('') + '</div>';

  container.querySelectorAll('.copy-hash').forEach(btn => {
    btn.addEventListener('click', () => copyToClipboard(btn.dataset.hash, btn));
  });
}

const TAB_ON = 'text-white border-slate-700 bg-slate-800/80 border border-b-0';
const TAB_OFF = 'text-slate-400 border-transparent';

function initTabs() {
  const tabs = document.querySelectorAll('[data-tab]');
  const panels = document.querySelectorAll('[data-panel]');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const id = tab.dataset.tab;
      tabs.forEach(t => {
        t.className = 'px-4 py-2 text-sm rounded-t-lg ' + (t.dataset.tab === id ? TAB_ON : TAB_OFF);
      });
      panels.forEach(p => p.classList.toggle('hidden', p.dataset.panel !== id));
    });
  });
}

if (typeof window !== 'undefined') {
  window.DFIR = { AGENT_COLORS, CASE_META, loadCaseFile, loadAuditChain, simpleMarkdown, verifyAuditChain, renderAuditChain, initTabs, difficultyBadge, agentStyle, formatTimestamp };
}
