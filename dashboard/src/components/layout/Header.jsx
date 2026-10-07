function Header({ connected }) {
  return (
    <header className="header">
      <h1>SENTINEL-X</h1>
      <span className={connected ? 'status online' : 'status offline'}>
        {connected ? '🟢 Connecté' : '🔴 Déconnecté'}
      </span>
    </header>
  );
}

export default Header;