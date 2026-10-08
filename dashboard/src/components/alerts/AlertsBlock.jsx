import { useState } from 'react';

function AlertsBlock({ alerts = [] }) {
  const [expanded, setExpanded] = useState(false);

  // Affiche 3 alertes par défaut, ou la totalité si déplié
  const displayedAlerts = expanded ? alerts : alerts.slice(0, 3);

  return (
    <section className="block alerts-block">
      <div
        className="alerts-header"
        onClick={() => alerts.length > 3 && setExpanded(!expanded)}
        style={{ cursor: alerts.length > 3 ? 'pointer' : 'default' }}
      >
        <h2>
          🚨 Alertes{' '}
          {alerts.length > 0 && <span className="alerts-count">({alerts.length})</span>}
        </h2>
        {alerts.length > 3 && (
          <span className="alerts-toggle-hint">
            {expanded ? '▲ Réduire' : `▼ Déplier (${alerts.length})`}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <p className="empty">Aucune alerte</p>
      ) : (
        <>
          <ul className="alerts-list">
            {displayedAlerts.map((a) => (
              <li key={a.id} className={`alert alert-${a.level}`}>
                <span className="alert-icon">
                  {a.level === 'critical' ? '🚨' : a.level === 'warning' ? '⚠️' : 'ℹ️'}
                </span>
                <span className="alert-time">{a.time}</span>
                <span className={`alert-source source-${a.source?.replace('_', '-')}`}>
                  {a.source === 'ia_anomaly' ? '🧠 IA' :
                   a.source === 'ia_vision'  ? '👁️ Vision' :
                   a.source === 'sensor'     ? '📡 Capteur' :
                   `[${a.source}]`}
                </span>
                <span className="alert-message">{a.message}</span>
              </li>
            ))}
          </ul>

          {alerts.length > 3 && (
            <button
              type="button"
              className="btn-toggle-alerts"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded
                ? '▲ Réduire (afficher les 3 récentes)'
                : `▼ Voir toutes les alertes (${alerts.length - 3} masquées)`}
            </button>
          )}
        </>
      )}
    </section>
  );
}

export default AlertsBlock;