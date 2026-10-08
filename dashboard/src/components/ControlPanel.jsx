import { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL ?? '';

function ControlPanel() {
  const [loading, setLoading] = useState(null);
  const [feedback, setFeedback] = useState(null);

  const triggerActuator = async (target, state = 'on', durationMs = 3000, label = '') => {
    setLoading(target);
    setFeedback(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target,
          state,
          duration_ms: durationMs,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }

      setFeedback({ type: 'success', message: `✅ ${label || target} activé avec succès !` });
    } catch (err) {
      setFeedback({ type: 'error', message: `❌ Erreur : ${err.message}` });
    } finally {
      setLoading(null);
      setTimeout(() => setFeedback(null), 3500);
    }
  };

  return (
    <div className="controls">
      <h3>🎛️ Panneau de Contrôle Réactif (Actionneurs ESP8266)</h3>
      <div className="controls-buttons">
        <button
          onClick={() => triggerActuator('buzzer', 'on', 3000, "Buzzer d'alarme")}
          className="btn-danger"
          disabled={loading !== null}
        >
          {loading === 'buzzer' ? '⏳ Envoi...' : "🚨 Déclencher le Buzzer"}
        </button>

        <button
          onClick={() => triggerActuator('led', 'on', 3000, 'LED de statut')}
          className="btn-warning"
          disabled={loading !== null}
        >
          {loading === 'led' ? '⏳ Envoi...' : '💡 Allumer la LED'}
        </button>

        <button
          onClick={() => triggerActuator('all', 'on', 3000, 'Alerte Totale (Buzzer + LED)')}
          className="btn-primary"
          disabled={loading !== null}
        >
          {loading === 'all' ? '⏳ Envoi...' : '⚡ Alerte Totale (Buzzer + LED)'}
        </button>

        <button
          onClick={() => triggerActuator('all', 'off', 0, 'Arrêt d\'urgence')}
          className="btn-secondary"
          disabled={loading !== null}
        >
          {loading === 'all' && feedback ? '⏳ Envoi...' : '🛑 Arrêt d\'urgence (Stop)'}
        </button>
      </div>

      {feedback && (
        <p className={`feedback ${feedback.type}`}>{feedback.message}</p>
      )}
    </div>
  );
}

export default ControlPanel;