function PersonCounter({ count = 0 }) {
  return (
    <div className="ia-card">
      <h4>👤 Personnes détectées</h4>
      <p className="ia-value">{count}</p>
    </div>
  );
}

export default PersonCounter;   