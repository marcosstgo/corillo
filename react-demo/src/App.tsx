import { useState, useEffect } from 'react';
import { useLive } from './useLive';
import { useVods } from './useVods';
import { STREAMERS } from './streamers';
import CorrilloLogo from './components/CorrilloLogo';
import Sidebar from './components/Sidebar';
import Drawer from './components/Drawer';
import FeaturedPlayer from './components/FeaturedPlayer';
import StreamCard from './components/StreamCard';
import VodCard from './components/VodCard';
import OfflineSlider from './components/OfflineSlider';
import './app.css';

export default function App() {
  const live = useLive();
  const vods = useVods(6);
  const [drawerOpen, setDrawerOpen]         = useState(false);
  const [forcedKey, setForcedKey]           = useState<string | null>(null);
  const [currentFeatured, setCurrentFeatured] = useState<string | null>(null);
  const [version, setVersion]               = useState('');

  const liveStreamers = STREAMERS.filter(s => s.key && live[s.key]?.ready);
  const liveCount     = liveStreamers.length;
  const liveKeys      = new Set(liveStreamers.map(s => s.key));
  const offlineVods   = vods.filter(v => !liveKeys.has(v.channel));

  useEffect(() => {
    fetch('https://corillo.live/version.json')
      .then(r => r.json())
      .then(d => { if (d.version) setVersion(d.version); })
      .catch(() => {});
  }, []);

  return (
    <div className="app">
      <Drawer live={live} open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      {/* ── NAV ── */}
      <nav>
        <button className="nav-menu-btn" onClick={() => setDrawerOpen(true)}>☰</button>
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
        <Sidebar
          live={live}
          featuredKey={currentFeatured}
          onChannelClick={setForcedKey}
        />

        <main>
          <FeaturedPlayer
            live={live}
            forcedKey={forcedKey}
            onFeaturedChange={setCurrentFeatured}
          />

          {/* ── GRID ── */}
          <div className="content-section">
            <div className="section-header">
              <h2>EN VIVO</h2>
              <span className="section-count">
                {liveCount > 0 ? `${liveCount} canal${liveCount > 1 ? 'es' : ''} activo${liveCount > 1 ? 's' : ''}` : 'ninguno en vivo'}
              </span>
              <div className="section-line" />
            </div>

            {liveStreamers.length > 0 ? (
              /* Live cards + VODs for offline channels below */
              <div className="live-grid">
                {liveStreamers.map(s => (
                  <StreamCard key={s.key} streamer={s} live={live} />
                ))}
                {offlineVods.length > 0 && (
                  <>
                    <div className="vods-row-header">
                      <span>Últimas transmisiones</span>
                      <div className="section-line" />
                      <a href="https://corillo.live/vods/" target="_blank" rel="noopener">Ver todas →</a>
                    </div>
                    {offlineVods.map(v => <VodCard key={v.id} vod={v} />)}
                  </>
                )}
              </div>
            ) : vods.length > 0 ? (
              /* Nobody live — offline slider */
              <OfflineSlider vods={vods} />
            ) : (
              /* Nothing at all */
              <div className="live-grid">
                <div className="no-live-msg">
                  <span>📡</span>
                  <span>Sin streams activos ahora mismo</span>
                </div>
              </div>
            )}
          </div>

          {/* ── FOOTER ── */}
          <footer className="site-footer">
            <div className="foot-inner">
              <div className="foot-left">
                <div className="foot-brand">
                  <CorrilloLogo height={28} />
                </div>
                <div className="foot-info">Puerto Rico<br />Plataforma independiente</div>
              </div>
              <div className="foot-links">
                <a href="https://corillo.live/multiplayer/" target="_blank" rel="noopener">Multiplayer</a>
                <span className="foot-sep">·</span>
                <a href="https://corillo.live/join/" target="_blank" rel="noopener">Crear Canal</a>
                <span className="foot-sep">·</span>
                <a href="https://corillo.live" target="_blank" rel="noopener">← Sitio principal</a>
                {version && <><span className="foot-sep">·</span><span className="foot-version">v{version}</span></>}
              </div>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
