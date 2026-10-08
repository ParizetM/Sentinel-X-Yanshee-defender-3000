function PhotosGallery({ photos = [] }) {
  return (
    <div className="ia-card">
      <h4>📸 Photos prises {photos.length > 0 && <span style={{ fontSize: '12px', color: '#00e5ff' }}>({photos.length})</span>}</h4>
      {photos.length === 0 ? (
        <p className="empty">Aucune photo enregistrée</p>
      ) : (
        <div className="photos-grid">
          {photos.map((p, i) => (
            <div key={i} className="photo-item">
              <a href={p.url} target="_blank" rel="noreferrer" title="Cliquer pour afficher la photo en grand">
                <img
                  src={p.url}
                  alt={p.label || `Photo ${i + 1}`}
                  className="photo-thumb"
                />
              </a>
              {p.time && <span className="photo-time">{p.time}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default PhotosGallery;