import { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/layout/Header';
import AlertBanner from './components/layout/AlertBanner';
import AlertsBlock from './components/alerts/AlertsBlock';
import IABlock from './components/ia/IABlock';
import SensorsBlock from './components/sensors/SensorsBlock';
import ControlPanel from './components/ControlPanel';

const API_URL = import.meta.env.VITE_API_URL || 'http://172.16.137.5:8080';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://172.16.137.5:8080/ws';
const CAMERA_URL = import.meta.env.VITE_CAMERA_URL || 'http://172.16.137.6:8080/stream.mjpg?key=sentinel-x-secret-key-2026';

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

  // ⭐ State IA prédictive
  const [anomaly, setAnomaly] = useState({
    available: false,
    risk: 0,
    level: 'normal',
    diagnosis_label: null,
    history: [],
  });

  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  const loadInitialData = useCallback(async () => {
    try {
      const resHist = await fetch(`${API_URL}/api/v1/measurements?limit=30`);
      if (resHist.ok) {
        const records = await resHist.json();
        setHistory(records.map((r) => ({
          time: new Date(r.recorded_at).toLocaleTimeString(),
          temp: r.temperature,
          humidity: r.humidity,
          gas: r.gas_raw,
          rssi: r.rssi,
        })));
      }

      const resAlerts = await fetch(`${API_URL}/api/v1/alerts?limit=20`);
      if (resAlerts.ok) {
        const alertList = await resAlerts.json();
        const latestPersonAlert = alertList.find((a) => a.payload?.person_count !== undefined);

        setAlerts(alertList.map((a) => ({
          id: a.id,
          time: new Date(a.created_at).toLocaleTimeString(),
          level: a.level,
          source: a.source,
          message: a.message,
        })));

        if (latestPersonAlert) {
          setIA((prev) => ({
            ...prev,
            personCount: latestPersonAlert.payload.person_count ?? prev.personCount,
          }));
        }
      }
    } catch (err) {
      console.error('Erreur chargement initial', err);
    }
  }, []);

  // ⭐ Récupère l'état IA et le nombre de personnes au démarrage
  const loadAnomalyStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/status`);
      if (!res.ok) return;

      const status = await res.json();
      const devices = status.devices || {};
      const yanshee = devices['yanshee-01'] || Object.values(devices).find((device) => device.person_count !== undefined);

      setIA((prev) => ({
        ...prev,
        personCount: yanshee?.person_count ?? prev.personCount,
      }));

      if (yanshee?.anomaly) {
        setAnomaly((prev) => ({
          ...prev,
          available: true,
          risk: yanshee.anomaly.risk ?? 0,
          level: yanshee.anomaly.level ?? 'normal',
          diagnosis_label: yanshee.anomaly.diagnosis_label ?? null,
        }));
      } else {
        setAnomaly((prev) => ({ ...prev, available: false }));
      }
    } catch {
      // Silencieux
    }
  }, []);

  const handleMessage = useCallback((msg) => {
    if (msg.type === 'connection') return;

    if (msg.type === 'anomaly' && msg.data) {
      const a = msg.data;
      setAnomaly((prev) => ({
        ...prev,
        available: true,
        risk: a.risk ?? 0,
        level: a.level ?? 'normal',
        diagnosis_label: a.diagnosis_label ?? null,
        history: [
          ...prev.history.slice(-60),
          {
            time: new Date().toLocaleTimeString(),
            risk: a.risk ?? 0,
          },
        ],
      }));
      return;
    }

    if (msg.type === 'alert' && msg.data) {
      const a = msg.data;
      setAlerts((prev) => [
        {
          id: a.id ?? Date.now(),
          time: new Date(a.created_at || Date.now()).toLocaleTimeString(),
          level: a.level ?? 'info',
          source: a.source ?? 'unknown',
          message: a.message ?? 'Alerte',
        },
        ...prev.slice(0, 19),
      ]);
      if (a.value !== undefined && a.alert_type?.includes('gas')) {
        setData((prev) => ({ ...prev, gas: a.value }));
      }
      return;
    }

    if (msg.type === 'telemetry' && msg.data) {
      const t = msg.data;
      const newData = {
        temperature: t.temperature ?? 0,
        humidity: t.humidity ?? 0,
        gas: t.gas_raw ?? 0,
        pir: t.presence ?? false,
        rssi: t.rssi ?? -60,
      };
      setData(newData);
      setHistory((prev) => [
        ...prev.slice(-30),
        {
          time: new Date(t.recorded_at || Date.now()).toLocaleTimeString(),
          temp: newData.temperature,
          humidity: newData.humidity,
          gas: newData.gas,
          rssi: newData.rssi,
        },
      ]);
    }
  }, []);

  // ===== CHARGEMENT INITIAL =====
  useEffect(() => {
    loadInitialData();
    loadAnomalyStatus();
  }, [loadInitialData, loadAnomalyStatus]);

  // ===== WEBSOCKET =====
  useEffect(() => {
    let reconnectTimeout, pingInterval;

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 30000);
      };

      ws.onclose = () => {
        setConnected(false);
        clearInterval(pingInterval);
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => console.error('Erreur WS', err);

      ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const msg = JSON.parse(event.data);
          handleMessage(msg);
        } catch (err) {
          console.error('Erreur parsing JSON', err);
        }
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      clearInterval(pingInterval);
      if (wsRef.current) wsRef.current.close();
    };
  }, [handleMessage]);

  const criticalAlert = alerts.find((a) => a.level === 'critical');

  return (
    <div className="app">
      <Header connected={connected} />
      {criticalAlert && <AlertBanner alert={criticalAlert} />}

      <ControlPanel />
      <AlertsBlock alerts={alerts} />
      <IABlock ia={ia} cameraUrl={CAMERA_URL} anomaly={anomaly} />
      <SensorsBlock data={data} history={history} />
    </div>
  );
}

export default App;