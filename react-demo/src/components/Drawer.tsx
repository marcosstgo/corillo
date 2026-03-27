import { useState } from 'react';
import CorrilloLogo from './CorrilloLogo';
import { STREAMERS } from '../streamers';
import { LiveState } from '../useLive';

interface Props {
  live: LiveState;
  open: boolean;
  onClose: () => void;
}

const MAX_OFFLINE = 8;

export default function Drawer({ live, open, onClose }: Props) {
  const [showAll, setShowAll] = useState(false);

  const liveStreamers    = STREAMERS.filter(s => s.key && live[s.key]?.ready);
  const offlineStreamers = STREAMERS.filter(s => s.key && !live[s.key]?.ready && !s.soon);
  const visibleOffline   = showAll ? offlineStreamers : offlineStreamers.slice(0, MAX_OFFLINE);

  return (
    <>
      <div className={`drawer-overlay${open ? ' open' : ''}`} onClick={onClose} />
      <div className={`drawer${open ? ' open' : ''}`}>
        <div className="drawer-header">
          <CorrilloLogo height={30} />
          <button className="drawer-close" onClick={onClose}>✕</button>
        </div>
        <div className="drawer-body">
          <div className="aside-nav">
            <a href="https://corillo.live/multiplayer/" className="sidebar-nav-link" onClick={onClose}>Multiplayer</a>
            <a href="https://corillo.live/join/" className="sidebar-nav-link" onClick={onClose}>+ Crear Canal</a>
            <a href="https://corillo.live/perfil/" className="sidebar-nav-link" onClick={onClose}>Mi Perfil</a>
          </div>
          <hr className="aside-divider" />

          {liveStreamers.length > 0 && (
            <div className="aside-section">
              <div className="aside-label">En vivo</div>
              {liveStreamers.map(s => {
                const viewers = s.key ? live[s.key]?.viewers ?? 0 : 0;
                return (
                  <a key={s.key} href={`https://corillo.live/${s.key}/`} className="channel-row is-live" onClick={onClose}>
                    <div className="ch-ava" style={{ background: s.color }}>{s.ava}</div>
                    <div className="ch-info">
                      <div className="ch-name">{s.name}</div>
                      <div className="ch-status live">{viewers > 0 ? `${viewers} viendo` : 'En vivo'}</div>
                    </div>
                    {viewers > 0 ? <span className="ch-viewers">{viewers}</span> : <span className="live-pip" />}
                  </a>
                );
              })}
              <hr className="aside-divider" />
            </div>
          )}

          <div className="aside-section">
            <div className="aside-label">Canales</div>
            {visibleOffline.map(s => (
              <a key={s.key} href={`https://corillo.live/${s.key}/`} className="channel-row" onClick={onClose}>
                <div className="ch-ava" style={{ background: s.color, opacity: .45 }}>{s.ava}</div>
                <div className="ch-info">
                  <div className="ch-name" style={{ color: 'rgba(232,246,255,.35)' }}>{s.name}</div>
                  <div className="ch-status">Offline</div>
                </div>
              </a>
            ))}
            {!showAll && offlineStreamers.length > MAX_OFFLINE && (
              <button className="sidebar-show-all" onClick={() => setShowAll(true)}>
                Ver {offlineStreamers.length - MAX_OFFLINE} más →
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
