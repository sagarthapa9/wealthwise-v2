const SEVERITY_MAP = {
  info: { border: 'si-border-info', bg: 'si-bg-info', title: 'si-title-info', ticker: 'si-ticker-info', muted: 'si-muted-info', tipBorder: 'si-tip-border-info' },
  warning: { border: 'si-border-warning', bg: 'si-bg-warning', title: 'si-title-warning', ticker: 'si-ticker-warning', muted: 'si-muted-warning', tipBorder: 'si-tip-border-warning' },
  danger: { border: 'si-border-danger', bg: 'si-bg-danger', title: 'si-title-danger', ticker: 'si-ticker-danger', muted: 'si-muted-danger', tipBorder: 'si-tip-border-danger' },
  success: { border: 'si-border-success', bg: 'si-bg-success', title: 'si-title-success', ticker: 'si-ticker-success', muted: 'si-muted-success', tipBorder: 'si-tip-border-success' },
  action: { border: 'si-border-danger', bg: 'si-bg-danger', title: 'si-title-danger', ticker: 'si-ticker-danger', muted: 'si-muted-danger', tipBorder: 'si-tip-border-danger' },
};

/**
 * HookInsightCard — severity-based insight card with hover tooltip.
 *
 * Accepts either a single `hook` (old format) or `sections` (new format).
 *
 * Old format (hook prop):
 *   { insight, prompt, ai_question, severity, tooltip }
 *
 * New format (sections prop):
 *   [{ severity, title, tooltip, insights: [{ ticker, message, value? }] }]
 */
function HookInsightCard({ hook, sections, onAsk }) {

  // ── Old format: single hook ─────────────────────────────────────
  if (hook && hook.insight) {
    const s = SEVERITY_MAP[hook.severity] || SEVERITY_MAP.info;
    return (
      <div className={`si-card ${s.border} ${s.bg}`}>
        <div className="si-header">
          <span className={`si-title ${s.title}`}>{hook.severity === 'action' ? 'Action Needed' : hook.severity === 'warning' ? 'Warning' : 'Insight'}</span>
          <div className="si-info-wrap">
            <svg className="si-info-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
            </svg>
            <div className={`si-tooltip ${s.tipBorder}`}>
              <div className="si-tip-title">{hook.severity === 'action' ? 'Action Needed' : hook.severity === 'warning' ? 'Concentration Warning' : 'Insight'}</div>
              <div className="si-tip-body">{hook.tooltip}</div>
            </div>
          </div>
        </div>
        <div className="si-row">
          <span className="si-row-text">{hook.insight}</span>
        </div>
        {onAsk && hook.ai_question && (
          <button className="si-ask-btn" onClick={() => onAsk(hook.ai_question)}>Ask AI</button>
        )}
      </div>
    );
  }

  // ── New format: multiple sections ───────────────────────────────
  if (!sections || sections.length === 0) return null;

  return (
    <div className="si-stack">
      {sections.map((sec, i) => {
        if (!sec.insights || sec.insights.length === 0) return null;
        const s = SEVERITY_MAP[sec.severity] || SEVERITY_MAP.info;

        return (
          <div key={i} className={`si-card ${s.border} ${s.bg}`}>
            <div className="si-header">
              <span className={`si-title ${s.title}`}>{sec.title}</span>
              <div className="si-info-wrap">
                <svg className="si-info-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
                </svg>
                <div className={`si-tooltip ${s.tipBorder}`}>
                  <div className="si-tip-title">{sec.title}</div>
                  <div className="si-tip-body">{sec.tooltip}</div>
                </div>
              </div>
            </div>
            <div className="si-list">
              {sec.insights.map((ins, j) => (
                <div key={j} className="si-row">
                  <span className={`si-row-ticker ${s.ticker}`}>{ins.ticker}</span>
                  <span className="si-row-text">{ins.message}</span>
                  {ins.value && <span className={`si-row-val ${s.muted}`}>{ins.value}</span>}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default HookInsightCard;
