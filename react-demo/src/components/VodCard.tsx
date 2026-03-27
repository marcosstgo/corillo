import { useRef } from 'react';
import { Vod } from '../useVods';
import { STREAMERS } from '../streamers';

function fmtDuration(s: number): string {
  if (!s) return '';
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`;
}

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 2)  return 'Hace un momento';
  if (mins < 60) return `Hace ${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `Hace ${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return 'Ayer';
  if (days < 7)  return `Hace ${days} días`;
  return `Hace ${Math.floor(days / 7)} sem`;
}

const canHover = window.matchMedia('(hover: hover)').matches;

export default function VodCard({ vod }: { vod: Vod }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const s = STREAMERS.find(x => x.key === vod.channel) ?? { name: vod.channel.toUpperCase(), color: '', ava: vod.channel[0].toUpperCase(), key: vod.channel, sub: '' };
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
