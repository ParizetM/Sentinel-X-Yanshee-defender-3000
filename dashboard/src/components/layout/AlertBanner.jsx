function AlertBanner({ alert }) {
  if (!alert) return null;

  return (
    <div className="alert-banner">
      🚨 ALERTE CRITIQUE : {alert.message}
    </div>
  );
}

export default AlertBanner;