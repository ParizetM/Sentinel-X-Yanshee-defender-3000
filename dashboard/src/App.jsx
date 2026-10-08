import { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/layout/Header';
import AlertBanner from './components/layout/AlertBanner';
import AlertsBlock from './components/alerts/AlertsBlock';
import IABlock from './components/ia/IABlock';
import SensorsBlock from './components/sensors/SensorsBlock';
import ControlPanel from './components/ControlPanel';

const API_URL = import.meta.env.VITE_API_URL ?? '';
const WS_URL = import.meta.env.VITE_WS_URL || (typeof window !== 'undefined' ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws` : 'ws://172.16.137.5:8080/ws');
const CAMERA_URL = import.meta.env.VITE_CAMERA_URL || '/api/v1/camera/stream';

function App() {
  const [data, setData] = useState({
    temperature: 0,
    humidity: 0,
    gas: 0,
    pir: false,
    rssi: -60,
  });

  const [history, setHistory] = useState([]);
  const [ia, setIa] = useState({
    personCount: 0,
    detectionsLastHour: 0,
    robotActions: [],
    photos: [],
    sensorDetections: [],
  });

  // ⭐ State IA prédictive
  const [anomaly, setAnomaly] = useState({
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
        setAlerts(alertList.map((a) => ({
          id: a.id,
          time: new Date(a.created_at).toLocaleTimeString(),
          level: a.level,
          source: a.source,
          message: a.message,
        })));
      }

      // ⭐ Chargement de l'historique des photos depuis MariaDB Galera
      try {
        const resPhotos = await fetch(`${API_URL}/api/v1/camera/photos?limit=6`);
        if (resPhotos.ok) {
          const photoList = await resPhotos.json();
          if (photoList.length > 0) {
            setIa((prev) => ({
              ...prev,
              photos: photoList.map((p) => {
                const cTime = p.captured_at ? new Date(p.captured_at).toLocaleTimeString() : new Date().toLocaleTimeString();
                return {
                  id: p.id,
                  url: `${API_URL}${p.url}?t=${Date.now()}`,
                  time: cTime,
                  label: `Intrusion #${p.id} (${cTime})`,
                };
              }),
            }));
          } else {
            const resPhoto = await fetch(`${API_URL}/api/v1/camera/latest_photo`);
            if (resPhoto.ok) {
              const tsHeader = resPhoto.headers.get('X-Capture-Timestamp');
              const captureTime = tsHeader ? new Date(tsHeader).toLocaleTimeString() : new Date().toLocaleTimeString();
              setIa((prev) => ({
                ...prev,
                photos: [
                  {
                    url: `${API_URL}/api/v1/camera/latest_photo?t=${Date.now()}`,
                    time: captureTime,
                    label: `Intrusion (${captureTime})`,
                  },
                ],
              }));
            }
          }
        }
      } catch {
        // Aucune photo capturée pour le moment
      }
    } catch (err) {
      console.error('Erreur chargement initial', err);
    }
  }, []);

  // ⭐ Récupère l'état IA au démarrage
  const loadAnomalyStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/status`);
      if (res.ok) {
        const status = await res.json();
        const devices = status.devices || {};
        const firstDevice = Object.values(devices)[0];
        if (firstDevice?.anomaly) {
          setAnomaly((prev) => ({
            ...prev,
            risk: firstDevice.anomaly.risk ?? 0,
            level: firstDevice.anomaly.level ?? 'normal',
            diagnosis_label: firstDevice.anomaly.diagnosis_label ?? null,
          }));
        }
        if (devices['yanshee-01']?.person_count !== undefined) {
          setIa((prev) => ({
            ...prev,
            personCount: devices['yanshee-01'].person_count,
          }));
        }
      }
    } catch {
      // Silencieux
    }
  }, []);

  const handleMessage = useCallback((msg) => {
    if (msg.type === 'connection') return;

    // ⭐ Réception temps réel d'une photo capturée par l'IA YOLO
    if (msg.type === 'photo') {
      const p = msg.data || {};
      const captureTime = p.timestamp ? new Date(p.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
      const photoUrl = `${API_URL}${p.url || '/api/v1/camera/latest_photo'}?t=${Date.now()}`;
      setIa((prev) => ({
        ...prev,
        photos: [
          {
            url: photoUrl,
            time: captureTime,
            label: `Intrusion (${captureTime})`,
          },
          ...prev.photos.slice(0, 5),
        ],
      }));
      return;
    }

    // ⭐ Mise à jour du compteur de personnes en direct
    if (msg.type === 'person_count' && msg.data) {
      setIa((prev) => ({
        ...prev,
        personCount: msg.data.person_count ?? 0,
      }));
      return;
    }

    // ⭐ Actions physiques exécutées par le robot
    if (msg.type === 'robot_action' && msg.data) {
      const actionName = typeof msg.data === 'string' ? msg.data : JSON.stringify(msg.data);
      setIa((prev) => ({
        ...prev,
        robotActions: [
          {
            time: new Date().toLocaleTimeString(),
            action: actionName,
          },
          ...prev.robotActions.slice(0, 9),
        ],
      }));
      return;
    }

    if (msg.type === 'anomaly' && msg.data) {
      const a = msg.data;
      setAnomaly((prev) => ({
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
      // Si alerte intrusion : rafraîchir la photo
      if (a.alert_type === 'human_intrusion' || a.source === 'ia_vision') {
        const captureTime = new Date(a.created_at || Date.now()).toLocaleTimeString();
        setTimeout(async () => {
          try {
            const resPhoto = await fetch(`${API_URL}/api/v1/camera/latest_photo`);
            if (resPhoto.ok) {
              setIa((prev) => ({
                ...prev,
                photos: [
                  {
                    url: `${API_URL}/api/v1/camera/latest_photo?t=${Date.now()}`,
                    time: captureTime,
                    label: `Intrusion (${captureTime})`,
                  },
                  ...prev.photos.slice(0, 5),
                ],
              }));
            }
          } catch {}
        }, 300);
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