import {
  LineChart, Line, XAxis, YAxis,
  Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';

function RssiChart({ data }) {
  return (
    <div className="chart-small">
      <h3>Signal Wi-Fi (dBm)</h3>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2a44" />
          <XAxis dataKey="time" stroke="#8899bb" fontSize={10} />
          <YAxis stroke="#8899bb" fontSize={10} domain={[-100, -30]} />
          <Tooltip contentStyle={{ background: '#131829', border: '1px solid #1f2a44' }} />
          <Line type="monotone" dataKey="rssi" stroke="#ffaa00" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default RssiChart;