import { useEffect, useRef, useState, useCallback } from 'react';
import Hls from 'hls.js';
import { STREAMERS, Streamer } from '../streamers';
import { LiveState } from '../useLive';
import { useVods, Vod } from '../useVods';
import { extractColor, hexToRgba, fmtDuration, relativeTime } from '../utils';

const ROTATE_MS = 8000;
const canHover = window.matchMedia('(hover: hover)').matches;

interface Props {
  live: LiveState;
  forcedKey?: string | null;
  onFeaturedChange?: (key: string | null) => void;
}

export default function FeaturedPlayer({ live, forcedKey, onFeaturedChange }: Props) {
  const videoRef      = useRef<HTMLVideoElement>(null);
  const hlsRef        = useRef<Hls | null>(null);
  const rafRef        = useRef<number>(0);
  const startRef      = useRef<number>(0);
  const barRef        = useRef<HTMLDivElement>(null);
  const glowColorRef  = useRef('#00bfff');
  const lastForcedRef = useRef<string | null>(null);

  const [featuredStreamer, setFeaturedStreamer] = useState<Streamer | null>(null);
  const [featuredVod, setFeaturedVod]           = useState<Vod | null>(null);
  const [isPlaying, setIsPlaying]               = useState(false);
  const [viewers, setViewers]                   = useState(0);
  const [muted, setMuted]                       = useState(true);
  const [fadeOut, setFadeOut]                   = useState(false);
  const [rotateIdx, setRotateIdx]               = useState(0);
  const [vodIdx, setVodIdx]                     = useState(0);

  const [glowColor, setGlowColor] = useState('#00bfff');
  const [prevColor, setPrevColor] = useState('#00bfff');
  const [fadeGlow, setFadeGlow]   = useState(false);

  const vods     = useVods(6);
  const liveList = STREAMERS.filter(s => s.key && live[s.key]?.ready);

  const applyGlow = useCallback((colorStr: string) => {
    const c = extractColor(colorStr);
    setPrevColor(glowColorRef.current);
    glowColorRef.current = c;
    setGlowColor(c);
    setFadeGlow(true);
    setTimeout(() => setFadeGlow(false), 1100);
  }, []);

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

  const loadStream = useCallback((key: string) => {
    const video = videoRef.current;
    if (!video) return;
    hlsRef.current?.destroy();
    hlsRef.current = null;
    const src = `https://corillo.live/live/${encodeURIComponent(key)}/index.m3u8`;
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src; video.load(); video.play().catch(() => {});
    } else if (Hls.isSupported()) {
      const hls = new Hls({ lowLatencyMode: false, maxBufferLength: 12 });
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
      hls.on(Hls.Events.ERROR, (_e, d) => { if (d.fatal) setIsPlaying(false); });
      hlsRef.current = hls;
    }
  }, []);

  const withFade = useCallback((fn: () => void, animate: boolean) => {
    if (!animate) { fn(); return; }
    setFadeOut(true);
    setTimeout(() => { fn(); setFadeOut(false); }, 380);
  }, []);

  const applyLiveChannel = useCallback((s: Streamer, animate: boolean) => {
    withFade(() => {
      setFeaturedStreamer(s);
      setFeaturedVod(null);
      const isLive = !!(s.key && live[s.key]?.ready);
      setIsPlaying(isLive);
      setViewers(s.key ? live[s.key]?.viewers ?? 0 : 0);
      applyGlow(s.color || '');
      if (isLive && s.key) loadStream(s.key);
      else { hlsRef.current?.destroy(); if (videoRef.current) videoRef.current.src = ''; }
      onFeaturedChange?.(s.key ?? null);
    }, animate);
    animateBar();
  }, [live, loadStream, applyGlow, withFade, onFeaturedChange, animateBar]);

  const applyVodChannel = useCallback((vod: Vod, animate: boolean) => {
    const s = STREAMERS.find(x => x.key === vod.channel);
    withFade(() => {
      setFeaturedVod(vod);
      setFeaturedStreamer(null);
      setIsPlaying(false);
      setViewers(0);
      applyGlow(s?.color || '');
      const video = videoRef.current;
      if (video) {
        hlsRef.current?.destroy();
        hlsRef.current = null;
        if (canHover && vod.preview) {
          video.src = vod.preview; video.loop = true; video.muted = true;
          video.play().catch(() => {});
        } else {
          video.src = '';
        }
      }
      onFeaturedChange?.(null);
    }, animate);
    animateBar();
  }, [applyGlow, withFade, onFeaturedChange, animateBar]);

  // Live rotation
  useEffect(() => {
    if (liveList.length === 0) {
      hlsRef.current?.destroy();
      if (videoRef.current) videoRef.current.src = '';
      setIsPlaying(false);
      return;
    }
    const idx  = rotateIdx % liveList.length;
    const next = liveList[idx];
    if (next.key !== featuredStreamer?.key) {
      applyLiveChannel(next, !!featuredStreamer && liveList.length > 1);
    }
    const id = setTimeout(() => setRotateIdx(i => i + 1), ROTATE_MS);
    return () => clearTimeout(id);
  }, [rotateIdx, liveList.length, live]);

  // VOD rotation (when nobody is live)
  useEffect(() => {
    if (liveList.length > 0 || vods.length === 0) return;
    const vod = vods[vodIdx % vods.length];
    if (vod.id !== featuredVod?.id) {
      applyVodChannel(vod, vodIdx > 0);
    }
    const id = setTimeout(() => setVodIdx(i => i + 1), ROTATE_MS);
    return () => clearTimeout(id);
  }, [vodIdx, vods.length, liveList.length]);

  // Reset VOD index when entering VOD mode
  useEffect(() => {
    if (liveList.length === 0 && vods.length > 0) setVodIdx(0);
  }, [liveList.length]);

  // Forced key from sidebar click
  useEffect(() => {
    if (!forcedKey || forcedKey === lastForcedRef.current) return;
    lastForcedRef.current = forcedKey;
    const newIdx = liveList.findIndex(l => l.key === forcedKey);
    if (newIdx >= 0) setRotateIdx(newIdx);
  }, [forcedKey, liveList.length]);

  // Sync viewer count
  useEffect(() => {
    if (featuredStreamer?.key) setViewers(live[featuredStreamer.key]?.viewers ?? 0);
  }, [live, featuredStreamer?.key]);

  // Cleanup
  useEffect(() => () => {
    hlsRef.current?.destroy();
    cancelAnimationFrame(rafRef.current);
  }, []);

  const vodPreviewMode  = !!(featuredVod && canHover && featuredVod.preview);
  const displayStreamer = featuredStreamer ?? (featuredVod ? STREAMERS.find(s => s.key === featuredVod.channel) : null);
  const accentColor     = extractColor(displayStreamer?.color || '');
  const showBar         = liveList.length > 1 || (liveList.length === 0 && vods.length > 1);

  return (
    <div className={`featured-wrap${isPlaying ? ' playing' : ''}${vodPreviewMode ? ' vod-preview-mode' : ''}`}>
      <div className="featured-bg" />

      {/* Glow */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse 70% 90% at 25% 55%, ${hexToRgba(prevColor, .18)}, transparent 65%)`,
        opacity: fadeGlow ? 0 : 1, transition: 'opacity 1.1s ease',
      }} />
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse 70% 90% at 25% 55%, ${hexToRgba(glowColor, .18)}, transparent 65%)`,
        opacity: fadeGlow ? 1 : 0, transition: 'opacity 1.1s ease',
      }} />

      {/* VOD thumbnail background */}
      {featuredVod?.thumb && (
        <div className="featured-vod-thumb show" style={{ backgroundImage: `url('${featuredVod.thumb}')` }} />
      )}

      <div className="featured-letter">{displayStreamer?.ava ?? ''}</div>

      <video ref={videoRef} className="featured-video" autoPlay muted={muted} playsInline />

      {!isPlaying && !vodPreviewMode && !featuredVod && (
        <div className="featured-offline">
          <div className="featured-offline-icon">📡</div>
          <p>Sin stream activo</p>
        </div>
      )}

      <div className="featured-viewers" style={{ display: isPlaying ? 'flex' : 'none' }}>
        <span style={{ fontSize: 10, color: 'var(--accent)' }}>👁</span>
        <span>{viewers}</span>
      </div>

      <div className="featured-overlay">
        <div className={`featured-content-anim${fadeOut ? ' out' : ''}`}>
          {featuredStreamer && (
            <div>
              <div className="featured-live-tag"><span className="live-dot" />EN VIVO</div>
              <div className="featured-name">
                {featuredStreamer.name.split('').map((ch, i) => (
                  <span key={i} style={i === 0 ? { color: 'var(--accent)', textShadow: `0 0 30px ${accentColor}66` } : {}}>{ch}</span>
                ))}
              </div>
              <div className="featured-sub">{featuredStreamer.sub}</div>
            </div>
          )}
          {featuredVod && (() => {
            const s    = STREAMERS.find(x => x.key === featuredVod.channel);
            const name = s?.name ?? featuredVod.channel.toUpperCase();
            const c    = extractColor(s?.color ?? '');
            return (
              <div>
                <div className="featured-vod-tag">🎬 Última transmisión</div>
                <div className="featured-name">
                  {name.split('').map((ch, i) => (
                    <span key={i} style={i === 0 ? { color: 'var(--accent)', textShadow: `0 0 30px ${c}66` } : {}}>{ch}</span>
                  ))}
                </div>
                <div className="featured-sub">
                  {relativeTime(featuredVod.date)}{featuredVod.duration ? ` · ${fmtDuration(featuredVod.duration)}` : ''}
                </div>
              </div>
            );
          })()}
        </div>

        <div className={`featured-actions${fadeOut ? ' out' : ''}`}>
          {featuredStreamer?.key && (
            <a href={`https://corillo.live/${featuredStreamer.key}/`} target="_blank" rel="noopener" className="nav-btn solid">
              Ver stream →
            </a>
          )}
          {featuredVod && (
            <>
              <a href={`https://corillo.live/vods/v/?id=${featuredVod.id}`} target="_blank" rel="noopener" className="nav-btn solid">
                ▶ Ver VOD
              </a>
              <a href="https://corillo.live/vods/" target="_blank" rel="noopener" className="nav-btn">
                🎬 Todos
              </a>
            </>
          )}
          {!featuredVod && (
            <button className="nav-btn" onClick={() => setMuted(m => !m)}>
              {muted ? '🔇' : '🔊'}
            </button>
          )}
        </div>
      </div>

      {showBar && <div className="rotate-bar" ref={barRef} />}
    </div>
  );
}
