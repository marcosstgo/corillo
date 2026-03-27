import { useLive } from './useLive';
import { STREAMERS } from './streamers';
import CorrilloLogo from './components/CorrilloLogo';
import Sidebar from './components/Sidebar';
import FeaturedPlayer from './components/FeaturedPlayer';
import StreamCard from './components/StreamCard';
import './app.css';

export default function App() {
  const live = useLive();
  const liveCount = STREAMERS.filter(s => s.key && live[s.key]?.ready).length;
  const liveStreamers = STREAMERS.filter(s => s.key && live[s.key]?.ready);

  return (
    <div className="app">
      {/* ── NAV ── */}
      <nav>
        <a href="https://corillo.live" className="nav-logo">
          <CorrilloLogo height={36} />
        </a>
        <div className="nav-spacer" />
        {liveCount > 0 && (
          <div className="nav-live" style={{ display: 'flex' }}>
            <span className="live-dot" />
            {liveCount} en vivo
          </div>
        )}
        <a href="https://corillo.live/join/" className="nav-btn solid">+ Unirse</a>
        <span className="nav-badge">React Demo</span>
      </nav>

      {/* ── LAYOUT ── */}
      <div className="layout">
        <Sidebar live={live} />

        <main>
          {/* Featured player */}
          <FeaturedPlayer live={live} />

          {/* Live grid */}
          <div className="content-section">
            <div className="section-header">
              <h2>EN VIVO</h2>
              <span className="section-count">
                {liveCount > 0 ? `${liveCount} stream${liveCount > 1 ? 's' : ''}` : '—'}
              </span>
              <div className="section-line" />
            </div>
            <div className="live-grid">
              {liveStreamers.length > 0
                ? liveStreamers.map(s => (
                    <StreamCard key={s.key} streamer={s} live={live} />
                  ))
                : (
                  <div className="no-live-msg">
                    <span>📡</span>
                    <span>Ningún canal en vivo en este momento</span>
                  </div>
                )
              }
            </div>
          </div>

          {/* Footer */}
          <footer className="site-footer">
            <div className="foot-inner">
              <div className="foot-left">
                <div className="foot-brand">
                  <CorrilloLogo height={28} />
                </div>
                <div className="foot-info">Puerto Rico<br />Plataforma independiente</div>
              </div>
              <div className="foot-links">
                <a href="https://corillo.live/multiplayer/">Multiplayer</a>
                <span className="foot-sep">·</span>
                <a href="https://corillo.live/join/">Crear Canal</a>
                <span className="foot-sep">·</span>
                <a href="https://corillo.live">← Sitio principal</a>
              </div>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
