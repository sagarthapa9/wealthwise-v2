/**
 * HookInsightCard — displays a per-tab insight about the portfolio allocation.
 *
 * Props:
 *   hook — { insight, prompt, ai_question, severity }
 *          severity is one of "info", "warning", "action"
 *
 * Severity icons: info = 💡, warning = ⚠️, action = 🎯
 */
function HookInsightCard({ hook }) {
  if (!hook || !hook.insight) return null;

  const severityIcons = {
    info: '💡',    // 💡
    warning: '⚠️', // ⚠️
    action: '🎯',  // 🎯
  };
  const icon = severityIcons[hook.severity] || '💡';

  return (
    <div className={`hook-card hook-${hook.severity}`}>
      <div className="hook-body">
        <span className="hook-icon">{icon}</span>
        <span className="hook-text">{hook.insight}</span>
      </div>
      <button
        className="hook-ask-btn"
        title="Ask AI about this insight"
      >
        Ask AI
      </button>
    </div>
  );
}

export default HookInsightCard;
