import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, CartesianGrid
} from 'recharts';

function AnomalyGauge({ risk = 0, history = [], level = 'normal', diagnosis = null }) {
  // Couleur selon le niveau
  const color =
    level === 'critical' ? '#ff3355' :
    level === 'warning'  ? '#ffaa00' :
    '#00ff88';

  // Position de la barre (0 à 2, plafonné à 100%)
  const percentage = Math.min((risk / 2) * 100, 100);

  return (
    <div className="ia-card anomaly-gauge">
      <h4>🧠 Risque IA prédictive</h4>

      {/* Jauge visuelle */}
      <div className="gauge-container">
        <div className="gauge-value" style={{ color }}>
          {risk.toFixed(2)}
        </div>
        <div className="gauge-bar">
          <div
            className="gauge-fill"
            style={{ width: `${percentage}%`, background: color }}
          />
          {/* Ligne du seuil 1 (= 50% de la jauge) */}
          <div className="gauge-threshold" style={{ left: '50%' }} />
        </div>
        <div className="gauge-labels">
          <span>0</span>
          <span className="threshold-label">Seuil</span>
          <span>2</span>
        </div>
      </div>

      {/* Diagnostic IA */}
      {diagnosis && (
        <p className="diagnosis" style={{ color }}>
          ⚠️ {diagnosis}
        </p>
      )}

      {/* Graphique d'évolution du risque */}
      {history.length > 0 && (
        <div className="risk-chart">
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={history}>
              <CartesianGrid stroke="#1f2a44" />
              <XAxis dataKey="time" stroke="#8899bb" fontSize={10} />
              <YAxis stroke="#8899bb" fontSize={10} domain={[0, 2]} />
              <Tooltip contentStyle={{ background: '#131829', border: '1px solid #1f2a44' }} />
              <ReferenceLine
                y={1}
                stroke="#ff3355"
                strokeDasharray="5 5"
                label={{ value: 'Seuil', fill: '#ff3355', fontSize: 10 }}
              />
              <Line type="monotone" dataKey="risk" stroke="#00e5ff" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default AnomalyGauge;