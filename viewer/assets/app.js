/* DFIR Co-pilot viewer — shared utilities (B-3 + B-4 polish) */

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

const DEBATE_EVENTS = new Set(['SPECIALIST_CHALLENGE', 'CAPTAIN_REDIRECT']);

function isDebateEvent(eventType) {
  return DEBATE_EVENTS.has(eventType);
}

function mitreTechniqueUrl(id) {
  const base = id.split('.')[0];
  return `https://attack.mitre.org/techniques/${base}/`;
}

function chainBadgeHtml(verifyResult, { compact = false } = {}) {
  if (verifyResult.ok) {
    return compact
      ? `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-xs font-medium"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Verified</span>`
      : `<span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-sm font-medium">Chain Verified ✓</span>`;
  }
  let label;
  if (verifyResult.brokenAt != null) {
    label = compact ? `Broken seq ${verifyResult.brokenAt}` : `Chain Broken at seq ${verifyResult.brokenAt} ✗`;
  } else {
    label = compact ? 'Not verified' : (verifyResult.reason || 'Chain verification unavailable');
  }
  return `<span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 text-sm font-medium">${label}</span>`;
}

function renderVerdictStrip(container, verdict, verifyResult, eventCount, debateCount) {
  const debateNote = debateCount > 0
    ? `<span class="debate-pill text-xs px-2 py-0.5 rounded-full font-medium">${debateCount} debate event${debateCount === 1 ? '' : 's'}</span>`
    : '';
  container.innerHTML = `
    <div class="verdict-strip rounded-xl p-4 md:p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        <p class="text-xs uppercase tracking-wide text-slate-500 mb-1">Captain verdict</p>
        <p class="text-xl font-semibold text-white">${verdict.classification}</p>
        <p class="text-sm text-slate-400 mt-0.5">${verdict.subtype || ''}</p>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        ${debateNote}
        <span class="text-xs text-slate-500">${eventCount} audit events</span>
        ${chainBadgeHtml(verifyResult)}
        <button type="button" data-jump-tab="audit" class="no-print text-xs px-3 py-1.5 rounded border border-slate-600 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors">View chain →</button>
      </div>
    </div>`;
  container.classList.remove('hidden');
  container.querySelector('[data-jump-tab]')?.addEventListener('click', () => activateTab('audit'));
}

const CASE_META = {
  '001': { name: 'Meridian Logistics Ransomware', org: 'Meridian Logistics Inc.', location: 'Columbus, Ohio, USA', difficulty: 'low', tagline: 'LockB1D ransomware with confirmed pre-encryption exfiltration', hero: true },
  '002': { name: 'BioGenix Insider Threat', org: 'BioGenix Therapeutics, Inc.', location: 'Cambridge, Massachusetts, USA', difficulty: 'medium', tagline: 'Host says no exfil on endpoint; Network sees 13.4 GB cloud upload', hero: false },
  '003': { name: 'Confluxe Supply Chain', org: 'Confluxe Systems, Inc.', location: 'Denver, Colorado, USA', difficulty: 'high', tagline: 'Captain re-scopes from web app to npm supply chain', hero: false },
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

function viewerDataUrl(filename) {
  return new URL(`../data/${filename}`, window.location.href).href;
}

async function loadCaseFile(caseNum) {
  const url = viewerDataUrl(`case_${caseNum}_output.json`);
  if (window.location.protocol === 'file:') {
    throw new Error('Open via a local web server (not file://). From viewer/: python3 -m http.server 8080');
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`case_${caseNum}_output.json not found (HTTP ${res.status}). URL: ${url}`);
  return res.json();
}

async function loadAuditChain(caseNum) {
  const url = viewerDataUrl(`case_${caseNum}_audit.jsonl`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`case_${caseNum}_audit.jsonl not found (HTTP ${res.status}). URL: ${url}`);
  const text = await res.text();
  return text.trim().split('\n').filter(Boolean).map((line, i) => {
    try {
      return JSON.parse(line);
    } catch {
      throw new Error(`Invalid JSON on line ${i + 1} of case_${caseNum}_audit.jsonl`);
    }
  });
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

function formatRelativeTime(iso) {
  const d = new Date(iso);
  const sec = Math.round((d - Date.now()) / 1000);
  const abs = Math.abs(sec);
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  if (abs < 60) return rtf.format(sec, 'second');
  if (abs < 3600) return rtf.format(Math.round(sec / 60), 'minute');
  if (abs < 86400) return rtf.format(Math.round(sec / 3600), 'hour');
  return rtf.format(Math.round(sec / 86400), 'day');
}

function payloadSummary(payload) {
  if (!payload || !Object.keys(payload).length) return '(empty payload)';
  const parts = Object.entries(payload).map(([k, v]) => {
    const val = typeof v === 'object' ? JSON.stringify(v) : String(v);
    return `${k}: ${val.length > 40 ? val.slice(0, 40) + '…' : val}`;
  });
  return parts.join(' · ');
}

function shortHash(hash, n = 8) {
  if (!hash || hash.length < n * 2) return hash || '';
  return `${hash.slice(0, n)}…${hash.slice(-n)}`;
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

/** Match Python json.dumps(obj, sort_keys=True) for audit_trail.py hash compatibility. */
/** Match Python json.dumps(..., sort_keys=True, ensure_ascii=True) for hash parity. */
function pythonJsonString(s) {
  let out = '"';
  for (const ch of s) {
    const cp = ch.codePointAt(0);
    if (cp === 0x22) out += '\\"';
    else if (cp === 0x5c) out += '\\\\';
    else if (cp === 0x08) out += '\\b';
    else if (cp === 0x0c) out += '\\f';
    else if (cp === 0x0a) out += '\\n';
    else if (cp === 0x0d) out += '\\r';
    else if (cp === 0x09) out += '\\t';
    else if (cp < 0x20) out += '\\u' + cp.toString(16).padStart(4, '0');
    else if (cp > 0x7f) {
      if (cp > 0xffff) {
        const adj = cp - 0x10000;
        const hi = 0xd800 + (adj >> 10);
        const lo = 0xdc00 + (adj & 0x3ff);
        out += '\\u' + hi.toString(16).padStart(4, '0') + '\\u' + lo.toString(16).padStart(4, '0');
      } else out += '\\u' + cp.toString(16).padStart(4, '0');
    } else out += ch;
  }
  return out + '"';
}

function pythonCanonicalJson(value) {
  if (value === null) return 'null';
  const t = typeof value;
  if (t === 'boolean') return value ? 'true' : 'false';
  if (t === 'number') return Number.isFinite(value) ? String(value) : 'null';
  if (t === 'string') return pythonJsonString(value);
  if (Array.isArray(value)) {
    return '[' + value.map(pythonCanonicalJson).join(', ') + ']';
  }
  if (t === 'object') {
    const keys = Object.keys(value).sort();
    return '{' + keys.map((k) => pythonJsonString(k) + ': ' + pythonCanonicalJson(value[k])).join(', ') + '}';
  }
  return 'null';
}

async function digestSha256Hex(text) {
  if (!globalThis.crypto?.subtle) {
    throw new Error('Web Crypto unavailable — open http://localhost:8080 (not file:// or a LAN IP)');
  }
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
}

async function verifyAuditChain(events) {
  const ZERO = '0'.repeat(64);
  for (let i = 0; i < events.length; i++) {
    const ev = events[i];
    if (ev.seq !== i) {
      return { ok: false, brokenAt: ev.seq, reason: 'sequence gap', head: events.at(-1)?.hash ?? null };
    }
    const fields = { seq: ev.seq, timestamp: ev.timestamp, event_type: ev.event_type, agent_id: ev.agent_id, payload: ev.payload, prev_hash: ev.prev_hash };
    let computed;
    try {
      computed = await digestSha256Hex(pythonCanonicalJson(fields));
    } catch (e) {
      return { ok: false, brokenAt: null, reason: e.message || 'SHA-256 unavailable', head: events.at(-1)?.hash ?? null };
    }
    if (computed !== ev.hash) {
      return { ok: false, brokenAt: ev.seq, reason: 'hash mismatch', head: events.at(-1)?.hash ?? null };
    }
    const expectedPrev = i === 0 ? ZERO : events[i - 1].hash;
    if (ev.prev_hash !== expectedPrev) {
      return { ok: false, brokenAt: ev.seq, reason: 'prev_hash break', head: events.at(-1)?.hash ?? null };
    }
  }
  return { ok: true, brokenAt: null, head: events.length ? events[events.length - 1].hash : null };
}

function renderAuditChain(container, events, verifyResult, options = {}) {
  const verdictEvent = events.find((e) => e.event_type === 'CAPTAIN_VERDICT');
  const verdictSealHash = options.auditChainHead || verdictEvent?.hash || null;
  const finalHead = verifyResult.head;
  const showDualHead = verdictSealHash && finalHead && verdictSealHash !== finalHead;
  const verdictVerified = verdictEvent && verdictSealHash === verdictEvent.hash;
  const finalEvent = events.length ? events[events.length - 1] : null;
  const finalVerified = finalEvent && finalHead === finalEvent.hash;

  const badge = verifyResult.ok
    ? `<span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-sm font-medium">Chain Verified ✓</span>`
    : `<span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 text-sm font-medium">${verifyResult.brokenAt != null ? `Chain Broken at seq ${verifyResult.brokenAt} ✗` : (verifyResult.reason || 'Chain verification failed')}</span>`;

  const headNote = (() => {
    if (!finalHead) return '';
    if (showDualHead) {
      const verdictMark = verdictVerified ? '<span class="text-emerald-400">✓ verified at seq ' + verdictEvent.seq + '</span>' : '<span class="text-red-400">✗ mismatch</span>';
      const finalMark = finalVerified ? '<span class="text-emerald-400">✓ verified at seq ' + finalEvent.seq + '</span>' : '<span class="text-red-400">✗ mismatch</span>';
      return `<div class="mt-3 space-y-1 text-xs font-mono">
        <p class="text-slate-500">Verdict sealed at: <span class="text-slate-400">${verdictSealHash}</span> ${verdictMark}</p>
        <p class="text-slate-500">Final chain head: <span class="text-slate-400">${finalHead}</span> ${finalMark}</p>
        <p class="text-slate-600 font-sans mt-1">The verdict hash is frozen at Captain issue time; Liaison report and case-seal events extend the chain afterward.</p>
      </div>`;
    }
    return `<p class="text-xs text-slate-500 mt-3 font-mono">Chain head: <span class="text-slate-400">${finalHead}</span></p>`;
  })();

  const intro = `<div class="mb-6 p-4 rounded-lg border border-slate-700/80 bg-slate-800/30 no-print">
    <p class="text-sm text-slate-300 mb-3">Tamper-evident SHA-256 hash chain. Each event links to the previous via <code class="text-xs text-blue-300">prev_hash</code>. Verified in-browser with <code class="text-xs text-blue-300">crypto.subtle</code> — not decorative.</p>
    <div class="flex flex-wrap items-center gap-3">${badge}<span class="text-xs text-slate-500">${events.length} events</span></div>
    ${headNote}
  </div>`;

  const cards = events.map((ev, i) => {
    const st = agentStyle(ev.agent_id);
    const icon = EVENT_ICONS[ev.event_type] || '•';
    const summary = payloadSummary(ev.payload);
    const prevLabel = ev.seq === 0 ? 'genesis (64 zeros)' : shortHash(ev.prev_hash, 10);
    const linkBlock = i > 0 ? `
      <div class="ml-[1.125rem] pl-6 py-2 flex items-center gap-2 text-xs text-slate-600">
        <div class="flex-1 h-px audit-link-connector"></div>
        <span class="shrink-0 font-mono" title="${ev.prev_hash}">↳ prev ${prevLabel}</span>
        <div class="flex-1 h-px audit-link-connector"></div>
      </div>` : '';

    return `${linkBlock}
      <div class="relative flex gap-4">
        <div class="flex flex-col items-center flex-shrink-0 z-10">
          <div class="w-9 h-9 rounded-full ${st.bg} ${st.border} border flex items-center justify-center text-sm shadow-lg shadow-black/20">${icon}</div>
          ${i < events.length - 1 ? '<div class="w-0.5 flex-1 min-h-[1rem] bg-gradient-to-b from-slate-600 to-slate-700 mt-1"></div>' : ''}
        </div>
        <div class="flex-1 min-w-0 pb-6">
          <div class="audit-card rounded-lg border border-slate-700/80 bg-slate-800/50 p-4 transition-colors${isDebateEvent(ev.event_type) ? ' debate-event' : ''}">
            <div class="flex flex-wrap items-center gap-2 mb-2">
              <span class="text-xs font-mono text-slate-500">seq ${ev.seq}</span>
              <span class="text-xs px-2 py-0.5 rounded ${st.bg} ${st.text} ${st.border} border font-medium">${ev.agent_id.replace('DFIR-', '')}</span>
              <span class="text-xs text-slate-400 uppercase tracking-wide">${ev.event_type.replace(/_/g, ' ')}</span>
              ${isDebateEvent(ev.event_type) ? '<span class="debate-pill text-xs px-2 py-0.5 rounded-full font-medium">Debate</span>' : ''}
            </div>
            <p class="text-xs text-slate-500 mb-3">
              <span class="time-relative" title="${ev.timestamp}">${formatRelativeTime(ev.timestamp)}</span>
              <span class="text-slate-600 mx-1">·</span>
              <span>${formatTimestamp(ev.timestamp)}</span>
            </p>
            <p class="text-sm text-slate-300 mb-3">${summary}</p>
            <details class="mb-3 text-xs no-print">
              <summary class="cursor-pointer text-slate-500 hover:text-slate-300">Raw payload</summary>
              <pre class="mt-2 p-2 rounded bg-slate-900/80 text-slate-400 overflow-x-auto font-mono">${JSON.stringify(ev.payload, null, 2)}</pre>
            </details>
            <div class="space-y-2">
              <div class="flex items-start gap-2">
                <span class="text-xs text-slate-600 shrink-0 pt-1">hash</span>
                <code class="text-xs font-mono text-emerald-400/90 audit-hash-block flex-1">${ev.hash}</code>
                <button type="button" class="copy-hash text-xs px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 shrink-0 no-print" data-hash="${ev.hash}">Copy</button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
  }).join('');

  container.innerHTML = intro + `<div class="relative">${cards}</div>`;

  container.querySelectorAll('.copy-hash').forEach(btn => {
    btn.addEventListener('click', () => copyToClipboard(btn.dataset.hash, btn));
  });
}

function renderTimeline(container, events) {
  const debateCount = events.filter(e => isDebateEvent(e.event_type)).length;
  const intro = debateCount > 0
    ? `<p class="text-sm text-slate-400 mb-4">Investigation timeline from the audit chain. <span class="text-amber-300/90">${debateCount} debate event${debateCount === 1 ? '' : 's'}</span> highlighted — specialists disagreed before the Captain reconciled.</p>`
    : `<p class="text-sm text-slate-400 mb-4">Investigation timeline from the audit chain — same events as the Audit Chain tab, optimized for reading.</p>`;

  container.innerHTML = intro + events.map(ev => {
    const st = agentStyle(ev.agent_id);
    const icon = EVENT_ICONS[ev.event_type] || '•';
    const debate = isDebateEvent(ev.event_type);
    const detail = ev.payload?.question || ev.payload?.directive || ev.payload?.summary || payloadSummary(ev.payload);
    return `<div class="timeline-row flex gap-3 items-start py-3 border-b border-slate-800/80 last:border-0 hover:bg-slate-900/30 px-2 -mx-2 rounded${debate ? ' debate-event' : ''}">
        <span class="text-lg w-6 text-center">${icon}</span>
        <span class="text-xs font-mono text-slate-500 w-8 pt-1">${ev.seq}</span>
        <div class="flex-1 min-w-0">
          <div class="flex flex-wrap gap-2 items-center">
            <span class="text-xs px-2 py-0.5 rounded ${st.bg} ${st.text}">${ev.event_type.replace(/_/g, ' ')}</span>
            <span class="text-sm text-slate-400">${ev.agent_id.replace('DFIR-', '')}</span>
            ${debate ? '<span class="debate-pill text-xs px-2 py-0.5 rounded-full font-medium">Debate</span>' : ''}
          </div>
          <p class="text-sm ${debate ? 'text-amber-100/80' : 'text-slate-500'} mt-1">${detail}</p>
        </div>
        <span class="text-xs text-slate-600 shrink-0 time-relative" title="${ev.timestamp}">${formatRelativeTime(ev.timestamp)}</span>
      </div>`;
  }).join('');
}

const TAB_ON = 'px-4 py-2 text-sm rounded-t-lg text-white border-slate-700 bg-slate-800/80 border border-b-0';
const TAB_OFF = 'px-4 py-2 text-sm rounded-t-lg text-slate-400 border-transparent hover:text-slate-200';

function activateTab(tabId) {
  const tabs = document.querySelectorAll('[data-tab]');
  const panels = document.querySelectorAll('[data-panel]');
  tabs.forEach(t => {
    t.className = (t.dataset.tab === tabId ? TAB_ON : TAB_OFF);
  });
  panels.forEach(p => p.classList.toggle('hidden', p.dataset.panel !== tabId));
  const active = document.querySelector(`[data-tab="${tabId}"]`);
  active?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
}

function initTabs() {
  const tabs = document.querySelectorAll('[data-tab]');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => activateTab(tab.dataset.tab));
  });
  const params = new URLSearchParams(window.location.search);
  const tabParam = params.get('tab');
  if (tabParam && document.querySelector(`[data-tab="${tabParam}"]`)) {
    activateTab(tabParam);
  }
}

function wirePlayCaseButton(caseId) {
  const el = document.getElementById('play-case');
  if (!el) return;
  const url = (window.DFIR_CONFIG && window.DFIR_CONFIG.bandRoomUrl) || 'https://app.band.ai/';
  el.href = url;
  el.target = '_blank';
  el.rel = 'noopener noreferrer';
  el.title = `Open Band room for ${caseId || 'live demo'}`;
}

if (typeof window !== 'undefined') {
  window.DFIR = {
    AGENT_COLORS, CASE_META, DEBATE_EVENTS, loadCaseFile, loadAuditChain, simpleMarkdown,
    verifyAuditChain, renderAuditChain, renderTimeline, renderVerdictStrip, initTabs, activateTab,
    difficultyBadge, agentStyle, formatTimestamp, formatRelativeTime, chainBadgeHtml, mitreTechniqueUrl,
    wirePlayCaseButton, payloadSummary, pythonCanonicalJson, digestSha256Hex, isDebateEvent,
  };
}
