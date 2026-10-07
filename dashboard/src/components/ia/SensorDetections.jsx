function SensorDetections({ detections = [] }) {
  return (
    <div className="ia-card">
      <h4>🎯 Détections capteurs</h4>
      {detections.length === 0 ? (
        <p className="empty">Aucune détection</p>
      ) : (
        <table className="detections-table">
          <thead>
            <tr>
              <th>Capteur</th>
              <th>Valeur</th>
              <th>Heure</th>
            </tr>
          </thead>
          <tbody>
            {detections.map((d, i) => (
              <tr key={i}>
                <td>{d.sensor}</td>
                <td>{d.value}</td>
                <td>{d.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default SensorDetections;