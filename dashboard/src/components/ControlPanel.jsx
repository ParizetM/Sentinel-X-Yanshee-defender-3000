import { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL ?? '';

function ControlPanel() {
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const triggerBuzzer = async () => {
    setLoading(true);
    setFeedback(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: 'buzzer',
          state: 'on',
          duration_ms: 3000,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }

      setFeedback({ type: 'success', message: '✅ Buzzer déclenché !' });
    } catch (err) {
      setFeedback({ type: 'error', message: `❌ Erreur : ${err.message}` });
    } finally {
      setLoading(false);
      setTimeout(() => setFeedback(null), 3000);
    }
  };

  return (
    <div className="controls">
      <h3>🎛️ Contrôles</h3>

      <button
        onClick={triggerBuzzer}
        className="btn-danger"
        disabled={loading}
      >
        {loading ? '⏳ Envoi...' : '🚨 Déclencher le buzzer'}
      </button>

      {feedback && (
        <p className={`feedback ${feedback.type}`}>{feedback.message}</p>
      )}
    </div>
  );
}

export default ControlPanel;