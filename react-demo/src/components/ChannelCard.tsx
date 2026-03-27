import { Streamer } from '../streamers';
import { LiveState } from '../useLive';

interface Props {
  streamer: Streamer;
  liveState: LiveState;
  index: number;
}

export default function ChannelCard({ streamer, liveState, index }: Props) {
  if (streamer.soon) {
    return (
      <div className="card card-soon" style={{ animationDelay: `${index * 40}ms` }}>
        <div className="card-ava" style={{ background: streamer.color }}>
          <span>{streamer.ava}</span>
        </div>
        <div className="card-info">
          <span className="card-name">{streamer.name}</span>
          <span className="card-sub">{streamer.sub}</span>
        </div>
        <span className="badge-soon">PRONTO</span>
      </div>
    );
  }

  const state = streamer.key ? liveState[streamer.key] : null;
  const isLive = state?.ready ?? false;
  const viewers = state?.viewers ?? 0;
  const href = streamer.key ? `https://corillo.live/${streamer.key}/` : '#';

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener"
      className={`card ${isLive ? 'card-live' : ''}`}
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <div className="card-ava" style={{ background: streamer.color }}>
        <span>{streamer.ava}</span>
        {isLive && <span className="ava-pulse" />}
      </div>
      <div className="card-info">
        <div className="card-name-row">
          <span className="card-name">{streamer.name}</span>
          {streamer.host && <span className="badge-host">HOST</span>}
        </div>
        <span className="card-sub">{streamer.sub}</span>
      </div>
      <div className="card-right">
        {isLive ? (
          <div className="live-pill">
            <span className="live-dot" />
            <span>EN VIVO</span>
            {viewers > 0 && <span className="viewers">{viewers}</span>}
          </div>
        ) : (
          <span className="offline-label">OFFLINE</span>
        )}
      </div>
    </a>
  );
}
