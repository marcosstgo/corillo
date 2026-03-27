import { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import { Streamer } from '../streamers';
import { LiveState } from '../useLive';

interface Props {
  streamers: Streamer[];
  liveState: LiveState;
}

export default function FeaturedPlayer({ streamers, liveState }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [muted, setMuted] = useState(true);

  // Pick featured: first live channel, or first non-soon streamer
  const liveChannels = streamers.filter(s => s.key && liveState[s.key]?.ready);
  const featured = liveChannels[0] ?? streamers.find(s => !s.soon) ?? null;

  useEffect(() => {
    const key = featured?.key ?? null;
    if (!key || key === activeKey) return;
    setActiveKey(key);

    const video = videoRef.current;
    if (!video) return;

    // Cleanup previous
    hlsRef.current?.destroy();
    hlsRef.current = null;

    const src = `https://corillo.live/live/${encodeURIComponent(key)}/index.m3u8`;

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Native HLS (Safari/iOS)
      video.src = src;
      video.load();
      video.play().catch(() => {});
    } else if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: false,
        maxBufferLength: 12,
        maxMaxBufferLength: 30,
      });
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {});
      });
      hlsRef.current = hls;
    }

    return () => {
      hlsRef.current?.destroy();
      hlsRef.current = null;
    };
  }, [featured?.key]);

  if (!featured || !featured.key) return null;

  const isLive = liveState[featured.key]?.ready ?? false;
  const viewers = liveState[featured.key]?.viewers ?? 0;

  return (
    <div className="featured" style={{ '--fc': featured.color } as React.CSSProperties}>
      <div className="featured-video-wrap">
        <video
          ref={videoRef}
          muted={muted}
          autoPlay
          playsInline
          className="featured-video"
        />
        <div className="featured-overlay">
          <div className="featured-meta">
            <div className="featured-ava" style={{ background: featured.color }}>
              {featured.ava}
            </div>
            <div className="featured-info">
              <span className="featured-name">{featured.name}</span>
              <span className="featured-sub">{featured.sub}</span>
            </div>
          </div>
          <div className="featured-controls">
            {isLive && (
              <div className="featured-live-badge">
                <span className="live-dot" />
                EN VIVO
                {viewers > 0 && <span>· {viewers} viendo</span>}
              </div>
            )}
            <button
              className="mute-btn"
              onClick={() => setMuted(m => !m)}
              aria-label={muted ? 'Activar sonido' : 'Silenciar'}
            >
              {muted ? '🔇 Activar sonido' : '🔊 Silenciar'}
            </button>
          </div>
        </div>
        {!isLive && (
          <div className="featured-offline">
            <span className="featured-ava-lg" style={{ background: featured.color }}>
              {featured.ava}
            </span>
            <p>Offline</p>
          </div>
        )}
      </div>
    </div>
  );
}
