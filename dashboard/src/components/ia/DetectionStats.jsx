function DetectionStats({ count = 0 }) {
  return (
    <div className="ia-card">
      <h4>📊 Détections (1h)</h4>
      <p className="ia-value">{count}</p>
    </div>
  );
}

export default DetectionStats;