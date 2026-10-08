function RobotActions({ actions = [] }) {
  return (
    <div className="ia-card">
      <h4>🤖 Dernières actions</h4>
      {actions.length === 0 ? (
        <p className="empty">Aucune action récente</p>
      ) : (
        <ul className="actions-list">
          {actions.map((a, i) => (
            <li key={i}>
              <span className="action-time">{a.time}</span>
              <span className="action-name">{a.action}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default RobotActions;