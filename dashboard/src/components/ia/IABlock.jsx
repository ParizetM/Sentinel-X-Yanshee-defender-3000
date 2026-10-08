import PersonCounter from './PersonCounter';
import YoloStream from './YoloStream';
import RobotActions from './RobotActions';
import PhotosGallery from './PhotosGallery';
import SensorDetections from './SensorDetections';
import AnomalyGauge from './AnomalyGauge';

function IABlock({ ia, cameraUrl, anomaly }) {
  return (
    <section className="block">
      <h2>🤖 Intelligence Artificielle</h2>

      {/* ⭐ Jauge IA prédictive */}
      {anomaly && (
        <AnomalyGauge
          risk={anomaly.risk}
          history={anomaly.history}
          level={anomaly.level}
          diagnosis={anomaly.diagnosis_label}
        />
      )}

      <div className="ia-grid">
        <YoloStream cameraUrl={cameraUrl} />
        <div className="ia-side">
          <PersonCounter count={ia.personCount} />
        </div>
      </div>

      <div className="ia-grid">
        <RobotActions actions={ia.robotActions} />
        <PhotosGallery photos={ia.photos} />
      </div>

      <SensorDetections detections={ia.sensorDetections} />
    </section>
  );
}

export default IABlock;