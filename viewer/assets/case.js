/* Case detail page bootstrap */

(async function () {
  const caseNum = document.body.dataset.case;
  if (!caseNum) return;

  const meta = window.DFIR.CASE_META[caseNum];
  try {
    const [caseFile, auditEvents] = await Promise.all([
      window.DFIR.loadCaseFile(caseNum),
      window.DFIR.loadAuditChain(caseNum),
    ]);

    document.getElementById('case-title').textContent = meta.name;
    document.getElementById('case-org').textContent = `${meta.org} · ${meta.location}`;
    document.getElementById('case-id').textContent = caseFile.case_id;
    document.getElementById('case-opened').textContent = window.DFIR.formatTimestamp(caseFile.opened_at);
    document.getElementById('case-closed').textContent = window.DFIR.formatTimestamp(caseFile.closed_at);

    const badge = document.getElementById('difficulty-badge');
    badge.textContent = meta.difficulty.toUpperCase();
    badge.className = `text-xs px-2 py-1 rounded border font-medium ${window.DFIR.difficultyBadge(meta.difficulty)}`;

    if (meta.hero) {
      document.getElementById('hero-badge')?.classList.remove('hidden');
    }

    document.getElementById('summary-content').innerHTML = window.DFIR.simpleMarkdown(caseFile.liaison_report_md);
    document.getElementById('brief-content').innerHTML = window.DFIR.simpleMarkdown(caseFile.case_brief_md);

    const timeline = document.getElementById('timeline-content');
    timeline.innerHTML = auditEvents.map(ev => {
      const st = window.DFIR.agentStyle(ev.agent_id);
      return `<div class="flex gap-3 items-start py-2 border-b border-slate-800 last:border-0">
        <span class="text-xs font-mono text-slate-500 w-8">${ev.seq}</span>
        <span class="text-xs px-2 py-0.5 rounded ${st.bg} ${st.text} shrink-0">${ev.event_type.replace(/_/g, ' ')}</span>
        <span class="text-sm text-slate-400">${ev.agent_id.replace('DFIR-', '')}</span>
        <span class="text-xs text-slate-600 ml-auto">${window.DFIR.formatTimestamp(ev.timestamp)}</span>
      </div>`;
    }).join('');

    const v = caseFile.captain_verdict;
    document.getElementById('mitre-content').innerHTML = `
      <div class="mb-4 p-4 rounded-lg bg-slate-800/50 border border-slate-700">
        <p class="text-lg font-semibold text-white">${v.classification}</p>
        <p class="text-slate-400 text-sm">${v.subtype || ''}</p>
        <p class="text-slate-300 mt-2 text-sm"><span class="text-slate-500">Initial access:</span> ${v.initial_access_vector}</p>
      </div>
      <table class="w-full text-sm">
        <thead><tr class="text-left text-slate-500 border-b border-slate-700">
          <th class="py-2 pr-4">ID</th><th class="py-2 pr-4">Technique</th><th class="py-2">Evidence</th>
        </tr></thead>
        <tbody>${(v.mitre_techniques || []).map(t => `
          <tr class="border-b border-slate-800">
            <td class="py-3 pr-4 font-mono text-blue-400">${t.id}</td>
            <td class="py-3 pr-4 text-slate-200">${t.name}</td>
            <td class="py-3 text-slate-400">${t.evidence}</td>
          </tr>`).join('')}
        </tbody>
      </table>`;

    const catalog = document.getElementById('evidence-content');
    catalog.innerHTML = (caseFile.all_findings || []).map(f => {
      const st = window.DFIR.agentStyle(f.specialist);
      return `<details class="mb-3 rounded-lg border border-slate-700 bg-slate-800/30 group" open>
        <summary class="cursor-pointer px-4 py-3 font-medium ${st.text}">${f.specialist.replace('DFIR-', '')} — ${f.findings.length} finding(s)</summary>
        <div class="px-4 pb-4 space-y-3">${f.findings.map(item => `
          <div class="pl-3 border-l-2 ${st.border}">
            <p class="text-slate-200 text-sm">${item.summary}</p>
            <p class="text-xs text-slate-500 mt-1">Confidence: ${item.confidence} · MITRE: ${(item.mitre_techniques || []).join(', ') || '—'}</p>
            <p class="text-xs font-mono text-slate-600 mt-1">${(item.evidence_refs || []).join(', ')}</p>
          </div>`).join('')}
        </div>
      </details>`;
    }).join('');

    const actions = document.getElementById('actions-content');
    actions.innerHTML = `
      <ul class="space-y-2 mb-6">${(v.immediate_actions || []).map(a => `<li class="flex gap-2 text-slate-300"><span class="text-amber-400">→</span>${a}</li>`).join('')}</ul>
      <h3 class="text-sm font-medium text-slate-400 mb-2">Regulatory obligations</h3>
      <ul class="space-y-1 mb-6">${(v.regulatory_obligations || []).map(a => `<li class="text-sm text-slate-400">• ${a}</li>`).join('')}</ul>
      <h3 class="text-sm font-medium text-slate-400 mb-2">Follow-up recommended</h3>
      <ul class="space-y-1">${(v.human_followup_recommended || []).map(a => `<li class="text-sm text-slate-400">• ${a}</li>`).join('')}</ul>`;

    const verifyResult = await window.DFIR.verifyAuditChain(auditEvents);
    window.DFIR.renderAuditChain(document.getElementById('audit-content'), auditEvents, verifyResult);

  } catch (err) {
    console.error(err);
    document.getElementById('case-error')?.classList.remove('hidden');
  }

  window.DFIR.initTabs();
})();
