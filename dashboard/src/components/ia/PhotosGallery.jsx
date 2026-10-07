function PhotosGallery({ photos = [] }) {
  return (
    <div className="ia-card">
      <h4>📸 Photos prises</h4>
      {photos.length === 0 ? (
        <p className="empty">Aucune photo</p>
      ) : (
        <div className="photos-grid">
          {photos.map((p, i) => (
            <img key={i} src={p.url} alt={p.label || 'Photo'} className="photo-thumb" />
          ))}
        </div>
      )}
    </div>
  );
}

export default PhotosGallery;