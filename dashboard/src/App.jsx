import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

function App() {
  const [data, setData] = useState([]);

  // Simulation de données (en attendant le vrai WebSocket)
  useEffect(() => {
    const interval = setInterval(() => {
      setData((prev) => [
        ...prev.slice(-30),
        {
          time: new Date().toLocaleTimeString(),
          temp: 22 + Math.random() * 4,
          gas: 100 + Math.random() * 50,
        },
      ]);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ padding: 20, background: '#0a0e1a', minHeight: '100vh', color: '#e0e6f0' }}>
      <h1 style={{ color: '#00e5ff' }}>SENTINEL-X</h1>
      <h3>Température & Gaz temps réel</h3>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2a44" />
          <XAxis dataKey="time" stroke="#8899bb" />
          <YAxis stroke="#8899bb" />
          <Tooltip
            contentStyle={{ background: '#131829', border: '1px solid #1f2a44' }}
          />
          <Line type="monotone" dataKey="temp" stroke="#00e5ff" strokeWidth={2} name="Température" />
          <Line type="monotone" dataKey="gas" stroke="#ff3355" strokeWidth={2} name="Gaz" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default App;