import { useState, useEffect } from 'react';
import Header from './components/layout/header.jsx';
import AlertBanner from './components/layout/alertBanner.jsx';
import AlertsBlock from './components/alerts/AlertsBlock.jsx';
import IABlock from './components/ia/IABlock';
import SensorsBlock from './components/sensors/SensorsBlock';

const CAMERA_URL = import.meta.env.VITE_CAMERA_URL || 'http://localhost:5000/video_feed';

function App() {
  const [data, setData] = useState({
    temperature: 0,
    humidity: 0,
    gas: 0,
    pir: false,
    rssi: -60,
  });

  const [history, setHistory] = useState([]);
  const [ia, setIA] = useState({
    personCount: 0,
    detectionsLastHour: 0,
    robotActions: [],
    photos: [],
    sensorDetections: [],
  });
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);

  // SIMULATION — à remplacer par WebSocket plus tard
  useEffect(() => {
    const interval = setInterval(() => {
      const newData = {
        temperature: 22 + Math.random() * 4,
        humidity: 40 + Math.random() * 20,
        gas: 100 + Math.random() * 400,
        pir: Math.random() > 0.7,
        rssi: -50 - Math.random() * 30,
      };

      setData(newData);
      setConnected(true);

      setHistory((prev) => [
        ...prev.slice(-30),
        {
          time: new Date().toLocaleTimeString(),
          temp: newData.temperature,
          humidity: newData.humidity,
          gas: newData.gas,
          rssi: newData.rssi,
        },
      ]);

      setIA((prev) => ({
        ...prev,
        personCount: Math.floor(Math.random() * 4),
        detectionsLastHour: prev.detectionsLastHour + (Math.random() > 0.9 ? 1 : 0),
        robotActions: [
          {
            time: new Date().toLocaleTimeString(),
            action: 'Scan zone',
          },
          ...prev.robotActions.slice(0, 4),
        ],
        photos: prev.photos,
        sensorDetections: [
          {
            sensor: 'PIR',
            value: newData.pir ? 'Présence' : 'Aucune',
            time: new Date().toLocaleTimeString(),
          },
          ...prev.sensorDetections.slice(0, 4),
        ],
      }));

      if (newData.gas > 400) {
        setAlerts((prev) => [
          {
            id: Date.now(),
            time: new Date().toLocaleTimeString(),
            level: 'critical',
            source: 'sensor',
            message: `Gaz élevé : ${newData.gas.toFixed(0)} ppm`,
          },
          ...prev.slice(0, 9),
        ]);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const criticalAlert = alerts.find((a) => a.level === 'critical');

  return (
    <div className="app">
      <Header connected={connected} />
      {criticalAlert && <AlertBanner alert={criticalAlert} />}

      {/* ORDRE : Alertes → IA → Capteurs */}
      <AlertsBlock alerts={alerts} />
      <IABlock ia={ia} cameraUrl={CAMERA_URL} />
      <SensorsBlock data={data} history={history} />
    </div>
  );
}

export default App;