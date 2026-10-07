import PersonCounter from './PersonCounter';
import DetectionStats from './DetectionStats';
import YoloStream from './YoloStream';
import RobotActions from './RobotActions';
import PhotosGallery from './PhotosGallery';
import SensorDetections from './SensorDetections';

function IABlock({ ia, cameraUrl }) {
  return (
    <section className="block">
      <h2>🤖 Intelligence Artificielle</h2>

      <div className="ia-grid">
        <YoloStream cameraUrl={cameraUrl} />
        <div className="ia-side">
          <PersonCounter count={ia.personCount} />
          <DetectionStats count={ia.detectionsLastHour} />
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