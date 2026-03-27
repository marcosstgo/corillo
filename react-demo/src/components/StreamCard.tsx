import { Streamer } from '../streamers';
import { LiveState } from '../useLive';

interface Props { streamer: Streamer; live: LiveState }

export default function StreamCard({ streamer: s, live }: Props) {
  const state   = s.key ? live[s.key] : null;
  const isLive  = state?.ready ?? false;
  const viewers = state?.viewers ?? 0;
  const href    = s.key ? `https://corillo.live/${s.key}/` : '#';
  const thumb   = s.key ? `https://corillo.live/assets/thumbs/${s.key}.jpg` : '';
  const preview = s.key ? `https://corillo.live/assets/thumbs/${s.key}-preview.mp4` : '';

  return (
    <a href={href} target="_blank" rel="noopener" className="stream-card">
      <div className="stream-thumb">
        <div className="stream-thumb-inner">
          <div className="stream-thumb-letter">{s.ava}</div>
        </div>
        {isLive && thumb && (
          <img className="stream-thumb-img" src={thumb} alt={s.name} loading="lazy"
            onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
        )}
        {isLive && preview && (
          <video className="stream-thumb-preview" src={preview} muted loop playsInline
            onMouseEnter={e => (e.target as HTMLVideoElement).play().catch(() => {})}
            onMouseLeave={e => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }}
          />
        )}
        {isLive && (
          <div className="stream-live-tag">
            <span className="live-dot" />EN VIVO
          </div>
        )}
        {isLive && viewers > 0 && (
          <div className="stream-viewers">
            <span style={{ fontSize: 9 }}>👁</span>{viewers}
          </div>
        )}
      </div>
      <div className="stream-body">
        <div className="stream-name" style={{ background: s.color, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          {s.name}
        </div>
        <div className="stream-desc">{s.sub}</div>
      </div>
    </a>
  );
}
