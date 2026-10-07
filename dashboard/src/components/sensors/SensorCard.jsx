function SensorCard({ title, value, unit, alert = false }) {
  return (
    <div className={`card ${alert ? 'card-alert' : ''}`}>
      <h3>{title}</h3>
      <p className="value">
        {value} <span>{unit}</span>
      </p>
    </div>
  );
}

export default SensorCard;