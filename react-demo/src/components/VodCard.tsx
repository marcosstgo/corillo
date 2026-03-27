import { useRef } from 'react';
import { Vod } from '../useVods';
import { STREAMERS } from '../streamers';
import { fmtDuration, relativeTime } from '../utils';

const canHover = window.matchMedia('(hover: hover)').matches;

export default function VodCard({ vod }: { vod: Vod }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const s   = STREAMERS.find(x => x.key === vod.channel) ?? { name: vod.channel.toUpperCase(), color: '', ava: vod.channel[0]?.toUpperCase() ?? '?', key: vod.channel, sub: '' };
  const dur = fmtDuration(vod.duration);

  return (
    <a href={`https://corillo.live/vods/v/?id=${vod.id}`} target="_blank" rel="noopener" className="stream-card">
      <div className="stream-thumb">
        <div className="stream-thumb-inner">
          <div className="stream-thumb-letter">{s.ava}</div>
        </div>
        {vod.thumb && (
          <img className="stream-thumb-img" src={vod.thumb} alt={s.name} loading="lazy"
            onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
        )}
        {canHover && vod.preview && (
          <video
            ref={videoRef}
            className="stream-thumb-preview"
            src={vod.preview}
            muted loop playsInline preload="none"
            onMouseEnter={() => videoRef.current?.play().catch(() => {})}
            onMouseLeave={() => { if (videoRef.current) { videoRef.current.pause(); videoRef.current.currentTime = 0; } }}
          />
        )}
        {dur && <div className="vod-duration">{dur}</div>}
      </div>
      <div className="stream-body">
        <div className="stream-name" style={{ background: s.color, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          {s.name}
        </div>
        <div className="stream-desc">{relativeTime(vod.date)}</div>
      </div>
    </a>
  );
}
