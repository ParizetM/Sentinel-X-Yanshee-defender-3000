import SensorCard from './SensorCard';
import GazChart from './GazChart';
import TempChart from './TempChart';
import HumidityChart from './HumidityChart';
import RssiChart from './RssiChart';

function SensorsBlock({ data, history }) {
  return (
    <section className="block">
      <h2>📊 Capteurs</h2>

      <div className="grid">
        <SensorCard
          title="Gaz"
          value={data.gas?.toFixed(0) ?? '—'}
          unit="ppm"
          alert={data.gas > 400}
        />
        <SensorCard
          title="Température"
          value={data.temperature?.toFixed(1) ?? '—'}
          unit="°C"
        />
        <SensorCard
          title="Humidité"
          value={data.humidity?.toFixed(1) ?? '—'}
          unit="%"
        />
        <SensorCard
          title="Signal Wi-Fi"
          value={data.rssi ?? '—'}
          unit="dBm"
        />
      </div>

      <div className="charts-grid">
        <GazChart data={history} />
        <TempChart data={history} />
        <HumidityChart data={history} />
        <RssiChart data={history} />
      </div>
    </section>
  );
}

export default SensorsBlock;