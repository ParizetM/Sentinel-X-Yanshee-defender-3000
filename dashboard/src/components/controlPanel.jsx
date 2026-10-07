

function ControlPanel() {
  const triggerAlarm = async () => {
    await fetch('http://localhost:3000/api/v1/control/alarm', {
      method: 'POST',
    });
    alert('Alarme déclenchée !');
  };

  const toggleLed = async () => {
    await fetch('http://localhost:3000/api/v1/control/led', {
      method: 'POST',
    });
  };

  return (
    <div className="controls">
      <h3>Contrôles</h3>
      <button onClick={triggerAlarm} className="btn-danger">
        🚨 Déclencher l'alarme
      </button>
      <button onClick={toggleLed} className="btn">
        💡 Toggle LED
      </button>
    </div>
  );
}

export default ControlPanel;