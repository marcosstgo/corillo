import { useEffect, useRef, useState, useCallback } from 'react';
import Hls from 'hls.js';
import { STREAMERS, Streamer } from '../streamers';
import { LiveState } from '../useLive';

const ROTATE_MS = 8000;

interface Props { live: LiveState }

function extractColor(gradient: string): string {
  const m = gradient.match(/#[0-9a-fA-F]{6}/);
  return m ? m[0] : '#00bfff';
}

export default function FeaturedPlayer({ live }: Props) {
  const videoRef   = useRef<HTMLVideoElement>(null);
  const hlsRef     = useRef<Hls | null>(null);
  const rafRef     = useRef<number>(0);
  const startRef   = useRef<number>(0);
  const barRef     = useRef<HTMLDivElement>(null);

  const [featured, setFeatured]   = useState<Streamer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [viewers, setViewers]     = useState(0);
  const [glowColor, setGlowColor] = useState('#00bfff');
  const [prevColor, setPrevColor] = useState('#00bfff');
  const [fadeGlow, setFadeGlow]   = useState(false); // true = prev fading out, next fading in
  const [muted, setMuted]         = useState(true);
  const [rotateIdx, setRotateIdx] = useState(0);

  // Derive live list
  const liveList = STREAMERS.filter(s => s.key && live[s.key]?.ready);

  // Rotation bar animation
  const animateBar = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    startRef.current = performance.now();
    function frame(now: number) {
      const pct = Math.min((now - startRef.current) / ROTATE_MS, 1) * 100;
      if (barRef.current) barRef.current.style.width = pct + '%';
      if (pct < 100) rafRef.current = requestAnimationFrame(frame);
    }
    rafRef.current = requestAnimationFrame(frame);
  }, []);

  // Load HLS
  const loadStream = useCallback((key: string) => {
    const video = videoRef.current;
    if (!video) return;
    hlsRef.current?.destroy();
    hlsRef.current = null;

    const src = `https://corillo.live/live/${encodeURIComponent(key)}/index.m3u8`;

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src;
      video.load();
      video.play().catch(() => {});
    } else if (Hls.isSupported()) {
      const hls = new Hls({ lowLatencyMode: false, maxBufferLength: 12 });
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => { video.play().catch(() => {}); });
      hls.on(Hls.Events.ERROR, (_e, d) => { if (d.fatal) setIsPlaying(false); });
      hlsRef.current = hls;
    }
  }, []);

  // Set featured channel with glow crossfade
  const setChannel = useCallback((s: Streamer) => {
    const color = extractColor(s.color);
    setPrevColor(glowColor);
    setGlowColor(color);
    setFadeGlow(true);
    setTimeout(() => setFadeGlow(false), 1100);
    setFeatured(s);
    setIsPlaying(!!s.key && (live[s.key!]?.ready ?? false));
    setViewers(s.key ? live[s.key]?.viewers ?? 0 : 0);
    if (s.key && live[s.key]?.ready) loadStream(s.key);
    else { hlsRef.current?.destroy(); if (videoRef.current) videoRef.current.src = ''; }
    animateBar();
  }, [glowColor, live, loadStream, animateBar]);

  // Initial + rotation
  useEffect(() => {
    if (liveList.length === 0) {
      const fallback = STREAMERS.find(s => !s.soon) ?? null;
      if (fallback && fallback.key !== featured?.key) setChannel(fallback);
      return;
    }
    const idx = rotateIdx % liveList.length;
    const next = liveList[idx];
    if (next.key !== featured?.key) setChannel(next);

    const id = setTimeout(() => setRotateIdx(i => i + 1), ROTATE_MS);
    return () => clearTimeout(id);
  }, [rotateIdx, liveList.length, live]);

  // Sync viewer count
  useEffect(() => {
    if (featured?.key) setViewers(live[featured.key]?.viewers ?? 0);
  }, [live, featured?.key]);

  // Cleanup
  useEffect(() => () => {
    hlsRef.current?.destroy();
    cancelAnimationFrame(rafRef.current);
  }, []);

  const color1 = extractColor(featured?.color ?? 'linear-gradient(#00bfff,#00bfff)');

  return (
    <div className={`featured-wrap${isPlaying ? ' playing' : ''}`}>
      {/* Background grid */}
      <div className="featured-bg" />

      {/* Glow layers */}
      <div className="glow-layer" style={{
        background: `radial-gradient(ellipse 70% 80% at 60% 50%, ${prevColor}22 0%, transparent 70%)`,
        opacity: fadeGlow ? 0 : 1, transition: 'opacity 1.1s ease',
        position: 'absolute', inset: 0, pointerEvents: 'none',
      }} />
      <div className="glow-layer" style={{
        background: `radial-gradient(ellipse 70% 80% at 60% 50%, ${glowColor}22 0%, transparent 70%)`,
        opacity: fadeGlow ? 1 : 0, transition: 'opacity 1.1s ease',
        position: 'absolute', inset: 0, pointerEvents: 'none',
      }} />

      {/* Watermark letter */}
      <div className="featured-letter">{featured?.ava ?? ''}</div>

      {/* Video */}
      <video
        ref={videoRef}
        className="featured-video"
        autoPlay muted={muted} playsInline
      />

      {/* Offline state */}
      {!isPlaying && (
        <div className="featured-offline">
          <div className="featured-offline-icon">📡</div>
          <p>Sin stream activo</p>
        </div>
      )}

      {/* Viewers badge */}
      <div className="featured-viewers" style={{ display: isPlaying ? 'flex' : 'none' }}>
        <span style={{ fontSize: 10, color: 'var(--accent)' }}>👁</span>
        <span>{viewers}</span>
      </div>

      {/* Overlay */}
      <div className="featured-overlay">
        <div id="featuredContent">
          {featured && (
            <div>
              {isPlaying
                ? <div className="featured-live-tag"><span className="live-dot" />EN VIVO</div>
                : <div className="featured-vod-tag">OFFLINE</div>
              }
              <div className="featured-name">
                {featured.name.split('').map((ch, i) =>
                  <span key={i} style={i === 0 ? { color: 'var(--accent)', textShadow: `0 0 30px ${color1}66` } : {}}>
                    {ch}
                  </span>
                )}
              </div>
              <div className="featured-sub">{featured.sub}</div>
            </div>
          )}
        </div>
        <div className="featured-actions">
          {featured?.key && (
            <a href={`https://corillo.live/${featured.key}/`} target="_blank" rel="noopener" className="nav-btn solid">
              Ver canal →
            </a>
          )}
          <button className="nav-btn" onClick={() => setMuted(m => !m)}>
            {muted ? '🔇' : '🔊'}
          </button>
        </div>
      </div>

      {/* Rotation bar */}
      {liveList.length > 1 && (
        <div className="rotate-bar" ref={barRef} />
      )}
    </div>
  );
}
