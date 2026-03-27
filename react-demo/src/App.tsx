import { useLive } from './useLive';
import { STREAMERS } from './streamers';
import FeaturedPlayer from './components/FeaturedPlayer';
import ChannelCard from './components/ChannelCard';
import './app.css';

export default function App() {
  const live = useLive();
  const liveCount = STREAMERS.filter(s => s.key && live[s.key]?.ready).length;

  return (
    <div className="app">
      {/* Nav */}
      <header className="nav">
        <div className="container nav-inner">
          <a href="https://corillo.live" className="nav-brand">
            <span className="nav-logo">CORILLO</span>
            <span className="nav-tag">Puerto Rico</span>
          </a>
          <div className="nav-right">
            {liveCount > 0 && (
              <span className="nav-live-count">
                <span className="live-dot" />
                {liveCount} en vivo
              </span>
            )}
            <span className="nav-badge">React Demo</span>
          </div>
        </div>
      </header>

      {/* Featured player */}
      <section className="featured-section">
        <div className="container">
          <FeaturedPlayer streamers={STREAMERS} liveState={live} />
        </div>
      </section>

      {/* Channel grid */}
      <section className="grid-section">
        <div className="container">
          <div className="grid-header">
            <h2 className="grid-title">CANALES</h2>
            {liveCount > 0 && (
              <span className="grid-live-badge">
                <span className="live-dot" />
                {liveCount} EN VIVO
              </span>
            )}
          </div>
          <div className="channel-grid">
            {STREAMERS.map((s, i) => (
              <ChannelCard
                key={s.key ?? 'soon'}
                streamer={s}
                liveState={live}
                index={i}
              />
            ))}
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="container">
          <span>CORILLO · Puerto Rico · React + Vite + hls.js</span>
          <a href="https://corillo.live">← Volver al sitio principal</a>
        </div>
      </footer>
    </div>
  );
}
