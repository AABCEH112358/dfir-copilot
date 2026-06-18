/* Case detail page bootstrap */

(async function () {
  const caseNum = document.body.dataset.case;
  if (!caseNum) return;

  const meta = window.DFIR.CASE_META[caseNum];
  const loadingEl = document.getElementById('case-loading');
  const contentEl = document.getElementById('case-content');

  try {
    const [caseFile, auditEvents] = await Promise.all([
      window.DFIR.loadCaseFile(caseNum),
      window.DFIR.loadAuditChain(caseNum),
    ]);

    const verifyResult = await window.DFIR.verifyAuditChain(auditEvents);
    const debateCount = auditEvents.filter(e => window.DFIR.isDebateEvent(e.event_type)).length;

    document.getElementById('case-title').textContent = meta.name;
    document.getElementById('case-org').textContent = `${meta.org} · ${meta.location}`;
    document.getElementById('case-id').textContent = caseFile.case_id;
    document.getElementById('case-opened').textContent = window.DFIR.formatTimestamp(caseFile.opened_at);
    document.getElementById('case-closed').textContent = window.DFIR.formatTimestamp(caseFile.closed_at);

    const printTitle = document.getElementById('print-title');
    if (printTitle) printTitle.textContent = `${meta.name} — ${caseFile.case_id}`;

    const badge = document.getElementById('difficulty-badge');
    badge.textContent = meta.difficulty.toUpperCase();
    badge.className = `text-xs px-2 py-1 rounded border font-medium ${window.DFIR.difficultyBadge(meta.difficulty)}`;

    if (meta.hero) {
      document.getElementById('hero-badge')?.classList.remove('hidden');
    }

    const headerChain = document.getElementById('header-chain-status');
    if (headerChain) headerChain.innerHTML = window.DFIR.chainBadgeHtml(verifyResult, { compact: true });

    window.DFIR.wirePlayCaseButton(caseFile.case_id);

    const v = caseFile.captain_verdict;
    window.DFIR.renderVerdictStrip(
      document.getElementById('verdict-strip'),
      v,
      verifyResult,
      auditEvents.length,
      debateCount,
    );

    document.getElementById('summary-content').innerHTML = window.DFIR.simpleMarkdown(caseFile.liaison_report_md);
    document.getElementById('brief-content').innerHTML = window.DFIR.simpleMarkdown(caseFile.case_brief_md);
    window.DFIR.renderTimeline(document.getElementById('timeline-content'), auditEvents);

    document.getElementById('mitre-content').innerHTML = `
      <div class="mb-4 p-4 rounded-lg bg-slate-800/50 border border-slate-700">
        <p class="text-lg font-semibold text-white">${v.classification}</p>
        <p class="text-slate-400 text-sm">${v.subtype || ''}</p>
        <p class="text-slate-300 mt-2 text-sm"><span class="text-slate-500">Initial access:</span> ${v.initial_access_vector}</p>
        ${v.threat_actor_attribution ? `<p class="text-slate-400 text-sm mt-1"><span class="text-slate-500">Attribution:</span> ${v.threat_actor_attribution.group} (${v.threat_actor_attribution.confidence})</p>` : ''}
      </div>
      <div class="overflow-x-auto rounded-lg border border-slate-800">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-slate-500 border-b border-slate-700 bg-slate-900/50">
          <th class="py-3 px-4">ID</th><th class="py-3 px-4">Technique</th><th class="py-3 px-4">Evidence</th>
        </tr></thead>
        <tbody>${(v.mitre_techniques || []).map(t => `
          <tr class="border-b border-slate-800/80 hover:bg-slate-900/40">
            <td class="py-3 px-4 font-mono"><a href="${window.DFIR.mitreTechniqueUrl(t.id)}" target="_blank" rel="noopener" class="text-blue-400 hover:text-blue-300">${t.id} ↗</a></td>
            <td class="py-3 px-4 text-slate-200">${t.name}</td>
            <td class="py-3 px-4 text-slate-400">${t.evidence}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      </div>`;

    const catalog = document.getElementById('evidence-content');
    catalog.innerHTML = (caseFile.all_findings || []).map(f => {
      const st = window.DFIR.agentStyle(f.specialist);
      return `<details class="mb-3 rounded-lg border border-slate-700 bg-slate-800/30 group" open>
        <summary class="cursor-pointer px-4 py-3 font-medium ${st.text} flex items-center gap-2">
          <span class="w-2 h-2 rounded-full ${st.dot}"></span>
          ${f.specialist.replace('DFIR-', '')} — ${f.findings.length} finding(s)
        </summary>
        <div class="px-4 pb-4 space-y-3">${f.findings.map(item => `
          <div class="pl-3 border-l-2 ${st.border}">
            <p class="text-slate-200 text-sm">${item.summary}</p>
            <p class="text-xs text-slate-500 mt-1">Confidence: <span class="text-slate-400">${item.confidence}</span> · MITRE: ${(item.mitre_techniques || []).map(id => `<a href="${window.DFIR.mitreTechniqueUrl(id)}" class="text-blue-400/80 hover:text-blue-300" target="_blank" rel="noopener">${id}</a>`).join(', ') || '—'}</p>
            <p class="text-xs font-mono text-slate-600 mt-1">${(item.evidence_refs || []).join(', ')}</p>
          </div>`).join('')}
        ${(f.open_questions || []).length ? `<p class="text-xs text-amber-400/80 mt-2 px-4">Open: ${f.open_questions.join('; ')}</p>` : ''}
        </div>
      </details>`;
    }).join('');

    document.getElementById('actions-content').innerHTML = `
      <ul class="space-y-2 mb-6">${(v.immediate_actions || []).map(a => `<li class="flex gap-2 text-slate-300"><span class="text-amber-400 shrink-0">→</span><span>${a}</span></li>`).join('')}</ul>
      <h3 class="text-sm font-medium text-slate-400 mb-2">Regulatory obligations</h3>
      <ul class="space-y-1 mb-6">${(v.regulatory_obligations || []).map(a => `<li class="text-sm text-slate-400">• ${a}</li>`).join('')}</ul>
      <h3 class="text-sm font-medium text-slate-400 mb-2">Follow-up recommended</h3>
      <ul class="space-y-1">${(v.human_followup_recommended || []).map(a => `<li class="text-sm text-slate-400">• ${a}</li>`).join('')}</ul>`;

    window.DFIR.renderAuditChain(document.getElementById('audit-content'), auditEvents, verifyResult, {
      auditChainHead: v.audit_chain_head,
    });

    const auditTab = document.querySelector('[data-tab="audit"]');
    if (auditTab && !auditTab.querySelector('.tab-badge')) {
      auditTab.insertAdjacentHTML('beforeend', `<span class="tab-badge bg-emerald-500/20 text-emerald-300">${verifyResult.ok ? '✓' : '!'}</span>`);
    }
    if (debateCount > 0) {
      const timelineTab = document.querySelector('[data-tab="timeline"]');
      if (timelineTab && !timelineTab.querySelector('.tab-badge')) {
        timelineTab.insertAdjacentHTML('beforeend', `<span class="tab-badge debate-pill">${debateCount}</span>`);
      }
    }

    loadingEl?.classList.add('hidden');
    contentEl?.classList.remove('hidden');

  } catch (err) {
    console.error(err);
    loadingEl?.classList.add('hidden');
    document.getElementById('case-error')?.classList.remove('hidden');
  }

  window.DFIR.initTabs();
})();
