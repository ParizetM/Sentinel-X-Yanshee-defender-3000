import { useState, useEffect, useRef } from 'react';
import Header from './components/layout/Header';
import AlertBanner from './components/layout/AlertBanner';
import AlertsBlock from './components/alerts/AlertsBlock';
import IABlock from './components/ia/IABlock';
import SensorsBlock from './components/sensors/SensorsBlock';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws';
const CAMERA_URL = import.meta.env.VITE_CAMERA_URL || 'http://localhost:8080/api/v1/camera/stream';

console.log('API_URL:', import.meta.env.VITE_API_URL);
console.log('WS_URL:', import.meta.env.VITE_WS_URL);
console.log('CAMERA_URL:', import.meta.env.VITE_CAMERA_URL);

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
  const wsRef = useRef(null);

  // ===== CHARGEMENT INITIAL =====
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      // Historique des mesures
      const resHist = await fetch(`${API_URL}/api/v1/measurements?limit=30`);
      if (resHist.ok) {
        const records = await resHist.json();
        setHistory(
          records.map((r) => ({
            time: new Date(r.recorded_at).toLocaleTimeString(),
            temp: r.temperature,
            humidity: r.humidity,
            gas: r.gas_raw,
            rssi: r.rssi,
          }))
        );
      }

      // Alertes récentes
      const resAlerts = await fetch(`${API_URL}/api/v1/alerts?limit=20`);
      if (resAlerts.ok) {
        const alertList = await resAlerts.json();
        setAlerts(
          alertList.map((a) => ({
            id: a.id,
            time: new Date(a.created_at).toLocaleTimeString(),
            level: a.level,
            source: a.source,
            message: a.message,
          }))
        );
      }
    } catch (err) {
      console.error('Erreur chargement initial', err);
    }
  };

  // ===== WEBSOCKET =====
  useEffect(() => {
    let reconnectTimeout;
    let pingInterval;

    const connect = () => {
      console.log('🔌 Connexion WebSocket à', WS_URL);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ WebSocket connecté');
        setConnected(true);

        // Keep-alive : ping toutes les 30s
        pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
      };

      ws.onclose = () => {
        console.log('❌ WebSocket déconnecté, reconnexion dans 3s...');
        setConnected(false);
        clearInterval(pingInterval);
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error('⚠️ Erreur WebSocket', err);
      };

      ws.onmessage = (event) => {
        // Gestion du pong (keep-alive)
        if (event.data === 'pong') return;

        try {
          const msg = JSON.parse(event.data);
          console.log('📩 Message reçu', msg);
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
  }, []);

  // ===== TRAITEMENT DES MESSAGES =====
  const handleMessage = (msg) => {
    // Message de bienvenue (connexion)
    if (msg.type === 'connection') {
      console.log('👋', msg.message);
      return;
    }

    // Message d'alerte
    if (msg.type === 'alert' && msg.data) {
      const a = msg.data;

      // Ajoute l'alerte à la liste
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

      // Si l'alerte contient une mesure, met à jour les données
      if (a.value !== undefined && a.alert_type?.includes('gas')) {
        setData((prev) => ({ ...prev, gas: a.value }));
      }
      return;
    }

    // Message de télémétrie (si le backend en envoie plus tard)
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
      return;
    }
  };

  // ===== ENVOI DE COMMANDES =====
  const sendCommand = async (target, state, duration_ms = 3000) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, state, duration_ms }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      console.log(`✅ Commande ${target}=${state} envoyée`);
      return true;
    } catch (err) {
      console.error('❌ Erreur envoi commande', err);
      return false;
    }
  };

  const criticalAlert = alerts.find((a) => a.level === 'critical');

  return (
    <div className="app">
      <Header connected={connected} />
      {criticalAlert && <AlertBanner alert={criticalAlert} />}

      <AlertsBlock alerts={alerts} />
      <IABlock ia={ia} cameraUrl={CAMERA_URL} />
      <SensorsBlock data={data} history={history} />
    </div>
  );
}

export default App;