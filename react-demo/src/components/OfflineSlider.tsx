import { useState, useEffect, useRef } from 'react';
import { Vod } from '../useVods';
import { STREAMERS } from '../streamers';
import { fmtDuration, relativeTime } from '../utils';

const SLIDE_INTERVAL = 60_000;

export default function OfflineSlider({ vods }: { vods: Vod[] }) {
  const [idx, setIdx]       = useState(0);
  const touchStartX         = useRef(0);

  // Auto-advance
  useEffect(() => {
    if (vods.length <= 1) return;
    const id = setTimeout(() => setIdx(i => (i + 1) % vods.length), SLIDE_INTERVAL);
    return () => clearTimeout(id);
  }, [idx, vods.length]);

  if (vods.length === 0) return null;

  const goTo = (n: number) => setIdx(((n % vods.length) + vods.length) % vods.length);

  return (
    <div className="offline-slider-wrap">
      <div className="offline-sl-hd">
        <span>Últimas transmisiones</span>
        <div className="section-line" />
        <a href="https://corillo.live/vods/" target="_blank" rel="noopener">Ver todos →</a>
      </div>

      <div
        className="offline-stage"
        onTouchStart={e => { touchStartX.current = e.touches[0].clientX; }}
        onTouchEnd={e => {
          const dx = e.changedTouches[0].clientX - touchStartX.current;
          if (Math.abs(dx) > 40) goTo(dx < 0 ? idx + 1 : idx - 1);
        }}
      >
        {vods.map((vod, i) => {
          const s    = STREAMERS.find(x => x.key === vod.channel);
          const name = s?.name ?? vod.channel.toUpperCase();
          const meta = [relativeTime(vod.date), vod.duration ? fmtDuration(vod.duration) : ''].filter(Boolean).join(' · ');
          return (
            <a
              key={vod.id}
              href={`https://corillo.live/${vod.channel}/`}
              target="_blank" rel="noopener"
              className={`offline-slide${i === idx ? ' active' : ''}`}
            >
              {vod.thumb && (
                <div className="offline-slide-bg" style={{ backgroundImage: `url('${vod.thumb}')` }} />
              )}
              <div className="offline-slide-grad" />
              <div className="offline-slide-info">
                <div className="offline-slide-tag">🎬 Última transmisión</div>
                <div className="offline-slide-name">{name}</div>
                <div className="offline-slide-meta">{meta}</div>
              </div>
            </a>
          );
        })}

        {/* key={idx} remounts element → restarts CSS animation */}
        <div className="offline-bar-wrap">
          <div key={idx} className="offline-bar" />
        </div>
      </div>

      {vods.length > 1 && (
        <div className="offline-dots">
          {vods.map((_, i) => (
            <button
              key={i}
              className={`offline-dot${i === idx ? ' active' : ''}`}
              onClick={() => goTo(i)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
