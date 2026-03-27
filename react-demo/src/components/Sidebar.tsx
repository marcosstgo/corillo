import { STREAMERS } from '../streamers';
import { LiveState } from '../useLive';

interface Props { live: LiveState }

export default function Sidebar({ live }: Props) {
  const liveStreamers  = STREAMERS.filter(s => s.key && live[s.key]?.ready);
  const offlineStreamers = STREAMERS.filter(s => s.key && !live[s.key]?.ready && !s.soon);

  function ChannelRow({ s, isLive }: { s: typeof STREAMERS[0]; isLive: boolean }) {
    const viewers = s.key ? live[s.key]?.viewers ?? 0 : 0;
    return (
      <a
        href={s.key ? `https://corillo.live/${s.key}/` : '#'}
        className={`channel-row${isLive ? ' is-live' : ''}`}
        target="_blank" rel="noopener"
      >
        <div className="ch-ava" style={{ background: s.color }}>{s.ava}</div>
        <div className="ch-info">
          <div className="ch-name">{s.name}</div>
          <div className={`ch-status${isLive ? ' live' : ''}`}>
            {isLive ? `${viewers > 0 ? viewers + ' viendo' : 'En vivo'}` : s.sub}
          </div>
        </div>
        {isLive && <span className="live-pip" />}
      </a>
    );
  }

  return (
    <aside>
      <div className="aside-nav">
        <a href="https://corillo.live/multiplayer/" className="sidebar-nav-link">Multiplayer</a>
        <a href="https://corillo.live/join/" className="sidebar-nav-link">+ Crear Canal</a>
        <a href="https://corillo.live/perfil/" className="sidebar-nav-link">Mi Perfil</a>
      </div>
      <hr className="aside-divider" />

      {liveStreamers.length > 0 && (
        <div className="aside-section">
          <div className="aside-label">En vivo</div>
          {liveStreamers.map(s => <ChannelRow key={s.key} s={s} isLive />)}
          <hr className="aside-divider" />
        </div>
      )}

      <div className="aside-section">
        <div className="aside-label">Canales</div>
        {offlineStreamers.map(s => <ChannelRow key={s.key} s={s} isLive={false} />)}
      </div>
      <div className="aside-footer">CORILLO<br />STREAM PLATFORM<br />PUERTO RICO</div>
    </aside>
  );
}
