
function AlertsBlock({ alerts = [] }) {
  return (
    <section className="block">
      <h2>🚨 Alertes</h2>
      {alerts.length === 0 ? (
        <p className="empty">Aucune alerte</p>
      ) : (
        <ul className="alerts-list">
          {alerts.map((a) => (
            <li key={a.id} className={`alert alert-${a.level}`}>
              <span className="alert-icon">
                {a.level === 'critical' ? '🚨' : a.level === 'warning' ? '⚠️' : 'ℹ️'}
              </span>
              <span className="alert-time">{a.time}</span>
              <span className="alert-source">[{a.source}]</span>
              <span className="alert-message">{a.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default AlertsBlock;