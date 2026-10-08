import { useState } from 'react';

function YoloStream({ cameraUrl }) {
  const [error, setError] = useState(false);

  return (
    <div className="ia-card ia-camera">
      <h4>📹 Flux YOLO</h4>
      {error ? (
        <div className="camera-placeholder">⚠️ Flux indisponible</div>
      ) : (
        <img
          src={cameraUrl}
          alt="Flux YOLO"
          className="yolo-stream"
          onError={() => setError(true)}
        />
      )}
    </div>
  );
}

export default YoloStream;