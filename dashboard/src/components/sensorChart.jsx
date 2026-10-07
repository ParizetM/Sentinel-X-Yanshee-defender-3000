import {
  LineChart, Line, XAxis, YAxis,
  Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';

function SensorChart({ data }) {
  return (
    <div className="chart-container">
      <h3>Température & Gaz temps réel</h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2a44" />
          <XAxis dataKey="time" stroke="#8899bb" />
          <YAxis stroke="#8899bb" />
          <Tooltip
            contentStyle={{
              background: '#131829',
              border: '1px solid #1f2a44'
            }}
          />
          <Line
            type="monotone"
            dataKey="temp"
            stroke="#00e5ff"
            strokeWidth={2}
            name="Température"
          />
          <Line
            type="monotone"
            dataKey="gas"
            stroke="#ff3355"
            strokeWidth={2}
            name="Gaz"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default SensorChart;